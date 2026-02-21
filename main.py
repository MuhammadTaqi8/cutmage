"""
Background Removal Microservice
Production-grade FastAPI application with rembg integration.
Optimised for CPU-only, low-RAM AWS Free Tier EC2 instances.
"""

import asyncio
import io
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from PIL import Image
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.logger import get_logger
from app.model import ModelManager
from app.security import SecurityValidator
from app.processing import process_image_bytes

# ── Logging ───────────────────────────────────────────────────────────────────
# INFO level by default — avoid chatty DEBUG noise on a small instance.
# Structured logging (one line per request summary) — see the endpoint below.
logger = get_logger(__name__)

# ── Concurrency limiter ───────────────────────────────────────────────────────
# On a free-tier EC2 (1–2 vCPUs, ~1 GB RAM), running more than 1 rembg job
# per worker simultaneously will saturate the CPU and spike RAM.
# Default: 1 job per worker.  Override with MAX_CONCURRENT_INFERENCE env var.
# With 2 Gunicorn workers this allows at most 2 concurrent inference jobs total,
# which keeps the CPU busy without thrashing.
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_INFERENCE", "1"))

# Semaphore is created inside lifespan() so it binds to the running event loop.
# Declaring the name here satisfies type-checkers.
inference_sem: asyncio.Semaphore

# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])

# ── Model singleton ────────────────────────────────────────────────────────────
model_manager = ModelManager()


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm-up model at startup; release resources on shutdown."""
    global inference_sem
    # Must be created here, after the event loop is running.
    inference_sem = asyncio.Semaphore(MAX_CONCURRENT)
    logger.info("Starting up — warming model …")
    await asyncio.get_event_loop().run_in_executor(None, model_manager.load)
    logger.info(
        "Model ready. Service is live.",
        max_concurrent_per_worker=MAX_CONCURRENT,
    )
    yield
    logger.info("Shutting down gracefully …")
    model_manager.unload()


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Background Removal API",
    version="1.0.0",
    description="Ultra-fast, secure background removal microservice.",
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Auth ───────────────────────────────────────────────────────────────────────
security = HTTPBasic(auto_error=False)


def verify_auth(credentials: Optional[HTTPBasicCredentials] = Depends(security)) -> None:
    """Optional Basic Auth — only enforced when API_KEY is set."""
    if not settings.API_KEY:
        return  # auth disabled
    import secrets
    provided = credentials.password if credentials else ""
    if not secrets.compare_digest(provided, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Basic"},
        )


# ── Schemas ────────────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float


class ReadyResponse(BaseModel):
    ready: bool
    model_loaded: bool


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = None


_start_time = time.monotonic()


# ── Health endpoints ───────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health():
    return {"status": "ok", "uptime_seconds": round(time.monotonic() - _start_time, 2)}


@app.get("/ready", response_model=ReadyResponse, tags=["ops"])
async def ready():
    loaded = model_manager.is_loaded()
    if not loaded:
        raise HTTPException(status_code=503, detail="Model not yet loaded")
    return {"ready": True, "model_loaded": True}


@app.get("/debug-model")
def debug_model():
    return {
        "backend": model_manager.backend,
        "model_name": model_manager.model_name,
        "device": model_manager.device,
    }


# ── Image downscaling helper ───────────────────────────────────────────────────
# Max megapixels before we downscale.  12 MP ≈ 4000×3000.
# Images larger than this cost disproportionately more CPU with little
# quality gain for background removal — the model works at ~1024px internally.
_MAX_MP = 12_000_000        # 12 megapixels
_DOWNSCALE_LONG_SIDE = 2048  # target longest dimension after downscale


def _maybe_downscale(raw: bytes) -> bytes:
    """
    If the image exceeds _MAX_MP, resize so its longest side is
    _DOWNSCALE_LONG_SIDE px using Pillow LANCZOS and re-encode as PNG.
    Images at or below the threshold are returned unchanged (zero copy).
    """
    img = Image.open(io.BytesIO(raw))
    w, h = img.size
    mp = w * h

    if mp <= _MAX_MP:
        return raw  # fast path — nothing to do

    # Compute scale factor so longest side == _DOWNSCALE_LONG_SIDE
    scale = _DOWNSCALE_LONG_SIDE / max(w, h)
    new_w = max(1, round(w * scale))
    new_h = max(1, round(h * scale))

    img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    # Re-encode as PNG to preserve any alpha channel from the original.
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Main endpoint ──────────────────────────────────────────────────────────────
@app.post(
    "/v1/remove-background",
    response_class=Response,
    responses={
        200: {"content": {"image/png": {}}, "description": "Transparent PNG"},
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    tags=["inference"],
)
@limiter.limit(settings.RATE_LIMIT)
async def remove_background(
    request: Request,
    file: UploadFile = File(..., description="JPEG, PNG, or WebP image"),
    _auth: None = Depends(verify_auth),
):
    request_id = request.headers.get("X-Request-ID", os.urandom(8).hex())
    t_start = time.monotonic()

    # ── Guard: model ready ─────────────────────────────────────────────────────
    if not model_manager.is_loaded():
        raise HTTPException(status_code=503, detail="Model is loading, retry shortly")

    # ── Read with size cap (stream up to limit + 1 byte) ──────────────────────
    raw = await file.read(settings.MAX_FILE_SIZE + 1)
    if len(raw) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {settings.MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )

    file_size_kb = round(len(raw) / 1024, 1)

    # ── Security validation ────────────────────────────────────────────────────
    validator = SecurityValidator(settings)
    try:
        validator.validate(raw, file.content_type or "")
    except ValueError as exc:
        logger.warning("Rejected upload", reason=str(exc), request_id=request_id)
        raise HTTPException(status_code=400, detail=str(exc))

    # ── Downscale huge images before inference ─────────────────────────────────
    # This is done in the async path (Pillow open + resize is fast at this step)
    # and saves significant CPU time inside process_image_bytes for big photos.
    try:
        raw = await asyncio.get_event_loop().run_in_executor(None, _maybe_downscale, raw)
    except Exception as exc:
        # Non-fatal — if Pillow can't open the image, security validation
        # should have caught it first; fall through to let rembg handle it.
        logger.warning("Downscale failed, passing raw bytes", exc=str(exc), request_id=request_id)

    # ── Concurrency gate ───────────────────────────────────────────────────────
    # On a small CPU-only instance, more than MAX_CONCURRENT simultaneous rembg
    # jobs thrash the CPU and blow memory.  We wait up to 3 seconds for a slot;
    # if none is available we return 503 so the client can retry quickly rather
    # than sit in a long queue.
    acquired = False
    try:
        acquired = await asyncio.wait_for(inference_sem.acquire(), timeout=3.0)
    except asyncio.TimeoutError:
        logger.warning(
            "Inference queue full after 3 s wait",
            request_id=request_id,
            queue_capacity=MAX_CONCURRENT,
        )
        raise HTTPException(
            status_code=503,
            detail="Server busy — please retry in a few seconds",
            headers={"Retry-After": "5"},
        )

    # ── Inference ──────────────────────────────────────────────────────────────
    try:
        t_inf_start = time.monotonic()
        output_bytes = await asyncio.get_event_loop().run_in_executor(
            None, process_image_bytes, raw, model_manager
        )
        processing_ms = round((time.monotonic() - t_inf_start) * 1000)
    except MemoryError:
        logger.error("OOM during processing", request_id=request_id)
        raise HTTPException(status_code=500, detail="Server out of memory")
    except Exception as exc:
        # Log full stack only for unexpected 5xx — not for every request.
        logger.exception(
            "Processing error",
            request_id=request_id,
            exc=str(exc),
        )
        raise HTTPException(status_code=500, detail="Background removal failed")
    finally:
        # Always release the semaphore, even if we raised.
        if acquired:
            inference_sem.release()

    total_ms = round((time.monotonic() - t_start) * 1000)

    # ── One log line per successful request ────────────────────────────────────
    logger.info(
        "Request complete",
        request_id=request_id,
        file_size_kb=file_size_kb,
        processing_ms=processing_ms,
        total_ms=total_ms,
        success=True,
    )

    return Response(
        content=output_bytes,
        media_type="image/png",
        headers={
            "X-Request-ID": request_id,
            "Cache-Control": "no-store",
        },
    )


# ── Global exception handler ───────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Log full stack for truly unexpected errors only.
    logger.exception("Unhandled exception", path=str(request.url))
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": "Contact support"},
    )


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Development only — single worker, local loopback.
    # In production, use the Gunicorn command below instead.
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        workers=1,
        http="httptools",
    )


# ── PRODUCTION START (small CPU-only EC2 — free tier) ─────────────────────────
#
#   gunicorn main:app \
#     --worker-class uvicorn.workers.UvicornWorker \
#     --workers 2 \
#     --bind 0.0.0.0:8000 \
#     --timeout 120 \
#     --preload \
#     --max-requests 500 \
#     --max-requests-jitter 50
#
# Why these numbers for a free-tier t2.micro / t3.micro:
#
#   --workers 2
#       2 processes is the sweet spot on a 1–2 vCPU instance.
#       More workers compete for the same CPU core and RAM, making
#       things slower, not faster.  rembg is CPU-bound and memory-hungry;
#       2 workers × ~400 MB each fits inside 1 GB RAM with headroom.
#
#   --preload
#       Loads the ML model ONCE in the master process before forking.
#       Both workers share the model weights via copy-on-write memory,
#       halving the RAM used for weights (~200 MB saved).
#
#   MAX_CONCURRENT_INFERENCE=1 (default, one per worker)
#       Each worker allows at most 1 concurrent rembg job.
#       2 workers × 1 slot = 2 simultaneous jobs max across the whole server.
#       This keeps CPU at ~90–100% (fully utilised) without over-committing
#       and triggering OOM or swapping on the tiny instance.
#
#   --max-requests 500 / --max-requests-jitter 50
#       Recycle workers every ~500 requests.  Prevents slow memory leaks
#       from accumulating over long uptimes on a RAM-constrained box.
#
#   --timeout 120
#       rembg on CPU can take 10–30 s on large images; 120 s gives
#       a wide safety margin without hanging indefinitely.
#
# Set the env var before starting if you want to tune the semaphore:
#   export MAX_CONCURRENT_INFERENCE=1   # default, recommended for free tier

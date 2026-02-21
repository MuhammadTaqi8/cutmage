"""
Background Removal Microservice
Production-grade FastAPI application with rembg integration.
"""

import asyncio
import io
import logging
import os
import struct
import time
import zlib
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.logger import get_logger
from app.model import ModelManager
from app.security import SecurityValidator
from app.processing import process_image_bytes

# ── Logging ──────────────────────────────────────────────────────────────────
logger = get_logger(__name__)

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])

# ── Model singleton ───────────────────────────────────────────────────────────
model_manager = ModelManager()

# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm-up model at startup; release on shutdown."""
    logger.info("Starting up — warming model …")
    await asyncio.get_event_loop().run_in_executor(None, model_manager.load)
    logger.info("Model ready. Service is live.")
    yield
    logger.info("Shutting down gracefully …")
    model_manager.unload()

# ── App ───────────────────────────────────────────────────────────────────────
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
# allow_origins=settings.CORS_ORIGINS,

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Auth ──────────────────────────────────────────────────────────────────────
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

# ── Schemas ───────────────────────────────────────────────────────────────────
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

# ── Health endpoints ──────────────────────────────────────────────────────────
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
        "backend": model_manager.backend,  # or however you access it
        "model_name": model_manager.model_name,
        "device": model_manager.device
    }
# ── Main endpoint ─────────────────────────────────────────────────────────────
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
    log = logger.bind(request_id=request_id) if hasattr(logger, "bind") else logger

    # ── Guard: model ready ────────────────────────────────────────────────────
    if not model_manager.is_loaded():
        raise HTTPException(status_code=503, detail="Model is loading, retry shortly")

    # ── Read with size cap (stream up to limit + 1 byte) ─────────────────────
    raw = await file.read(settings.MAX_FILE_SIZE + 1)
    if len(raw) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {settings.MAX_FILE_SIZE // (1024*1024)} MB.",
        )

    # ── Security validation ───────────────────────────────────────────────────
    validator = SecurityValidator(settings)
    try:
        validator.validate(raw, file.content_type or "")
    except ValueError as exc:
        logger.warning("Rejected upload", reason=str(exc), request_id=request_id)
        raise HTTPException(status_code=400, detail=str(exc))

    # ── Process (offload to thread pool — keeps event loop free) ─────────────
    try:
        output_bytes = await asyncio.get_event_loop().run_in_executor(
            None, process_image_bytes, raw, model_manager
        )
    except MemoryError:
        logger.error("OOM during processing", request_id=request_id)
        raise HTTPException(status_code=500, detail="Server out of memory")
    except Exception as exc:
        logger.exception("Processing error", request_id=request_id, exc=str(exc))
        raise HTTPException(status_code=500, detail="Background removal failed")

    return Response(
        content=output_bytes,
        media_type="image/png",
        headers={
            "X-Request-ID": request_id,
            "Cache-Control": "no-store",
            # "Content-Disposition": "attachment; filename=result.png",
        },
    )

# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception", path=str(request.url))
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": "Contact support"},
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        workers=1,
        http="httptools",
    )

# if __name__ == "__main__":
#     uvicorn.run(
#         "main:app",
#         host="127.0.0.1",
#         port=8000,
#         workers=1,
#         loop="uvloop",
#         http="httptools",
#     )

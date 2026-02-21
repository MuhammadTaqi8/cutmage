"""
app/model.py — Backend-agnostic ModelManager.

Loads one of three possible background-removal backends depending on the
BG_MODEL_BACKEND environment variable:

    BG_MODEL_BACKEND=u2net       (default-compatible) → rembg + ONNX U²-Net
    BG_MODEL_BACKEND=inspyrenet  → InSPyReNet via transparent-background
    BG_MODEL_BACKEND=ben2        → BEN2 (future)

The public interface is identical regardless of backend:

    model_manager.load()          # call once at startup (blocking)
    model_manager.is_loaded()     # bool — ready for inference?
    model_manager.process(bytes)  # bytes → bytes (PNG with transparency)
    model_manager.unload()        # release resources on shutdown
"""

from __future__ import annotations

import threading
from typing import Optional

from app.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# ModelManager — thin dispatcher, delegates to the selected backend
# ──────────────────────────────────────────────────────────────────────────────

class ModelManager:
    """
    Thread-safe singleton that owns exactly one model backend.

    Instantiate once at module level and share across the application.
    All public methods are safe to call from multiple threads simultaneously
    because inference is stateless (each call gets its own tensors/images).
    """

    def __init__(self) -> None:
        self._backend: Optional[object] = None   # set in load()
        self._backend_name: Optional[str] = None
        self._lock = threading.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Blocking load — intended to be called once inside run_in_executor()
        from the FastAPI lifespan coroutine so it doesn't block the event loop.

        Reads BG_MODEL_BACKEND from config and initialises the appropriate
        backend.  Idempotent: subsequent calls are no-ops.
        """
        with self._lock:
            if self._backend is not None:
                return  # already loaded

            from app.config import settings
            backend_name = settings.BG_MODEL_BACKEND.lower()
            self._backend_name = backend_name

            logger.info("Loading model backend", backend=backend_name)

            if backend_name == "u2net":
                self._backend = self._load_u2net(settings)

            elif backend_name == "inspyrenet":
                self._backend = self._load_inspyrenet(settings)

            elif backend_name == "ben2":
                raise NotImplementedError(
                    "BEN2 backend is not yet implemented. "
                    "Set BG_MODEL_BACKEND=u2net or BG_MODEL_BACKEND=inspyrenet."
                )

            else:
                raise ValueError(
                    f"Unknown BG_MODEL_BACKEND: {backend_name!r}. "
                    "Choose one of: u2net, inspyrenet, ben2"
                )

            logger.info("Model backend ready", backend=backend_name)

    def unload(self) -> None:
        """Release resources.  Called on shutdown."""
        with self._lock:
            if hasattr(self._backend, "unload"):
                self._backend.unload()
            self._backend = None
            logger.info("Model backend unloaded", backend=self._backend_name)

    def is_loaded(self) -> bool:
        return self._backend is not None

    # ── Inference ─────────────────────────────────────────────────────────────

    def process(self, image_bytes: bytes) -> bytes:
        """
        Remove the background from *image_bytes* and return a transparent PNG.

        Parameters
        ----------
        image_bytes : bytes
            Raw bytes of a JPEG, PNG, or WebP image (already size-validated
            by the security middleware before this is called).

        Returns
        -------
        bytes
            PNG-encoded RGBA image with the background set to full transparency.

        Raises
        ------
        RuntimeError
            If the model has not been loaded yet.
        """
        if self._backend is None:
            raise RuntimeError("ModelManager: model not loaded — call load() first.")
        return self._backend.process(image_bytes)

    # Legacy property kept for backwards compatibility with any code that
    # still reads `model_manager.session` (e.g. old processing.py revisions).
    @property
    def session(self):
        """
        Compatibility shim.  Returns the underlying session/remover object.
        Prefer calling process() directly.
        """
        if self._backend is None:
            raise RuntimeError("Model not loaded")
        # u2net backend exposes ._session; inspyrenet exposes ._remover
        if hasattr(self._backend, "_session"):
            return self._backend._session
        if hasattr(self._backend, "_remover"):
            return self._backend._remover
        return self._backend

    # ── Private loaders ───────────────────────────────────────────────────────

    @staticmethod
    def _load_u2net(settings) -> "_U2NetBackend":
        backend = _U2NetBackend(model_name=settings.REMBG_MODEL)
        backend.load()
        return backend

    @staticmethod
    def _load_inspyrenet(settings) -> "InSPyReNetBackend":
        from app.backends.inspyrenet import InSPyReNetBackend
        backend = InSPyReNetBackend(
            input_size=settings.INSPYRENET_INPUT_SIZE,
            fast=False,
            weights=settings.INSPYRENET_WEIGHTS,
        )
        backend.load()
        return backend


# ──────────────────────────────────────────────────────────────────────────────
# U²-Net backend (wraps rembg — original behaviour)
# ──────────────────────────────────────────────────────────────────────────────

class _U2NetBackend:
    """
    Internal backend class for rembg + ONNX U²-Net.
    Keeps the same process() contract as InSPyReNetBackend.
    """

    def __init__(self, model_name: str = "u2net") -> None:
        self._model_name = model_name
        self._session = None

    def load(self) -> None:
        try:
            import rembg
            logger.info("Loading rembg / U²-Net session", model=self._model_name)
            self._session = rembg.new_session(model_name=self._model_name)
            logger.info("rembg session ready", model=self._model_name)
        except Exception as exc:
            logger.exception("Failed to load rembg model", error=str(exc))
            raise

    def is_loaded(self) -> bool:
        return self._session is not None

    def unload(self) -> None:
        self._session = None

    def process(self, image_bytes: bytes) -> bytes:
        import io
        import rembg
        from PIL import Image

        input_image = Image.open(io.BytesIO(image_bytes))
        if input_image.mode != "RGBA":
            input_image = input_image.convert("RGBA")

        output_image: Image.Image = rembg.remove(
            input_image,
            session=self._session,
            alpha_matting=False,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=10,
            alpha_matting_erode_size=10,
            only_mask=False,
            post_process_mask=True,
        )

        buf = io.BytesIO()
        output_image.save(buf, format="PNG", optimize=False, compress_level=1)
        buf.seek(0)
        return buf.read()

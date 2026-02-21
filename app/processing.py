"""
app/processing.py — Backend-agnostic inference entry point.

The actual model logic now lives inside the backend classes
(app/backends/inspyrenet.py, and the _U2NetBackend in app/model.py).
This module is kept as a thin shim so that main.py's call-site

    process_image_bytes(raw, model_manager)

remains unchanged — zero edits required in main.py.

Thread-safe: model_manager.process() is stateless per call; all backends
allocate their working tensors/images locally inside each inference call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.model import ModelManager


def process_image_bytes(raw: bytes, model_manager: "ModelManager") -> bytes:
    """
    Remove background from raw image bytes and return transparent PNG bytes.

    Parameters
    ----------
    raw : bytes
        Raw image bytes (JPEG / PNG / WebP), already validated by the
        security layer before this function is called.
    model_manager : ModelManager
        The loaded model manager singleton.  Its process() method dispatches
        to whichever backend was configured via BG_MODEL_BACKEND.

    Returns
    -------
    bytes
        PNG-encoded RGBA image with the background removed (transparent).
    """
    return model_manager.process(raw)

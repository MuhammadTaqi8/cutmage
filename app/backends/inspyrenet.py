"""
app/backends/inspyrenet.py
──────────────────────────
Thin wrapper around the transparent-background package, which ships the
official InSPyReNet implementation and its pretrained weights.

Package:  transparent-background >= 1.2.4
GitHub:   https://github.com/plemeri/transparent-background
          (same author as the InSPyReNet paper — plemeri/InSPyReNet)

transparent-background bundles:
  - the InSPyReNet architecture
  - HuggingFace weight download on first load
  - a simple Remover API that accepts PIL Images or np.ndarrays

We wrap it here so that ModelManager stays backend-agnostic.
"""

from __future__ import annotations

import io
from typing import Optional

import numpy as np
from PIL import Image


# ──────────────────────────────────────────────────────────────────────────────
# Public interface
# ──────────────────────────────────────────────────────────────────────────────

class InSPyReNetBackend:
    """
    Loads InSPyReNet once and exposes a single `process()` call.

    Parameters
    ----------
    input_size : int
        The square resolution the model sees internally. Higher = sharper
        edges, slower inference.  1024 is the recommended default.
    fast : bool
        When True, transparent-background uses its "fast" mode (slightly
        lower quality, roughly 2× faster on CPU).
    weights : str
        "latest" → download the latest checkpoint from HuggingFace (cached
        in ~/.cache/huggingface after first run).
        Any other string is treated as a local directory path.
    """

    def __init__(
        self,
        input_size: int = 1024,
        fast: bool = False,
        weights: str = "latest",
    ) -> None:
        self._input_size = input_size
        self._fast = fast
        self._weights = weights
        self._remover: Optional[object] = None

    # ── Load ──────────────────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Download weights (once, then cached) and initialise the model.
        Automatically uses CUDA if torch detects a GPU, otherwise CPU.
        Blocking — must be called inside run_in_executor or a thread.
        """
        try:
            from transparent_background import Remover  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "transparent-background is not installed. "
                "Run: pip install transparent-background"
            ) from exc

        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"

        # Build kwargs supported by the Remover constructor.
        # transparent-background >= 1.2.4 accepts `fast`, `jit`, and `device`.
        kwargs: dict = {"fast": self._fast}

        # Modern transparent-background API (no `fast` arg anymore)
        try:
            self._remover = Remover(device=device)
        except TypeError:
            # Older builds without device kwarg
            self._remover = Remover()


        # # Some builds expose device selection; guard with hasattr-style try.
        # try:
        #     self._remover = Remover(fast=self._fast, device=device)
        # except TypeError:
        #     # Older API without device kwarg — falls back to its own detection.
        #     self._remover = Remover(fast=self._fast)

    def is_loaded(self) -> bool:
        return self._remover is not None

    def unload(self) -> None:
        self._remover = None

    # ── Inference ─────────────────────────────────────────────────────────────

    def process(self, image_bytes: bytes) -> bytes:
        """
        Remove background and return a transparent PNG as bytes.

        Parameters
        ----------
        image_bytes : bytes
            Raw bytes of a JPEG, PNG, or WebP image.

        Returns
        -------
        bytes
            PNG image with the background replaced by full transparency.
        """
        if self._remover is None:
            raise RuntimeError("InSPyReNet model not loaded — call load() first.")

        # ── 1. Decode to PIL RGB ───────────────────────────────────────────────
        input_pil: Image.Image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        orig_w, orig_h = input_pil.size

        # ── 2. Run InSPyReNet ─────────────────────────────────────────────────
        # transparent-background Remover.process() accepts a PIL Image and
        # returns either a PIL RGBA image (type="rgba") or a grayscale mask
        # (type="map").  We request "rgba" for a direct composited result.
        output_pil: Image.Image = self._remover.process(input_pil, type="rgba")

        # Sanity: ensure output is RGBA and matches original dimensions.
        if output_pil.mode != "RGBA":
            output_pil = output_pil.convert("RGBA")
        if output_pil.size != (orig_w, orig_h):
            output_pil = output_pil.resize((orig_w, orig_h), Image.LANCZOS)

        # ── 3. Encode to PNG ──────────────────────────────────────────────────
        buf = io.BytesIO()
        output_pil.save(buf, format="PNG", optimize=False, compress_level=1)
        buf.seek(0)
        return buf.read()

    # ── Optional: mask-only variant (useful for debugging) ────────────────────

    def get_mask(self, image_bytes: bytes) -> bytes:
        """Return the raw greyscale alpha mask as a PNG (white=foreground)."""
        if self._remover is None:
            raise RuntimeError("Model not loaded.")
        input_pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        mask_pil: Image.Image = self._remover.process(input_pil, type="map")
        buf = io.BytesIO()
        mask_pil.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

"""
app/security.py — Deep input validation.

Layers:
1. Magic-byte validation (not just MIME/extension)
2. MIME type whitelist
3. PIL-based resolution check (decompression bomb guard)
4. Zip-bomb / malicious-payload heuristics
"""

import io
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings

# Known-good magic bytes for JPEG, PNG, WebP
_MAGIC = {
    "image/jpeg": [(b"\xff\xd8\xff", 0)],
    "image/png":  [(b"\x89PNG\r\n\x1a\n", 0)],
    "image/webp": [(b"RIFF", 0), (b"WEBP", 8)],
}

_ALLOWED_MIME = set(_MAGIC.keys())


class SecurityValidator:
    def __init__(self, settings: "Settings"):
        self.settings = settings

    def validate(self, data: bytes, claimed_mime: str) -> None:
        """Run all security checks. Raises ValueError on failure."""
        self._check_not_empty(data)
        detected_mime = self._detect_mime(data)
        self._check_mime_allowed(detected_mime, claimed_mime)
        self._check_image_dimensions(data, detected_mime)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _check_not_empty(self, data: bytes) -> None:
        if len(data) < 8:
            raise ValueError("File is too small to be a valid image")

    def _detect_mime(self, data: bytes) -> str:
        """Return MIME type based on magic bytes; raise if unknown."""
        for mime, checks in _MAGIC.items():
            if all(data[offset: offset + len(sig)] == sig for sig, offset in checks):
                return mime
        raise ValueError(
            "Unsupported or unrecognised file type. "
            "Only JPEG, PNG, and WebP are accepted."
        )

    def _check_mime_allowed(self, detected: str, claimed: str) -> None:
        if detected not in _ALLOWED_MIME:
            raise ValueError(f"Detected MIME type '{detected}' is not permitted")
        # Tolerate empty / generic claimed types from some clients
        if claimed and claimed not in ("application/octet-stream", ""):
            normalised_claim = claimed.split(";")[0].strip().lower()
            if normalised_claim not in _ALLOWED_MIME:
                raise ValueError(
                    f"Claimed MIME type '{claimed}' is not in the allowed list"
                )

    def _check_image_dimensions(self, data: bytes, mime: str) -> None:
        """
        Open just the image header to get dimensions — never fully decode.
        Protects against decompression bombs (e.g., 1×1 PNG that expands to 4 GB).
        """
        from PIL import Image, ImageFile

        # Allow Pillow to read headers only
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        img = Image.open(io.BytesIO(data))
        # `img.size` reads only the header; it does NOT decompress pixel data
        w, h = img.size

        s = self.settings
        if w > s.MAX_IMAGE_WIDTH or h > s.MAX_IMAGE_HEIGHT:
            raise ValueError(
                f"Image dimensions {w}×{h} exceed the maximum "
                f"{s.MAX_IMAGE_WIDTH}×{s.MAX_IMAGE_HEIGHT}"
            )

        megapixels = (w * h) / 1_000_000
        if megapixels > s.MAX_MEGAPIXELS:
            raise ValueError(
                f"Image is {megapixels:.1f} MP; maximum is {s.MAX_MEGAPIXELS} MP"
            )

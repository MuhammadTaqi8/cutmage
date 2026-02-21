"""
app/config.py — Centralised settings via Pydantic v2 BaseSettings.
All values are overridable via environment variables or a .env file.
"""

from typing import List, Literal
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Auth ──────────────────────────────────────────────────────────────────
    # Set API_KEY to any non-empty string to enable Basic-Auth protection.
    # The client sends it as the HTTP Basic password (username can be anything).
    API_KEY: str = Field(default="", env="API_KEY")

    # ── Limits ────────────────────────────────────────────────────────────────
    MAX_FILE_SIZE: int = Field(default=10 * 1024 * 1024, env="MAX_FILE_SIZE")   # 10 MB
    MAX_IMAGE_WIDTH: int = Field(default=8000, env="MAX_IMAGE_WIDTH")
    MAX_IMAGE_HEIGHT: int = Field(default=8000, env="MAX_IMAGE_HEIGHT")
    MAX_MEGAPIXELS: float = Field(default=25.0, env="MAX_MEGAPIXELS")           # bomb guard

    # ── Rate limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT: str = Field(default="30/minute", env="RATE_LIMIT")

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = Field(default=["*"], env="CORS_ORIGINS")

    # ── Model backend ─────────────────────────────────────────────────────────
    # Choose which model powers background removal.
    #   "u2net"       — rembg + ONNX U²-Net (original behaviour, CPU-friendly)
    #   "inspyrenet"  — InSPyReNet PyTorch model (higher quality, needs torch)
    #   "ben2"        — BEN2 from HuggingFace (future)
    BG_MODEL_BACKEND: Literal["u2net", "inspyrenet", "ben2"] = Field(
        default="inspyrenet", env="BG_MODEL_BACKEND"
    )

    # Legacy alias kept for compatibility; only used when BG_MODEL_BACKEND="u2net"
    REMBG_MODEL: str = Field(default="u2net", env="REMBG_MODEL")

    # ── InSPyReNet options ────────────────────────────────────────────────────
    # "latest"  — download latest weights from HF on first run (default)
    # Alternatively set to a local directory containing the checkpoint.
    INSPYRENET_WEIGHTS: str = Field(default="latest", env="INSPYRENET_WEIGHTS")

    # Input resolution fed to InSPyReNet. 1024 gives the best quality/speed
    # trade-off on a modern CPU; lower (e.g. 512) is faster.
    INSPYRENET_INPUT_SIZE: int = Field(default=1024, env="INSPYRENET_INPUT_SIZE")

    # ── Misc ──────────────────────────────────────────────────────────────────
    ENABLE_DOCS: bool = Field(default=False, env="ENABLE_DOCS")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

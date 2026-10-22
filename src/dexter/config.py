"""Runtime settings read from ``DEXTER_*`` environment variables or a ``.env`` file."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Server configuration.

    Attributes:
        games: TCG names to load at startup (keys of ``dexter.games.TCG_CATALOGS``).
        top_k: Catalog matches returned per identification.
        min_sharpness: Detector sharpness below which no card is reported.
        max_upload_bytes: Largest accepted image upload in bytes.
        num_threads: ONNX Runtime intra-op threads per model.
        provider: ONNX Runtime provider preference.
        cors_origins: Browser origins allowed to call the API; empty disables CORS.
        cache_dir: Where CollectorVision stores downloaded models and catalogs.
        host: Bind address for the ``dexter`` command.
        port: Bind port for the ``dexter`` command.
    """

    model_config = SettingsConfigDict(
        env_prefix="DEXTER_", env_file=".env", extra="ignore"
    )

    games: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["pokemon"])
    top_k: int = Field(default=5, ge=1)
    min_sharpness: float = Field(default=0.02, ge=0.0)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    num_threads: int = Field(default=4, ge=1)
    provider: Literal["auto", "cpu", "gpu"] = "auto"
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    cache_dir: Path | None = None
    host: str = "127.0.0.1"
    port: int = 8000

    @field_validator("games", "cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: str | list[str]) -> list[str]:
        """Accept comma-separated strings from the environment."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

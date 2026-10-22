"""Response models for the DEXter API."""

from typing import Literal

from pydantic import BaseModel

Orientation = Literal["upright", "rotated_180"]


class CardMatch(BaseModel):
    """One catalog candidate for the scanned card."""

    card_id: str
    name: str
    identifiers: dict[str, str]
    metadata: dict[str, object] | None
    confidence: float


class IdentifyResponse(BaseModel):
    """Result of identifying a single uploaded image."""

    card_present: bool
    tcg: str
    source: str
    sharpness: float | None
    orientation: Orientation | None
    match: CardMatch | None
    alternatives: list[CardMatch]
    timing_ms: float


class GameHealthResponse(BaseModel):
    """Liveness and catalog details for one loaded game."""

    status: Literal["ok"]
    tcg: str
    source: str
    catalog_version: int
    catalog_rows: int
    version: str


class ServerHealthResponse(BaseModel):
    """Liveness for the whole server."""

    status: Literal["ok"]
    games: list[str]
    version: str

"""HTTP routes mounted under ``/DEXter``."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from dexter import __version__
from dexter.config import Settings
from dexter.pipeline import CardIdentifier
from dexter.schemas import GameHealthResponse, IdentifyResponse, ServerHealthResponse

router = APIRouter(prefix="/DEXter")


def _identifier(request: Request, tcg: str) -> CardIdentifier:
    identifiers: dict[str, CardIdentifier] = request.app.state.identifiers
    try:
        return identifiers[tcg]
    except KeyError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Unknown TCG {tcg!r}; loaded games: {sorted(identifiers)}",
        ) from None


@router.get("/health")
def server_health(request: Request) -> ServerHealthResponse:
    """Report that the server is up and which games are loaded."""
    return ServerHealthResponse(
        status="ok", games=sorted(request.app.state.identifiers), version=__version__
    )


@router.get("/{tcg}/health")
def game_health(request: Request, tcg: str) -> GameHealthResponse:
    """Report the loaded catalog for one game."""
    catalog = _identifier(request, tcg).catalog
    return GameHealthResponse(
        status="ok",
        tcg=tcg,
        source=catalog.source,
        catalog_version=catalog.version,
        catalog_rows=len(catalog),
        version=__version__,
    )


@router.post("/{tcg}/identify")
async def identify(
    request: Request, tcg: str, file: Annotated[UploadFile, File()]
) -> IdentifyResponse:
    """Identify the card in an uploaded photo.

    Send a multipart form with one ``file`` field holding a JPEG, PNG or WebP image.
    """
    identifier = _identifier(request, tcg)
    settings: Settings = request.app.state.settings
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload an image/* file"
        )
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"Image exceeds {settings.max_upload_bytes} bytes",
        )
    try:
        result = await run_in_threadpool(identifier.identify, data)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return IdentifyResponse(
        card_present=result.card_present,
        tcg=tcg,
        source=identifier.catalog.source,
        sharpness=result.sharpness,
        orientation=result.orientation,
        match=result.matches[0] if result.matches else None,
        alternatives=list(result.matches[1:]),
        timing_ms=result.timing_ms,
    )

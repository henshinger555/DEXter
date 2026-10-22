"""Application factory and the ``dexter`` console entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import collector_vision as cvg
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dexter import __version__
from dexter.config import Settings
from dexter.games import resolve_catalog_key
from dexter.pipeline import CardIdentifier
from dexter.routes import router

logger = logging.getLogger(__name__)


def load_identifiers(settings: Settings) -> dict[str, CardIdentifier]:
    """Load the corner detector and every configured catalog.

    Models and catalogs are downloaded on first use and cached afterwards.

    Args:
        settings: Server configuration naming the games to load.

    Returns:
        One ``CardIdentifier`` per configured game, keyed by its TCG name.

    Raises:
        KeyError: If ``settings.games`` names an unknown TCG.
        ValueError: If a catalog is malformed or incompatible.
        OSError: If a download or cache read fails.
    """
    detector = cvg.NeuralCornerDetector(
        num_threads=settings.num_threads,
        provider=settings.provider,
        cache_dir=settings.cache_dir,
    )
    identifiers: dict[str, CardIdentifier] = {}
    for tcg in settings.games:
        catalog = cvg.Catalog.load(
            resolve_catalog_key(tcg), cache_dir=settings.cache_dir
        )
        # Reading ``embedder`` downloads the embedding model now, not on the first
        # request, so startup fails fast and serving starts warm.
        logger.info("Loaded %s %r with %r", tcg, catalog, catalog.embedder)
        identifiers[tcg] = CardIdentifier(
            catalog, detector, settings.top_k, settings.min_sharpness
        )
    return identifiers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load models before serving; fail startup loudly if that is impossible."""
    settings: Settings = app.state.settings
    try:
        app.state.identifiers = load_identifiers(settings)
    except (KeyError, ValueError, OSError):
        logger.error("Could not load catalogs for %s", settings.games, exc_info=True)
        raise
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application.

    Args:
        settings: Configuration to use; read from the environment when omitted.

    Returns:
        The configured application with all routes mounted under ``/DEXter``.
    """
    settings = settings or Settings()
    app = FastAPI(
        title="DEXter",
        description="Identify trading cards from photos.",
        version=__version__,
        lifespan=lifespan,
        docs_url="/DEXter/docs",
        redoc_url=None,
        openapi_url="/DEXter/openapi.json",
    )
    app.state.settings = settings
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )
    app.include_router(router)
    return app


def main() -> None:
    """Run the server with settings from the environment."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = Settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)

"""Registry of the trading card games DEXter can serve.

The ``{tcg}`` segment of ``/DEXter/{tcg}/`` is resolved here to the CollectorVision
catalog key that backs it. Adding a game is one new entry plus listing it in
``DEXTER_GAMES``.
"""

TCG_CATALOGS: dict[str, str] = {
    "pokemon": "pokemon",
    "pokemon-japan": "pokemon-japan",
}


def resolve_catalog_key(tcg: str) -> str:
    """Return the CollectorVision catalog key for a TCG path name.

    Args:
        tcg: Lowercase game name from the URL, for example ``"pokemon"``.

    Returns:
        The game key accepted by ``collector_vision.Catalog.load``.

    Raises:
        KeyError: If ``tcg`` is not a known game.
    """
    try:
        return TCG_CATALOGS[tcg]
    except KeyError:
        known = ", ".join(sorted(TCG_CATALOGS))
        raise KeyError(f"Unknown TCG {tcg!r}. Known games: {known}") from None

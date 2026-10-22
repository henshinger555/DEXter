"""Tests for the TCG registry."""

import pytest

from dexter.games import resolve_catalog_key


def test_known_game_resolves_to_catalog_key() -> None:
    assert resolve_catalog_key("pokemon") == "pokemon"


def test_unknown_game_raises_with_known_names() -> None:
    with pytest.raises(KeyError, match="Known games: pokemon"):
        resolve_catalog_key("magic")

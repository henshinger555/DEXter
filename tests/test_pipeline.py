"""Tests for the identification pipeline with fake models."""

import pytest

from dexter.pipeline import CardIdentifier, decode_image
from tests.conftest import FakeCatalog, FakeDetector


def test_decode_rejects_non_image_bytes() -> None:
    with pytest.raises(ValueError, match="Could not decode image"):
        decode_image(b"definitely not an image")


def test_decode_returns_bgr_array(png_bytes: bytes) -> None:
    assert decode_image(png_bytes).shape == (64, 64, 3)


def test_no_card_returns_sharpness_only(png_bytes: bytes) -> None:
    identifier = CardIdentifier(
        FakeCatalog(), FakeDetector(card_present=False, sharpness=0.005), 3, 0.02
    )

    result = identifier.identify(png_bytes)

    assert result.card_present is False
    assert result.sharpness == 0.005
    assert result.matches == ()
    assert result.orientation is None


def test_upright_orientation_wins_when_it_scores_higher(png_bytes: bytes) -> None:
    identifier = CardIdentifier(FakeCatalog(0.9, 0.4), FakeDetector(), 3, 0.02)

    result = identifier.identify(png_bytes)

    assert result.orientation == "upright"
    assert [match.card_id for match in result.matches] == [
        "card-0-0",
        "card-0-1",
        "card-0-2",
    ]
    assert result.matches[0].confidence == 0.9
    assert result.matches[0].metadata == {
        "set": "Base Set",
        "collector_number": "0/102",
    }


def test_rotated_orientation_wins_when_it_scores_higher(png_bytes: bytes) -> None:
    identifier = CardIdentifier(FakeCatalog(0.3, 0.8), FakeDetector(), 2, 0.02)

    result = identifier.identify(png_bytes)

    assert result.orientation == "rotated_180"
    assert result.matches[0].card_id == "card-1-0"
    assert len(result.matches) == 2

"""Shared fakes standing in for CollectorVision models and catalogs."""

from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from dexter import app as app_module
from dexter.config import Settings
from dexter.pipeline import CardIdentifier

EMBEDDING_DIM = 128


class FakeDetection:
    """Detection result with a fixed verdict."""

    def __init__(self, card_present: bool, sharpness: float) -> None:
        self.card_present = card_present
        self.sharpness = sharpness

    def dewarp(self, bgr: np.ndarray) -> Image.Image:
        """Return a blank card-sized crop."""
        return Image.new("RGB", (448, 448))


class FakeDetector:
    """Detector that always reports the configured verdict."""

    def __init__(self, card_present: bool = True, sharpness: float = 0.05) -> None:
        self.card_present = card_present
        self.sharpness = sharpness

    def detect(self, image: np.ndarray, min_sharpness: float = 0.02) -> FakeDetection:
        """Ignore the image and return the configured detection."""
        return FakeDetection(self.card_present, self.sharpness)


class FakeEmbedder:
    """Embedder returning one-hot rows so searches can tell orientations apart."""

    def embed(self, images: Image.Image | list[Image.Image]) -> np.ndarray:
        """Return row ``i`` as the ``i``-th unit vector."""
        count = len(images) if isinstance(images, list) else 1
        return np.eye(count, EMBEDDING_DIM, dtype=np.float32)


class FakeCatalog:
    """Catalog whose top score depends on which orientation row is searched."""

    source = "tcgplayer"
    version = 7
    embedder = FakeEmbedder()

    def __init__(self, upright_score: float = 0.9, rotated_score: float = 0.4) -> None:
        self.scores = (upright_score, rotated_score)

    def search_records(
        self, embedding: np.ndarray, top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Return ``top_k`` descending records tagged with the orientation index."""
        index = int(np.argmax(embedding))
        return [
            {
                "id": f"card-{index}-{rank}",
                "name": f"Card {rank}",
                "identifiers": {"tcgplayer": f"{index}{rank}"},
                "metadata": {"set": "Base Set", "collector_number": f"{rank}/102"},
                "score": self.scores[index] - rank * 0.1,
            }
            for rank in range(top_k)
        ]

    def __len__(self) -> int:
        return 42


@pytest.fixture
def png_bytes() -> bytes:
    """A small valid PNG."""
    buffer = BytesIO()
    Image.new("RGB", (64, 64), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    """Settings with a small upload limit; run outside the repo so no .env leaks in."""
    monkeypatch.chdir(tmp_path)
    return Settings(games=["pokemon"], max_upload_bytes=4096, top_k=3)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> Iterator[TestClient]:
    """Test client whose startup installs fakes instead of downloading models."""
    identifier = CardIdentifier(
        FakeCatalog(), FakeDetector(), settings.top_k, settings.min_sharpness
    )
    monkeypatch.setattr(
        app_module, "load_identifiers", lambda _settings: {"pokemon": identifier}
    )
    with TestClient(app_module.create_app(settings)) as test_client:
        yield test_client

"""Image bytes to card identification."""

import time
from dataclasses import dataclass
from typing import Any, Protocol

import cv2
import numpy as np
from collector_vision import rotate_card_180
from PIL import Image

from dexter.schemas import CardMatch, Orientation

ORIENTATIONS: tuple[Orientation, Orientation] = ("upright", "rotated_180")


class Detection(Protocol):
    """Subset of ``collector_vision.DetectionResult`` the pipeline uses."""

    @property
    def card_present(self) -> bool: ...

    @property
    def sharpness(self) -> float | None: ...

    def dewarp(self, bgr: np.ndarray) -> Image.Image: ...


class Detector(Protocol):
    """Subset of ``collector_vision.NeuralCornerDetector`` the pipeline uses."""

    def detect(self, image: np.ndarray, min_sharpness: float = ...) -> Detection: ...


class Embedder(Protocol):
    """Subset of ``collector_vision.NeuralEmbedder`` the pipeline uses."""

    def embed(self, images: Image.Image | list[Image.Image]) -> np.ndarray: ...


class Catalog(Protocol):
    """Subset of ``collector_vision.CatalogV2`` the pipeline uses."""

    @property
    def source(self) -> str: ...

    @property
    def version(self) -> int: ...

    @property
    def embedder(self) -> Embedder: ...

    def search_records(
        self, embedding: np.ndarray, top_k: int = ...
    ) -> list[dict[str, Any]]: ...

    def __len__(self) -> int: ...


@dataclass(frozen=True)
class IdentifyResult:
    """Outcome of ``CardIdentifier.identify``.

    Attributes:
        card_present: Whether the detector found a card in the image.
        sharpness: Detector sharpness score, or ``None`` for older checkpoints.
        timing_ms: Wall-clock time spent on detection, embedding and search.
        orientation: Which crop orientation produced the best match.
        matches: Catalog candidates, best first; empty when no card is present.
    """

    card_present: bool
    sharpness: float | None
    timing_ms: float
    orientation: Orientation | None = None
    matches: tuple[CardMatch, ...] = ()


def decode_image(data: bytes) -> np.ndarray:
    """Decode JPEG, PNG or WebP bytes into a BGR uint8 array.

    Args:
        data: Raw encoded image bytes.

    Returns:
        The decoded image in the BGR layout OpenCV uses.

    Raises:
        ValueError: If the bytes are not a decodable image.
    """
    bgr = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("Could not decode image; expected JPEG, PNG or WebP data")
    return bgr


def _to_match(record: dict[str, Any]) -> CardMatch:
    return CardMatch(
        card_id=record["id"],
        name=record["name"],
        identifiers=record.get("identifiers") or {},
        metadata=record.get("metadata"),
        confidence=round(float(record["score"]), 4),
    )


def _top_score(records: list[dict[str, Any]]) -> float:
    return float(records[0]["score"]) if records else float("-inf")


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


class CardIdentifier:
    """Identify cards against one catalog using a shared corner detector."""

    def __init__(
        self, catalog: Catalog, detector: Detector, top_k: int, min_sharpness: float
    ) -> None:
        """Store the collaborators; the caller has already loaded the models.

        Args:
            catalog: Loaded CollectorVision catalog for one game.
            detector: Loaded corner detector.
            top_k: Number of matches to return.
            min_sharpness: Sharpness gate passed to the detector.
        """
        self.catalog = catalog
        self.detector = detector
        self.top_k = top_k
        self.min_sharpness = min_sharpness

    def identify(self, data: bytes) -> IdentifyResult:
        """Detect, dewarp, embed and search one image.

        The upright crop and its 180-degree rotation are embedded in a single
        batch, and the orientation with the stronger top match wins.

        Args:
            data: Encoded image bytes (JPEG, PNG or WebP).

        Returns:
            The identification outcome, with ``matches`` ordered best first.

        Raises:
            ValueError: If ``data`` cannot be decoded as an image.
        """
        started = time.perf_counter()
        bgr = decode_image(data)
        detection = self.detector.detect(bgr, min_sharpness=self.min_sharpness)
        if not detection.card_present:
            return IdentifyResult(
                card_present=False,
                sharpness=detection.sharpness,
                timing_ms=_elapsed_ms(started),
            )
        crop = detection.dewarp(bgr)
        embeddings = self.catalog.embedder.embed([crop, rotate_card_180(crop)])
        orientation, records = max(
            (
                (orientation, self.catalog.search_records(embedding, top_k=self.top_k))
                for orientation, embedding in zip(ORIENTATIONS, embeddings, strict=True)
            ),
            key=lambda ranked: _top_score(ranked[1]),
        )
        return IdentifyResult(
            card_present=True,
            sharpness=detection.sharpness,
            timing_ms=_elapsed_ms(started),
            orientation=orientation,
            matches=tuple(_to_match(record) for record in records),
        )

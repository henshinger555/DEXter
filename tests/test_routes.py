"""Tests for the HTTP layer."""

from fastapi.testclient import TestClient


def test_identify_returns_best_match_and_alternatives(
    client: TestClient, png_bytes: bytes
) -> None:
    response = client.post(
        "/DEXter/pokemon/identify", files={"file": ("card.png", png_bytes, "image/png")}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["card_present"] is True
    assert body["tcg"] == "pokemon"
    assert body["source"] == "tcgplayer"
    assert body["orientation"] == "upright"
    assert body["match"]["card_id"] == "card-0-0"
    assert body["match"]["name"] == "Card 0"
    assert [alt["card_id"] for alt in body["alternatives"]] == ["card-0-1", "card-0-2"]
    assert body["timing_ms"] >= 0


def test_unknown_tcg_is_404(client: TestClient, png_bytes: bytes) -> None:
    response = client.post(
        "/DEXter/magic/identify", files={"file": ("card.png", png_bytes, "image/png")}
    )

    assert response.status_code == 404
    assert "pokemon" in response.json()["detail"]


def test_undecodable_image_is_400(client: TestClient) -> None:
    response = client.post(
        "/DEXter/pokemon/identify", files={"file": ("x.png", b"nope", "image/png")}
    )

    assert response.status_code == 400


def test_non_image_content_type_is_415(client: TestClient, png_bytes: bytes) -> None:
    response = client.post(
        "/DEXter/pokemon/identify",
        files={"file": ("card.txt", png_bytes, "text/plain")},
    )

    assert response.status_code == 415


def test_oversized_upload_is_413(client: TestClient) -> None:
    response = client.post(
        "/DEXter/pokemon/identify",
        files={"file": ("big.png", b"\x89PNG" + b"0" * 5000, "image/png")},
    )

    assert response.status_code == 413


def test_server_health_lists_games(client: TestClient) -> None:
    response = client.get("/DEXter/health")

    assert response.status_code == 200
    assert response.json()["games"] == ["pokemon"]


def test_game_health_reports_catalog(client: TestClient) -> None:
    response = client.get("/DEXter/pokemon/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "tcg": "pokemon",
        "source": "tcgplayer",
        "catalog_version": 7,
        "catalog_rows": 42,
        "version": "0.1.0",
    }


def test_game_health_unknown_tcg_is_404(client: TestClient) -> None:
    assert client.get("/DEXter/magic/health").status_code == 404

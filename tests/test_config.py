"""Tests for environment-driven settings."""

from pathlib import Path

import pytest

from dexter.config import Settings


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run outside the repo so a developer .env cannot leak into the assertions."""
    monkeypatch.chdir(tmp_path)
    for name in ("DEXTER_GAMES", "DEXTER_CORS_ORIGINS"):
        monkeypatch.delenv(name, raising=False)


def test_defaults_load_pokemon_only() -> None:
    settings = Settings()

    assert settings.games == ["pokemon"]
    assert settings.cors_origins == []


def test_csv_environment_values_are_split(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEXTER_GAMES", "pokemon, pokemon-japan")
    monkeypatch.setenv("DEXTER_CORS_ORIGINS", "https://a.example,https://b.example")

    settings = Settings()

    assert settings.games == ["pokemon", "pokemon-japan"]
    assert settings.cors_origins == ["https://a.example", "https://b.example"]


def test_dotenv_file_is_read_from_working_directory(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("DEXTER_GAMES=pokemon-japan\nDEXTER_PORT=9000\n")

    settings = Settings()

    assert settings.games == ["pokemon-japan"]
    assert settings.port == 9000

# DEXter

DEXter is a small HTTP API that identifies trading cards from photos. Send it a
picture, get back the card's name, set and collector number. It wraps
[CollectorVision](https://github.com/HanClinto/CollectorVision), which finds the
card in the image, flattens it and matches it against a catalog of known cards.

Pokemon is loaded by default. Other games CollectorVision publishes catalogs for
can be enabled with one line of configuration (see "Adding a game").

## How it works

1. The uploaded image is decoded and passed to CollectorVision's corner detector.
2. If a card is present, it is dewarped to a flat 448x448 crop.
3. The crop and its 180-degree rotation are embedded in one batch, so the card
   can be upside down.
4. Each embedding is searched against the game's catalog; the orientation with
   the stronger top match wins and its candidates are returned.

Models and catalogs are downloaded from CollectorVision's feed on first start
and cached locally after that.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- About 2 GB of RAM at runtime (ONNX Runtime plus the loaded catalog), or 1 GB
  plus a swap file (see the deployment guide)
- Network access on first start to download models and catalogs

## Quick start

```sh
git clone https://github.com/<your-org>/DEXter.git
cd DEXter
uv sync
uv run dexter
```

The first start downloads the detector, the embedding model and the Pokemon
catalog, then listens on `http://127.0.0.1:8000`. Interactive docs are at
`http://127.0.0.1:8000/DEXter/docs`.

Identify a card:

```sh
curl -F "file=@card.jpg" http://127.0.0.1:8000/DEXter/pokemon/identify
```

## API

All routes live under `/DEXter/{tcg}/`, where `{tcg}` is a game name from the
registry (currently `pokemon` and `pokemon-japan`). Only games listed in
`DEXTER_GAMES` are loaded; any other name returns `404`.

### `POST /DEXter/{tcg}/identify`

Multipart form with one `file` field holding a JPEG, PNG or WebP image.

| Status | Meaning |
|---|---|
| 200 | Identification ran (check `card_present`) |
| 400 | The bytes could not be decoded as an image |
| 404 | Unknown or unloaded `{tcg}` |
| 413 | Upload larger than `DEXTER_MAX_UPLOAD_BYTES` |
| 415 | `Content-Type` of the file part is not `image/*` |

Response:

```json
{
  "card_present": true,
  "tcg": "pokemon",
  "source": "tcgplayer",
  "sharpness": 0.0637,
  "orientation": "upright",
  "match": {
    "card_id": "42382",
    "name": "Charizard",
    "identifiers": {
      "tcgplayer_product": "42382",
      "tcgplayer_category": "3",
      "tcgplayer_group": "604"
    },
    "metadata": {
      "category": "Pokemon",
      "set": "Base Set",
      "collector_number": "004/102",
      "rarity": "Holo Rare"
    },
    "confidence": 0.9145
  },
  "alternatives": [
    { "card_id": "42479", "name": "Charizard", "identifiers": { "..." : "..." }, "metadata": { "set": "Base Set 2", "collector_number": "004/130", "rarity": "Holo Rare", "category": "Pokemon" }, "confidence": 0.8042 }
  ],
  "timing_ms": 184.2
}
```

When no card is detected, `card_present` is `false`, `match` is `null`,
`alternatives` is empty and `sharpness` tells you how far below the gate the
frame was. `confidence` is a cosine similarity in roughly `[0, 1]`; treat values
under about `0.5` as unreliable.

`identifiers` and `metadata` come straight from the catalog, so their field names
depend on `source`. The TCGplayer Pokemon catalog provides `tcgplayer_product`
(the product id) and `metadata.set`, `collector_number`, `rarity` and
`category`. Different printings of the same card (for example Base Set and
Base Set Shadowless) are separate catalog rows and often appear together in
`alternatives` with close scores.

### `GET /DEXter/{tcg}/health`

```json
{ "status": "ok", "tcg": "pokemon", "source": "tcgplayer", "catalog_version": 12, "catalog_rows": 21034, "version": "0.1.0" }
```

### `GET /DEXter/health`

```json
{ "status": "ok", "games": ["pokemon"], "version": "0.1.0" }
```

## Configuration

Settings are read from `DEXTER_*` environment variables or a `.env` file in the
working directory. Copy `.env.example` to get started.

| Variable | Default | Purpose |
|---|---|---|
| `DEXTER_GAMES` | `pokemon` | Comma-separated games to load at startup |
| `DEXTER_TOP_K` | `5` | Matches returned per request (best plus alternatives) |
| `DEXTER_MIN_SHARPNESS` | `0.02` | Detector sharpness below which no card is reported; `0` disables |
| `DEXTER_MAX_UPLOAD_BYTES` | `10485760` | Largest accepted upload |
| `DEXTER_NUM_THREADS` | `4` | ONNX Runtime threads per model |
| `DEXTER_PROVIDER` | `auto` | `auto`, `cpu` or `gpu` |
| `DEXTER_CORS_ORIGINS` | empty | Comma-separated browser origins; empty disables CORS |
| `DEXTER_CACHE_DIR` | `~/.cache/collectorvision` | Where models and catalogs are stored |
| `DEXTER_HOST` | `127.0.0.1` | Bind address |
| `DEXTER_PORT` | `8000` | Bind port |

## Adding a game

1. Add the URL name and the CollectorVision game key to `TCG_CATALOGS` in
   [src/dexter/games.py](src/dexter/games.py). The keys CollectorVision
   publishes are listed in its `collector_vision.games.Game` enum.
2. Add the name to `DEXTER_GAMES`.
3. Restart. The catalog downloads on the next start.

Every loaded catalog must use the same embedding model, which is true for all
current CollectorVision catalogs.

## Development

```sh
uv sync                 # creates .venv with dev tools
uv run ruff format .    # format
uv run ruff check .     # lint
uv run mypy             # type check (strict)
uv run pytest           # tests run with fake models, no downloads
```

To update CollectorVision, change the `rev` under `[tool.uv.sources]` in
`pyproject.toml` and run `uv sync`.

## Deployment

[deploy/README.md](deploy/README.md) walks through running DEXter on a
DigitalOcean droplet behind nginx with HTTPS. The same guide is available as
[deploy/DEXter-Deployment-Guide.pdf](deploy/DEXter-Deployment-Guide.pdf).

On a server, run commands as the service user with the folder change inside
the command, for example
`sudo -u dexter -H sh -c 'cd ~/app && ~/.local/bin/uv sync'`, where `-H` makes
`~` the service user's home, `/opt/dexter`.
Otherwise `sudo` keeps root's folder, `/root`, and uv stops with
``failed to open file `/root/uv.toml`: Permission denied``.

## License

DEXter is released under the GNU Affero General Public License v3.0 or later;
see [LICENSE](LICENSE). CollectorVision is AGPL-3.0 licensed as well, and
because DEXter offers it over a network, anyone running a modified DEXter must
make their modified source available to its users.

CollectorVision's Pokemon catalog is marked experimental upstream; expect
occasional misses, and send corrections there.

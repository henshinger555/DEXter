# Deploying DEXter on a DigitalOcean Droplet

This guide takes a fresh Ubuntu 24.04 droplet to a DEXter server answering
`https://dexter.example.com/DEXter/pokemon/identify`. It assumes you can use a
terminal and have a domain whose DNS you control. Replace `dexter.example.com`
with your hostname throughout.

Files in this folder and where they go on the droplet:

| File | Installed as |
|---|---|
| `systemd/dexter.service` | `/etc/systemd/system/dexter.service` |
| `nginx/dexter.conf` | `/etc/nginx/sites-available/dexter` |

## 1. Create the droplet

In the DigitalOcean control panel choose:

- Image: Ubuntu 24.04 LTS
- Size: at least 2 GB RAM. The ONNX models and the Pokemon catalog need about
  1 GB at runtime; 1 GB droplets swap and time out. 2 vCPUs keep identification
  under half a second.
- Authentication: SSH key
- Hostname: `dexter.example.com`

Create an `A` record for `dexter.example.com` pointing at the droplet's IPv4
address (and an `AAAA` record if you enabled IPv6). Wait until
`dig +short dexter.example.com` returns the address before step 7.

## 2. Packages and firewall

Log in as root and install what the rest of the guide needs.

```sh
apt update && apt upgrade -y
apt install -y nginx certbot python3-certbot-nginx git ufw curl
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
```

Expect `ufw status` to list `OpenSSH` and `Nginx Full` as allowed.

## 3. A service user and folders

DEXter runs as an unprivileged user that owns only its code and cache.

```sh
adduser --system --group --home /opt/dexter --shell /usr/sbin/nologin dexter
mkdir -p /var/lib/dexter/cache
chown -R dexter:dexter /opt/dexter /var/lib/dexter
```

## 4. Install uv and Python

`uv` manages the Python version and the virtual environment. Install it for the
service user so the venv is owned by that user.

```sh
sudo -u dexter -H sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo -u dexter -H /opt/dexter/.local/bin/uv python install 3.12
```

Expect the second command to print the installed CPython version.

## 5. The code

```sh
sudo -u dexter -H git clone https://github.com/<your-org>/DEXter.git /opt/dexter/app
cd /opt/dexter/app
sudo -u dexter -H /opt/dexter/.local/bin/uv sync --no-dev
```

`uv sync` creates `/opt/dexter/app/.venv`, installs CollectorVision from GitHub
at the commit pinned in `pyproject.toml`, and installs the `dexter` command. It
takes a minute or two; ONNX Runtime and OpenCV are the large downloads.

## 6. Configuration

```sh
cp /opt/dexter/app/.env.example /opt/dexter/app/.env
chown dexter:dexter /opt/dexter/app/.env
chmod 600 /opt/dexter/app/.env
nano /opt/dexter/app/.env
```

Set at least:

```
DEXTER_GAMES=pokemon
DEXTER_CACHE_DIR=/var/lib/dexter/cache
DEXTER_HOST=127.0.0.1
DEXTER_PORT=8000
DEXTER_CORS_ORIGINS=https://app.example.com
```

`DEXTER_CORS_ORIGINS` lists the browser origins allowed to call the API. Leave
it empty if only servers will call DEXter.

Do a first run by hand so the model and catalog downloads happen where you can
watch them:

```sh
cd /opt/dexter/app
sudo -u dexter -H .venv/bin/dexter
```

Expect a line like `Loaded pokemon CatalogV2(... n=27275) with NeuralEmbedder(...)`
followed by `Uvicorn running on http://127.0.0.1:8000`. Press Ctrl+C.

If the download fails, check that the droplet can reach
`https://huggingface.co` and that `/var/lib/dexter/cache` is writable by
`dexter`.

## 7. The systemd service

The unit file in this folder uses the paths above. If you changed any, edit the
copy before enabling it.

```sh
cp /opt/dexter/app/deploy/systemd/dexter.service /etc/systemd/system/dexter.service
systemctl daemon-reload
systemctl enable --now dexter
systemctl status dexter --no-pager
curl http://127.0.0.1:8000/DEXter/health
```

Expect `active (running)` and `{"status":"ok","games":["pokemon"],...}`.

`TimeoutStartSec=300` in the unit allows for a slow first download; after the
cache is warm the service starts in a few seconds.

Logs: `journalctl -u dexter -f`.

## 8. nginx and HTTPS

nginx terminates TLS and forwards `/DEXter/` to the service. Everything else
returns 404.

```sh
cp /opt/dexter/app/deploy/nginx/dexter.conf /etc/nginx/sites-available/dexter
sed -i 's/dexter.example.com/YOUR-HOSTNAME/' /etc/nginx/sites-available/dexter
ln -s /etc/nginx/sites-available/dexter /etc/nginx/sites-enabled/dexter
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
certbot --nginx -d YOUR-HOSTNAME --agree-tos -m you@example.com --redirect
```

certbot rewrites the site file with the certificate paths and an HTTP to HTTPS
redirect, and installs a timer that renews it. Check with
`certbot renew --dry-run`.

`client_max_body_size 11m` in the nginx file must stay at or above
`DEXTER_MAX_UPLOAD_BYTES`, otherwise nginx answers 413 before DEXter sees the
request.

## 9. Check from outside

From your own machine:

```sh
curl https://YOUR-HOSTNAME/DEXter/health
curl -F "file=@card.jpg" https://YOUR-HOSTNAME/DEXter/pokemon/identify
```

The first returns the health JSON. The second returns `card_present: true` with
a `match` for a clear photo of a Pokemon card on a plain background, or
`card_present: false` with a low `sharpness` if the detector could not find a
card. Interactive docs are at `https://YOUR-HOSTNAME/DEXter/docs`.

## Updating

```sh
cd /opt/dexter/app
sudo -u dexter -H git pull
sudo -u dexter -H /opt/dexter/.local/bin/uv sync --no-dev
systemctl restart dexter
curl http://127.0.0.1:8000/DEXter/health
```

If a release changes the CollectorVision pin, the new catalog downloads on the
next start. To go back, `git checkout <previous-tag>` and run the same three
commands.

Catalogs update themselves: CollectorVision checks its feed on each start and
downloads a newer snapshot when one exists. Restart the service occasionally to
pick up new card printings.

## Adding a game

Edit `/opt/dexter/app/.env`, append the game to `DEXTER_GAMES`
(for example `DEXTER_GAMES=pokemon,pokemon-japan`), and
`systemctl restart dexter`. The game must exist in `src/dexter/games.py`; see the
root README for adding new ones.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `systemctl status dexter` shows `failed` within seconds | A `.env` value is invalid or `DEXTER_GAMES` names an unknown game. `journalctl -u dexter` shows the error. |
| Service hangs in `activating` | First-run download is slow. Wait up to five minutes, or run the manual start from step 6 to see progress. |
| `502 Bad Gateway` from nginx | The service is not listening on `127.0.0.1:8000`. Check `DEXTER_HOST`/`DEXTER_PORT` against the nginx `proxy_pass`. |
| `413` on every upload | `client_max_body_size` in nginx is below the image size. |
| `card_present: false` for real cards | The photo is blurry or the card does not fill enough of the frame. Try `DEXTER_MIN_SHARPNESS=0` to see the raw sharpness value, then pick a threshold. |
| Memory errors in the journal | Droplet has under 2 GB RAM. Resize it, or add swap as a stopgap. |

## Backups

Nothing on the droplet is unique. The code is in git, the models and catalog are
re-downloaded into `DEXTER_CACHE_DIR`, and `.env` is the only file worth copying
somewhere safe.

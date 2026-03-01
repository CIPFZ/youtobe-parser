# Deployment & One-Click Container Update

## 1) Prepare env

```bash
cp .env.example .env
```

Fill required values in `.env` (OpenAI key, proxy, etc.).

## 2) One-click update (recommended)

```bash
COMPOSE_PROFILES=pot bash scripts/update-container.sh
```

The script will:
1. (Optional) login to GHCR if `GHCR_USERNAME` and `GHCR_TOKEN` are provided.
2. Pull latest app image (`ghcr.io/cipfz/youtobe-parser:latest` by default).
3. Recreate app/redis (and pot-provider by default) containers with the pulled image(s).

## 3) Optional env vars

- `APP_IMAGE` (default: `ghcr.io/cipfz/youtobe-parser:latest`)
- `ENV_FILE` (default: `<repo>/.env`)
- `GHCR_USERNAME` / `GHCR_TOKEN` (needed for private GHCR package)
- `COMPOSE_PROFILES` (default: `pot`; set empty to skip bundled pot-provider)

Example:

```bash
GHCR_USERNAME=yourname \
GHCR_TOKEN=ghp_xxx \
APP_IMAGE=ghcr.io/cipfz/youtobe-parser:latest \
COMPOSE_PROFILES=pot \
bash scripts/update-container.sh
```

## 4) Manual compose command (without script)

```bash
APP_IMAGE=ghcr.io/cipfz/youtobe-parser:latest COMPOSE_PROFILES=pot \
docker compose --env-file .env \
  -f docker-compose.yml -f docker-compose.image.yml \
  up -d --pull always --remove-orphans
```


## 5) Optional: enable built-in POT provider

```bash
docker compose --profile pot up -d
```

When profile `pot` is enabled, default `PO_TOKEN_SERVER` can be `http://pot-provider:4416`.


> Troubleshooting: If pot-provider logs `protocol mismatch`, set `POT_PROXY` to a valid **HTTP/HTTPS** proxy or leave it empty.

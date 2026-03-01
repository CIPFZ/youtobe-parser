# Deployment & One-Click Container Update

## 1) Prepare env

```bash
cp .env.example .env
```

Fill required values in `.env` (OpenAI key, proxy, etc.).

## 2) One-click update (recommended)

```bash
bash scripts/update-container.sh
```

The script will:
1. (Optional) login to GHCR if `GHCR_USERNAME` and `GHCR_TOKEN` are provided.
2. Pull latest app image (`ghcr.io/cipfz/youtobe-parser:latest` by default).
3. Recreate app/redis containers with the pulled image.

## 3) Optional env vars

- `APP_IMAGE` (default: `ghcr.io/cipfz/youtobe-parser:latest`)
- `ENV_FILE` (default: `<repo>/.env`)
- `GHCR_USERNAME` / `GHCR_TOKEN` (needed for private GHCR package)

Example:

```bash
GHCR_USERNAME=yourname \
GHCR_TOKEN=ghp_xxx \
APP_IMAGE=ghcr.io/cipfz/youtobe-parser:latest \
bash scripts/update-container.sh
```

## 4) Manual compose command (without script)

```bash
APP_IMAGE=ghcr.io/cipfz/youtobe-parser:latest \
docker compose --env-file .env \
  -f docker-compose.yml -f docker-compose.image.yml \
  up -d --pull always --remove-orphans
```

## CoexistAI — Docker Quickstart

Short, step-by-step instructions for two ways to start CoexistAI. Pick either Method A (direct Docker Compose) or Method B (helper script).

Prerequisites
- Docker Engine and Docker Compose (v2) installed.

Before you start (one-time)
1. Open a terminal and change into the repository folder:

```bash
cd /path/to/CoexistAI
```

2. Copy the example env and set an admin token (required to edit config from the Admin UI):

```bash
cp .env.example .env
# Edit .env and set ADMIN_TOKEN to a secret value
```

Method A — Direct Docker Compose (fast, manual)
1. Start the stack (builds the image the first time):

```bash
docker compose up -d --build
```

2. Wait a minute, then open the admin UI:

- http://localhost:8000/admin

3. Verify status from the host:

```bash
curl http://localhost:8000/status
# expected JSON: {"status":"starting"} or {"status":"ready"}
```

4. Edit configuration:
- Use the Admin UI `/admin` and click "Save & Reload" to apply changes without rebuilding.
- Or from the host (curl):

```bash
curl -X POST -H "X-Admin-Token: $ADMIN_TOKEN" http://localhost:8000/admin/reload-config
```

When to use Method A: you prefer to run compose directly and watch logs yourself.

Method B — Helper script (recommended for beginners)
This script automates the compose start and waits until the app reports ready.

1. Run the helper (from repo root):

```bash
./start_and_wait.sh        # default timeout 300s
./start_and_wait.sh 600    # pass timeout in seconds (example: 600s = 10min)
```

2. What the script does (so you know what to expect):
- Runs: `docker compose up -d --build` to start containers detached.
- Polls `http://localhost:8000/status` every few seconds and prints a spinner.
- Exits with code 0 when the app reports `{"status":"ready"}`.
- Exits non-zero if the app reports `error` or the timeout is reached.

3. After the script finishes successfully, open:

- http://localhost:8000/admin

When to use Method B: you're new to Docker or want a simple way to wait until the app is ready.

Secrets (recommended pattern)
- Do not store API keys in the repo. Use `.env` or file-backed secrets.
- Recommended: create `CoexistAI/config/keys/` on the host, place key files there, and mount that folder into the container. Reference them in `config/model_config.json` with `llm_api_key_file` / `embed_api_key_file`.

Quick troubleshooting
- App unreachable? Check app logs:

```bash
docker compose logs app --tail=200
```

- App timed out in `start_and_wait.sh` or reports `error`? Inspect logs and increase timeout:

```bash
docker compose logs app --tail=400
./start_and_wait.sh 600
```

- Long model downloads or HF errors: allow more time on first start or mount `artifacts/` (HF cache) into the container to avoid repeated downloads.

Helpful commands

```bash
# Check status
curl http://localhost:8000/status

# Ask app to reload config (from host)
curl -X POST -H "X-Admin-Token: $ADMIN_TOKEN" http://localhost:8000/admin/reload-config

# Follow logs interactively
docker compose logs -f app --tail=200
```

Security reminders
- Never commit API keys. Keep `ADMIN_TOKEN` secret and use file-backed secrets for production.

Add-ons
- I can add a small `config/example.model_config.json` and a screenshot if you want a copy-paste example and visual cue.


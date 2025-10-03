#!/usr/bin/env bash
# start_and_wait.sh - start docker compose and wait until CoexistAI app reports ready
# Usage: ./start_and_wait.sh
#!/usr/bin/env bash
# start_and_wait.sh - start docker compose and wait until CoexistAI app reports ready
# Usage: ./start_and_wait.sh
set -euo pipefail
COMPOSE_CMD="docker compose up -d --build"
TIMEOUT=${1:-300}  # seconds to wait (default 300s)
INTERVAL=3

echo "Running: $COMPOSE_CMD"
$COMPOSE_CMD

echo "Started containers (detached). If you want live logs, run:"
echo "  docker compose logs -f app --tail=200"

echo "Waiting for CoexistAI to report ready on http://localhost:8000/status (timeout ${TIMEOUT}s)..."

START=$(date +%s)
while true; do
  if [ $(( $(date +%s) - START )) -ge $TIMEOUT ]; then
    echo "Timed out waiting for app to become ready after ${TIMEOUT}s"
    exit 2
  fi
  # fetch status JSON and extract status field using python for reliable parsing
  status=$(curl -s http://localhost:8000/status || true)
  if [ -n "$status" ]; then
    st=$(printf '%s' "$status" | python3 -c 'import sys,json
try:
    o=json.load(sys.stdin)
    print(o.get("status",""))
except Exception:
    print("")')
    if [ "$st" = "ready" ]; then
      echo "CoexistAI status: ready"
      break
    fi
    if [ "$st" = "error" ]; then
      echo "CoexistAI reported error state. Check logs: docker compose logs app --tail=200"
      exit 3
    fi
  fi
  # simple spinner
  printf '.'
  sleep $INTERVAL
done

echo "Done: app is ready. You can open http://localhost:8000/admin"
exit 0

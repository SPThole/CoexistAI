#!/usr/bin/env bash
# start_and_wait.sh - start docker compose and wait until CoexistAI app reports ready
# Usage: ./start_and_wait.sh
#!/usr/bin/env bash
# start_and_wait.sh - start docker compose and wait until CoexistAI app reports ready
# Usage: ./start_and_wait.sh
set -euo pipefail
if docker image inspect coexistai-app > /dev/null 2>&1; then
    COMPOSE_CMD="docker compose up -d"
else
    COMPOSE_CMD="docker compose up -d --build"
fi
TIMEOUT=${1:-500}  # seconds to wait (default 500s)
INTERVAL=3

echo "Running: $COMPOSE_CMD"
$COMPOSE_CMD

echo ""
echo "Started containers (detached). Streaming logs from app container..."
echo "==============================================================================="

# Start streaming logs in the background and to stdout
docker compose logs -f app 2>&1 &
LOGS_PID=$!

# Give logs a moment to start
sleep 0.5

echo "Waiting for CoexistAI to report ready on http://localhost:8000/status (timeout ${TIMEOUT}s)..."
echo ""

START=$(date +%s)
while true; do
  if [ $(( $(date +%s) - START )) -ge $TIMEOUT ]; then
    kill $LOGS_PID 2>/dev/null || true
    wait $LOGS_PID 2>/dev/null || true
    echo ""
    echo "==============================================================================="
    echo "ERROR: Timed out waiting for app to become ready after ${TIMEOUT}s"
    echo "Check full logs with: docker compose logs app --tail=500"
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
      kill $LOGS_PID 2>/dev/null || true
      wait $LOGS_PID 2>/dev/null || true
      echo ""
      echo "==============================================================================="
      echo "✓ CoexistAI status: READY"
      echo "==============================================================================="
      break
    fi
    if [ "$st" = "error" ]; then
      kill $LOGS_PID 2>/dev/null || true
      wait $LOGS_PID 2>/dev/null || true
      echo ""
      echo "==============================================================================="
      echo "ERROR: CoexistAI reported error state"
      echo "Check logs with: docker compose logs app --tail=200"
      echo "==============================================================================="
      exit 3
    fi
  fi
  sleep $INTERVAL
done

echo ""
echo "Done: app is ready."
echo "Access the admin panel to configure models:"
echo "  http://localhost:8000/admin"
echo "Default ADMIN_TOKEN is 123456 (changeable in .env)"
echo "==============================================================================="
exit 0

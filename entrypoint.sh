#!/bin/sh
set -e

# Load environment variables from /app/.env if present
if [ -f "/app/.env" ]; then
  export $(grep -v '^#' /app/.env | xargs)
fi

echo "Starting CoexistAI (in container)"

# Ensure searxng is running is handled by docker-compose service; start app
PORT_NUM_APP=${PORT_NUM_APP:-8000}
HOST_APP=${HOST_APP:-0.0.0.0}

# If model_config.py exists in mounted volume it will override the packaged one
echo "Using model_config from $(pwd)/model_config.py"

# Check for wget or curl for downloads
if command -v wget &> /dev/null; then
  DOWNLOADER_CMD="wget"
  DOWNLOADER_ARGS="-O"
elif command -v curl &> /dev/null; then
  DOWNLOADER_CMD="curl"
  DOWNLOADER_ARGS="-L -o"
else
  echo "Neither wget nor curl could be found in container. Please install one."
  exit 1
fi

# Download large model assets if not present (mirror quick_setup.sh behaviour)
if [ ! -f kokoro-v1.0.onnx ]; then
  echo "Downloading kokoro-v1.0.onnx..."
  $DOWNLOADER_CMD $DOWNLOADER_ARGS kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx || true
else
  echo "kokoro-v1.0.onnx already exists, skipping download."
fi

if [ ! -f voices-v1.0.bin ]; then
  echo "Downloading voices-v1.0.bin..."
  $DOWNLOADER_CMD $DOWNLOADER_ARGS voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin || true
else
  echo "voices-v1.0.bin already exists, skipping download."
fi

# Run the app using the coexistaienv python (mirrors quick_setup.sh flow)
# Ensure HOST_APP is 0.0.0.0 inside container so the service is reachable from the host
if [ "${HOST_APP}" = "127.0.0.1" ] || [ "${HOST_APP}" = "localhost" ]; then
  echo "HOST_APP was set to ${HOST_APP}; overriding to 0.0.0.0 so the container listens on all interfaces"
  HOST_APP=0.0.0.0
fi

# Export so subprocesses (uvicorn/python) inherit the values
export HOST_APP
export PORT_NUM_APP

if [ -f /opt/coexistaienv/bin/activate ]; then
  echo "Activating coexistaienv and launching uvicorn (binding to 0.0.0.0 port=${PORT_NUM_APP})"
  # Run without --reload in container to avoid the reloader binding to localhost and resetting connections
  exec /opt/coexistaienv/bin/python -m uvicorn app:app --host 0.0.0.0 --port ${PORT_NUM_APP}
else
  echo "coexistaienv not found, falling back to system python"
  # Fallback: run without --reload in container
  exec uvicorn app:app --host 0.0.0.0 --port ${PORT_NUM_APP}
fi


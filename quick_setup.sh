#!/bin/zsh
# Quick Shell Setup for CoexistAI (macOS/zsh)

echo "Pulling SearxNG Docker image..."
docker pull searxng/searxng

echo "📚 Installing infinity_emb in separate environment..."
echo "Creating and activating Python virtual environment..."
python3.12 -m venv infinity_env
source infinity_env/bin/activate
pip install 'infinity_emb[all]'
pip install --upgrade "transformers<4.49"
pip install --upgrade "typer==0.19.1" "click>=8.1.3" "optimum==1.27.0"
deactivate
echo "✅ Infinity environment setup complete"

# (Optional) Create and activate a Python virtual environment
echo "Creating and activating Python virtual environment..."
python3.12 -m venv coexistaienv
source coexistaienv/bin/activate

pip install 'markitdown[all]'

# You can neglect this if you dont want to use google models (either llm or embedding)
echo "Setting GOOGLE_API_KEY, add any other keys which you want to store in environment (edit this script to use your real key)"
export GOOGLE_API_KEY=REPLACE_YOUR_API_KEY_HERE_WITHOUT_QUOTES_AND_SPACES


# Spin up the SearxNG Docker container
echo "Starting SearxNG Docker container..."
PORT_NUM_SEARXNG=$(python3.12 -c "from model_config import PORT_NUM_SEARXNG; print(PORT_NUM_SEARXNG)")
HOST_SEARXNG=$(python3.12 -c "from model_config import HOST_SEARXNG; print(HOST_SEARXNG)")

# Stop and remove existing searxng container if it exists
if [ "$(docker ps -aq -f name=searxng)" ]; then
  echo "Stopping and removing existing SearxNG container..."
  docker stop searxng 2>/dev/null || true
  docker rm searxng 2>/dev/null || true
fi

# Start new SearxNG container
docker run -d \
  --name searxng \
  -p ${PORT_NUM_SEARXNG}:8080 \
  -v $(pwd)/searxng:/etc/searxng:rw \
  -e SEARXNG_BASE_URL=http://${HOST_SEARXNG}:${PORT_NUM_SEARXNG}/ \
  -e SEARXNG_PORT=${PORT_NUM_SEARXNG} \
  -e SEARXNG_BIND_ADDRESS=${HOST_SEARXNG} \
  --restart unless-stopped \
  searxng/searxng:latest

echo "SearxNG container started successfully!"

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r ./requirements.txt

# Adding tts files
# Check if wget is installed
# Check if wget or curl is installed
if command -v wget &> /dev/null; then
  DOWNLOADER_CMD="wget"
  DOWNLOADER_ARGS="-O"
elif command -v curl &> /dev/null; then
  DOWNLOADER_CMD="curl"
  DOWNLOADER_ARGS="-L -o"
else
  echo "Neither wget nor curl could be found, please install one to continue."
  exit 1
fi

# Download kokoro-v1.0.onnx if not present
if [ ! -f kokoro-v1.0.onnx ]; then
  $DOWNLOADER_CMD $DOWNLOADER_ARGS kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
else
  echo "kokoro-v1.0.onnx already exists, skipping download."
fi

# Download voices-v1.0.bin if not present
if [ ! -f voices-v1.0.bin ]; then
  $DOWNLOADER_CMD $DOWNLOADER_ARGS voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
else
  echo "voices-v1.0.bin already exists, skipping download."
fi


# 8. Start the FastAPI app
echo "Starting FastAPI app..."
cd . || exit 1
# Get port and host values from model_config
PORT_NUM_APP=$(python3.12 -c "from model_config import PORT_NUM_APP; print(PORT_NUM_APP)")
HOST_APP=$(python3.12 -c "from model_config import HOST_APP; print(HOST_APP)")
uvicorn app:app --host ${HOST_APP} --port ${PORT_NUM_APP} --reload --reload-include '*.json'

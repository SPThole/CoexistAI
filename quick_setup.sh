#!/bin/sh
# Quick Shell Setup for CoexistAI (linux/sh)

# Install infinity in its own virtual environment
echo "📚 Installing infinity_emb in separate environment..."

echo "Remove old infinity virtual environment"
rm -rf infinity_env

echo "Creating infinity virtual environment"
python3 -m venv infinity_env

echo "Activating infinity virtual environment"
if [ -d infinity_env/Scripts ]; then
  ENV_DIR=infinity_env/Scripts
else
  ENV_DIR=infinity_env/bin
fi
source $ENV_DIR/activate
if [ $? -ne 0 ]; then
    echo "Error activating infinity environment"
	return 1
fi

echo "Installing infinity"
python3 -m pip install 'infinity_emb[all]'
if [ $? -ne 0 ]; then
    echo "Error installing infinity in the environment"
	return 1
fi
python -m pip install --upgrade "transformers<4.49"
python -m pip install --upgrade "typer==0.19.1" "click>=8.1.3"

echo "Deactivating infinity virtual environment"
deactivate
echo "✅ Infinity environment setup complete"

# (Optional) Create and activate a Python virtual environment
echo "Remove old coexistai environment"
rm -rf coexistaienv

echo "Creating coexistai virtual environment..."
python -m venv coexistaienv

echo "Activating coexistai virtual environment"
if [ -d coexistaienv/Scripts ]; then
  ENV_DIR=coexistaienv/Scripts
else
  ENV_DIR=coexistaienv/bin
fi
source $ENV_DIR/activate
if [ $? -ne 0 ]; then
    echo "Error activating coexistai virtual environment"
	return 1
fi

# Install Python dependencies
echo "Installing Python dependencies in coexistai virtual environment"
python -m pip install -r ./requirements.txt

# Installing SearXNG
START_SEARXNG=$(python -c "from model_config import START_SEARXNG; print(START_SEARXNG)")
if [ $START_SEARXNG == 0 ]; then
  echo "Skipping SearxNG startup as per configuration"
elif [ $START_SEARXNG == 1 ]; then
	echo "Pulling SearxNG Docker image..."
	docker pull searxng/searxng
else
    echo "Invalid value for START_SEARXNG in model_config.py. Use 0 or 1."
    exit 1
fi

# Deactivate coexistai virtual environment
echo "Deactivating coexistai virtual environment"
deactivate

# Adding tts files
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

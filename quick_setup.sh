#!/bin/zsh
# Quick Shell Setup for CoexistAI (macOS/zsh)

echo "Pulling SearxNG Docker image..."
docker pull searxng/searxng

# (Optional) Create and activate a Python virtual environment
echo "Creating and activating Python virtual environment..."
python3.13 -m venv coexistaienv
source coexistaienv/bin/activate

pip install 'markitdown[all]'

echo "Setting GOOGLE_API_KEY (edit this script to use your real key)"
export GOOGLE_API_KEY=REPLACE_YOUR_API_KEY_HERE_WITHOUT_QUOTES_AND_SPACES

# Spin up the SearxNG Docker container
echo "Starting SearxNG Docker container..."
docker run --rm -d -p 30:8080 \
  -v $(pwd)/searxng:/etc/searxng \
  -e BASE_URL=http://localhost:30/ \
  -e INSTANCE_NAME=my-instance \
  searxng/searxng

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r ./requirements.txt

# 8. Start the FastAPI app
echo "Starting FastAPI app..."
cd . || exit 1
uvicorn app:app --reload

#!/bin/zsh

echo "Pulling SearxNG Docker image..."
docker pull searxng/searxng


echo "Cloning repository..."
git clone https://github.com/SPThole/CoexistAI.git coexistai
cd coexistai || exit 1

# 3. Use the searxng folder from the repo (do NOT overwrite it)
echo "Using searxng folder from the repo (not overwriting)"


# 6. (Optional) Create and activate a Python virtual environment
echo "Creating and activating Python virtual environment..."
python3 -m venv coexistaienv
source coexistaienv/bin/activate

echo "Setting GOOGLE_API_KEY (edit this script to use your real key)"
export GOOGLE_API_KEY=REPLACE_YOUR_API_KEY_HERE_WITHOUT_QUOTES_AND_SPACES

# 5. Spin up the SearxNG Docker container
echo "Starting SearxNG Docker container..."
docker run --rm -d -p 30:8080 \
  -v $(pwd)/searxng:/etc/searxng \
  -e BASE_URL=http://localhost:30/ \
  -e INSTANCE_NAME=my-instance \
  searxng/searxng

# 7. Install Python dependencies
echo "Installing Python dependencies..."
pip install -r ./requirements.txt

# 8. Start the FastAPI app
echo "Starting FastAPI app..."
cd . || exit 1
uvicorn app:app --reload

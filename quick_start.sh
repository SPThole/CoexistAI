#!/bin/sh
# Quick Shell Startup for CoexistAI (linux/sh)

# For Git bash run
#export PATH=$(pwd)/infinity_env/Scripts:$PATH

# (Optional) Activate a Python virtual environment
echo "Activating Python virtual environment..."
if [ -d coexistaienv/Scripts ]; then
  ENV_DIR=coexistaienv/Scripts
else
  ENV_DIR=coexistaienv/bin
fi
source $ENV_DIR/activate
if [ $? -ne 0 ]; then
    echo "Error activating coexistai environment"
	return 1
fi

# You can neglect this if you dont want to use google models (either llm or embedding)
echo "Setting GOOGLE_API_KEY, add any other keys which you want to store in environment (edit this script to use your real key)"
export GOOGLE_API_KEY=REPLACE_YOUR_API_KEY_HERE_WITHOUT_QUOTES_AND_SPACES

# Spin up the SearxNG Docker container
START_SEARXNG=$(python -c "from model_config import START_SEARXNG; print(START_SEARXNG)")
if [ $START_SEARXNG == 0 ]; then
  echo "Skipping SearxNG startup as per configuration"
elif [ $START_SEARXNG == 1 ]; then
  echo "Starting SearxNG Docker container..."
  PORT_NUM_SEARXNG=$(python -c "from model_config import PORT_NUM_SEARXNG; print(PORT_NUM_SEARXNG)")
  HOST_SEARXNG=$(python -c "from model_config import HOST_SEARXNG; print(HOST_SEARXNG)")

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
else
    echo "Invalid value for START_SEARXNG in model_config.py. Use 0 or 1."
    exit 1
fi

# Start the FastAPI app
echo "Starting FastAPI app..."
cd . || exit 1
# Get port and host values from model_config
PORT_NUM_APP=$(python -c "from model_config import PORT_NUM_APP; print(PORT_NUM_APP)")
HOST_APP=$(python -c "from model_config import HOST_APP; print(HOST_APP)")
python -m uvicorn app:app --host ${HOST_APP} --port ${PORT_NUM_APP} --reload

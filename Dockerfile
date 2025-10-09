FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Build-time args that will be copied into the image as environment variables.
# Users can pass these via `docker build --build-arg KEY=VALUE` to bake defaults.
ARG LLM_MODEL_NAME=gemini-2.0-flash
ARG LLM_TYPE=google
ARG LLM_TEMPERATURE=0.1
ARG PORT_NUM_APP=8000
ARG PORT_NUM_SEARXNG=8085
ARG HOST_APP=0.0.0.0
ARG HOST_SEARXNG=0.0.0.0
ARG EMBED_MODE=google
ARG EMBEDDING_MODEL_NAME=models/embedding-001

# Export non-secret build args as environment variables so model_config.py can read them at runtime
ENV LLM_MODEL_NAME=${LLM_MODEL_NAME}
ENV LLM_TYPE=${LLM_TYPE}
ENV LLM_TEMPERATURE=${LLM_TEMPERATURE}
ENV PORT_NUM_APP=${PORT_NUM_APP}
ENV PORT_NUM_SEARXNG=${PORT_NUM_SEARXNG}
ENV HOST_APP=${HOST_APP}
ENV HOST_SEARXNG=${HOST_SEARXNG}
ENV EMBED_MODE=${EMBED_MODE}
ENV EMBEDDING_MODEL_NAME=${EMBEDDING_MODEL_NAME}

# Install small set of system deps commonly needed by ML/audio packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        wget \
        ffmpeg \
        build-essential \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*


# Use /app as the workdir so the Dockerfile can be built from the CoexistAI folder
WORKDIR /app

# Copy only requirements first to leverage Docker cache (build context is the CoexistAI folder)
COPY ./requirements.txt ./requirements.txt

RUN python -m pip install --upgrade pip setuptools wheel

# Copy application code (copy the current folder contents into /app)
COPY ./ ./

# Reproduce quick_setup.sh virtualenv installs inside the image (mirrors the script)
# Create a separate infinity_env and install packages there to avoid conflicts as in the script
RUN python3.13 -m venv /opt/infinity_env && \
    /opt/infinity_env/bin/pip install --no-cache-dir 'infinity-emb[all]' && \
    /opt/infinity_env/bin/pip install --no-cache-dir 'optimum==1.27.0' && \
    /opt/infinity_env/bin/pip install --no-cache-dir 'transformers<4.49' && \
    /opt/infinity_env/bin/pip install --no-cache-dir --upgrade "typer==0.19.1" "click>=8.1.3" || true

# Create a second venv similar to coexistaienv and install markitdown[all]
RUN python3.13 -m venv /opt/coexistaienv && \
    /opt/coexistaienv/bin/pip install --no-cache-dir 'markitdown[all]' || true

# Now install the project requirements into the coexistaienv (matches quick_setup.sh order)
RUN /opt/coexistaienv/bin/pip install --no-cache-dir -r requirements.txt || true

# Entrypoint will be executed via shell; no need to force executable bit when host may mount files

EXPOSE 8000

# Invoke the entrypoint from the copied project path. The entrypoint lives at CoexistAI/entrypoint.sh
CMD ["sh", "/app/entrypoint.sh"]

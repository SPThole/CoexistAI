import os
import json
"""
This module defines the configuration for language model (LLM) and embedding models.
Attributes:
    api_key (str): The OpenAI API key, loaded from the environment variable 'OPENAI_API_KEY'.
    model_config (dict): A dictionary containing configuration parameters for LLM and embedding models.
        Keys:
            - "llm_model_name" (str): Name of the LLM model to use.
            - "llm_type" (str): Type of the LLM provider (e.g., "openai"). "local" is for lmstudio, 
            for ollama and other local models use "others" with base_url updated in openai_compatible.
            - If you using others llm type, then check the openai_compatible url dict for others key, you can generally 
            find it by "googling YOUR provider name openai api base compatilble url"
            - "llm_base_url" (str): Base URL for the LLM API endpoint.
            - "llm_tools" (list): List of tools or plugins to use with the LLM.
            - "llm_kwargs" (dict): Additional keyword arguments for LLM initialization.
                - "temperature" (float): Sampling temperature for generation.
                - "max_tokens" (int or None): Maximum number of tokens to generate.
                - "timeout" (int or None): Timeout for API requests.
                - "max_retries" (int): Maximum number of retries for failed requests.
                - "api_key" (str): API key for authentication.
            - "embedding_model_name" (str): Name of the embedding model to use.
            - "embed_mode" (str): Embedding mode or backend.
            - "cross_encoder_name" (str): Name of the cross-encoder model for reranking.
"""
############## PORT and HOST SETTINGS (can be overridden via env vars)
DEFAULT_PORT_NUM_SEARXNG = 8080
DEFAULT_PORT_NUM_APP = 8000
DEFAULT_HOST_APP = "host.docker.internal" # Use host.docker.internal for Docker on Mac/Windows else localhost
DEFAULT_HOST_SEARXNG = "searxng" # Use container hostname in Docker if running docker else localhost

# Allow runtime or build-time overrides via environment variables
PORT_NUM_SEARXNG = int(os.environ.get('PORT_NUM_SEARXNG', DEFAULT_PORT_NUM_SEARXNG))
PORT_NUM_APP = int(os.environ.get('PORT_NUM_APP', DEFAULT_PORT_NUM_APP))
HOST_APP = os.environ.get('HOST_APP', DEFAULT_HOST_APP)
HOST_SEARXNG = os.environ.get('HOST_SEARXNG', DEFAULT_HOST_SEARXNG)

###############

# API keys: prefer provider-specific vars, fall back to the old GOOGLE_API_KEY for compatibility
llm_api_key = os.environ.get('LLM_API_KEY', os.environ.get('GOOGLE_API_KEY', 'DUMMY'))
embed_api_key = os.environ.get('EMBED_API_KEY', os.environ.get('GOOGLE_API_KEY', 'DUMMY'))

# Build the model_config dict but read values from env when provided. This lets users
# override defaults using Docker build-args (baked into image via ENV) or runtime -e flags.
def _env_bool(key, default=False):
    v = os.environ.get(key)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "y")

def _env_json(key, default=None):
    v = os.environ.get(key)
    if not v:
        return default
    try:
        return json.loads(v)
    except Exception:
        return default

model_config = {
    "llm_model_name": os.environ.get('LLM_MODEL_NAME', 'gemini-2.0-flash'),
    "llm_type": os.environ.get('LLM_TYPE', 'google'),
    "llm_tools": _env_json('LLM_TOOLS', None),
    "llm_kwargs": {
        "temperature": float(os.environ.get('LLM_TEMPERATURE', 0.1)),
        "max_tokens": None if os.environ.get('LLM_MAX_TOKENS') is None else int(os.environ.get('LLM_MAX_TOKENS')),
        "timeout": None if os.environ.get('LLM_TIMEOUT') is None else int(os.environ.get('LLM_TIMEOUT')),
        "max_retries": int(os.environ.get('LLM_MAX_RETRIES', 2)),
        "api_key": llm_api_key,
    },
    "embedding_model_name": os.environ.get('EMBEDDING_MODEL_NAME', 'models/embedding-001'),
    "embed_kwargs": _env_json('EMBED_KWARGS', {"google_api_key": embed_api_key}),
    "embed_mode": os.environ.get('EMBED_MODE', 'google'),
    "cross_encoder_name": os.environ.get('CROSS_ENCODER_NAME', 'BAAI/bge-reranker-base')
}


# Runtime file-backed config support
CONFIG_PATH = os.environ.get('CONFIG_PATH', os.path.join(os.path.dirname(__file__), 'config', 'model_config.json'))


def _load_config_file(path):
    """Load overrides from a JSON config file and apply into module globals/model_config.
    Expected keys: llm_model_name, llm_type, llm_tools, llm_kwargs (dict), embedding_model_name,
    embed_mode, embed_kwargs, cross_encoder_name, llm_api_key, embed_api_key, or *_file entries
    pointing to files that contain the secret values.
    """
    try:
        with open(path, 'r') as f:
            cfg = json.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to read config file {path}: {e}")

    # secrets: direct or file-backed
    if 'llm_api_key' in cfg:
        globals()['llm_api_key'] = cfg['llm_api_key']
    elif 'llm_api_key_file' in cfg:
        try:
            with open(cfg['llm_api_key_file'], 'r') as kf:
                globals()['llm_api_key'] = kf.read().strip()
        except Exception:
            pass

    if 'embed_api_key' in cfg:
        globals()['embed_api_key'] = cfg['embed_api_key']
    elif 'embed_api_key_file' in cfg:
        try:
            with open(cfg['embed_api_key_file'], 'r') as kf:
                globals()['embed_api_key'] = kf.read().strip()
        except Exception:
            pass

    # top-level simple fields
    for key in ('llm_model_name', 'llm_type', 'llm_tools', 'embedding_model_name', 'embed_mode', 'cross_encoder_name'):
        if key in cfg:
            model_config[key] = cfg[key]

    # allow overriding openai_compatible mapping
    if 'openai_compatible' in cfg and isinstance(cfg['openai_compatible'], dict):
        # update or create the mapping
        try:
            globals()['openai_compatible'].update(cfg['openai_compatible'])
        except Exception:
            globals()['openai_compatible'] = cfg['openai_compatible']

    # allow overriding default host/port values
    for k in ('DEFAULT_HOST_APP', 'DEFAULT_PORT_NUM_APP', 'DEFAULT_HOST_SEARXNG', 'DEFAULT_PORT_NUM_SEARXNG'):
        if k in cfg:
            globals()[k] = cfg[k]

    # allow runtime host/port overrides in config file
    for k in ('HOST_APP', 'PORT_NUM_APP', 'HOST_SEARXNG', 'PORT_NUM_SEARXNG'):
        if k in cfg:
            # coerce numeric ports to int
            if 'PORT' in k:
                try:
                    val = int(cfg[k])
                except Exception:
                    val = globals().get(k)
            else:
                val = cfg[k]
            globals()[k] = val

    # dict fields to merge
    if 'llm_kwargs' in cfg and isinstance(cfg['llm_kwargs'], dict):
        model_config.setdefault('llm_kwargs', {}).update(cfg['llm_kwargs'])
    if 'embed_kwargs' in cfg and isinstance(cfg['embed_kwargs'], dict):
        model_config.setdefault('embed_kwargs', {}).update(cfg['embed_kwargs'])

    # ensure api keys are set into llm/embed kwargs
    model_config.setdefault('llm_kwargs', {})['api_key'] = globals().get('llm_api_key', model_config['llm_kwargs'].get('api_key'))
    model_config.setdefault('embed_kwargs', {})
    if 'google_api_key' not in model_config['embed_kwargs']:
        model_config['embed_kwargs']['google_api_key'] = globals().get('embed_api_key', model_config['embed_kwargs'].get('google_api_key'))

    return model_config


def reload_model_config(path=None):
    """Reload configuration from JSON file. If path is None, uses CONFIG_PATH env var or default.
    Raises RuntimeError if load fails.
    """
    p = path or os.environ.get('CONFIG_PATH') or CONFIG_PATH
    if not p or not os.path.exists(p):
        raise FileNotFoundError(f"Config path not found: {p}")
    return _load_config_file(p)


# Try to load config at import time if present; this is non-fatal.
try:
    if os.path.exists(CONFIG_PATH):
        _load_config_file(CONFIG_PATH)
except Exception:
    # ignore errors during import; admin endpoints or manual reload can show issues
    pass


# NO CHANGE NEEDED UNLESS PROVIDER CHANGES THE BASE URLS, OR YOU WANT TO USE DIFFERENT PROVIDER UNDER "others"
openai_compatible = {
    'google': "https://generativelanguage.googleapis.com/v1beta/openai/",
    'local': "http://127.0.0.1:1234/v1",
    'groq': 'https://api.groq.com/openai/v1',
    'openai':'https://api.openai.com/v1',
    'others': 'https://openrouter.ai/api/v1' # for an example I have added here the openrouter api, since its openai compatible
}

#####IF YOU WANT TO GO ALL LOCAL 

# model_config = {
#     # Name of the LLM model to use. For local models, use the model name served by your local server.
#     "llm_model_name": "google/gemma-3-12b",

#     # LLM provider type: choose from 'google', 'local', 'groq', or 'openai' or 'others' 
#     # in case of 'others' (base url needs to be updated in openai_compatible given below accordingly).
#     # Make sure to update the api_key variable above to match the provider.
#     "llm_type": "local", 

#     # List of tools or plugins to use with the LLM, if any. Set to None if not used.
#     "llm_tools": None,

#     # Additional keyword arguments for LLM initialization.
#     "llm_kwargs": {
#         "temperature": 0.1,  # Sampling temperature for generation.
#         "max_tokens": None,  # Maximum number of tokens to generate (None for default).
#         "timeout": None,     # Timeout for API requests (None for default).
#         "max_retries": 2,    # Maximum number of retries for failed requests.
#         "api_key": llm_api_key,  # API key for authentication.
#     },

#     # Name of the embedding model to use.
#     # For Google, use their embedding model names. For local/HuggingFace, use the model path or name.
#     "embedding_model_name": "nomic-ai/nomic-embed-text-v1",

#     "embed_kwargs":{}, #additional kwargs for embedding model initialization

#     # Embedding backend: 'google' for Google, 'infinity_emb' for local/HuggingFace models.
#     "embed_mode": "infinity_emb",

#     # Name of the cross-encoder model for reranking, typically a HuggingFace model.
#     "cross_encoder_name": "BAAI/bge-reranker-base"
# }
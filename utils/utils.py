"""
utils_langchain.py
Author: Sidhant Thole
Created: 25 May 2025
Description: Utility functions for LangChain-based applications, including model loading, session state, markdown/table extraction, email sending, and more.
"""

# Standard library imports
import os
import re
import time
import datetime
import smtplib
import logging
import subprocess

# Third-party imports
import requests
import streamlit as st
from rich import print
from markdownify import markdownify as md

# Langchain and related imports
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_community.embeddings import InfinityEmbeddings
from langchain.docstore.document import Document

# Project imports
from utils.config import *

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

os.environ["GOOGLE_API_KEY"] = os.environ.get("GOOGLE_API_KEY", "")

def set_logging(enabled: bool):
    """
    Enable or disable logger output at runtime, including in Jupyter notebooks and all modules.
    Args:
        enabled (bool): If True, set logger to INFO. If False, silence logger.
    """
    import logging
    level = logging.INFO if enabled else logging.CRITICAL
    # Set all existing loggers' levels and remove handlers
    for name, logger in logging.root.manager.loggerDict.items():
        if isinstance(logger, logging.Logger):
            logger.setLevel(level)
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            if enabled and not logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
                handler.setFormatter(formatter)
                logger.addHandler(handler)
    # Set root logger level and handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    if enabled:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

def is_searxng_running():
       result = subprocess.run(
              ["docker", "ps", "--filter", "ancestor=searxng/searxng", "--format", "{{.ID}}"],
              stdout=subprocess.PIPE,
              stderr=subprocess.PIPE,
              text=True
       )
       return bool(result.stdout.strip())
   
def fix_json(json_str):
    """
    Attempts to fix a malformed JSON string by removing trailing commas and correcting common issues.
    Args:
        json_str (str): A potentially malformed JSON string.

    Returns:
        str: The fixed JSON string.
    """
    logger.debug("Fixing JSON string.")
    # Remove trailing commas before } or ]
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
    # Replace single quotes with double quotes
    json_str = re.sub(r"'", '"', json_str)
    # Remove newlines and excessive whitespace
    json_str = re.sub(r'\s+', ' ', json_str)
    # Optionally, add more fixes as needed
    return json_str

def load_model(model_name, 
               _embed_mode='infinity_emb', 
               cross_encoder_name="BAAI/bge-reranker-base",
               kwargs=None):
    """
    Loads the appropriate embeddings and cross-encoder model based on the embedding mode.
    TODO: Validate model and handle errors for unsupported modes.
    Args:
        model_name (str): The name of the Hugging Face or Google embedding model.
        _embed_mode (str, optional): The embedding mode ('infinity_emb', 'huggingface', 'google'). Defaults to 'infinity_emb'.
        cross_encoder_name (str, optional): The name of the cross-encoder model to use. Defaults to "BAAI/bge-reranker-base".

    Returns:
        tuple: The selected embedding model and cross-encoder.
    """
    logger.info(f"Loading model: {model_name} with embedding mode: {_embed_mode}")
    supported_modes = ['infinity_emb', 'huggingface', 'google']
    if _embed_mode not in supported_modes:
        logger.error(f"Unsupported embedding mode: {_embed_mode}")
        raise ValueError(f"Unsupported embedding mode: {_embed_mode}. Supported modes: {supported_modes}")

    hf_embeddings = None
    if _embed_mode == 'infinity_emb':
        infinity_api_url = "http://0.0.0.0:7997"
        # Check if the Infinity API server is running
        try:
            response = requests.get(f"{infinity_api_url}/health", timeout=2)
            if response.status_code != 200:
                raise Exception("Infinity API health check failed")
        except Exception:
            logger.info("Infinity API not running. Attempting to start it...")
            try:
                subprocess.Popen(
                    ["infinity_emb", "v2", "--model-id", model_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                # Wait a few seconds for the server to start
                time.sleep(10)
                # Check again if the Infinity API server is running after attempting to start it
                try:
                    response = requests.get(f"{infinity_api_url}/health", timeout=2)
                    if response.status_code != 200:
                        raise Exception("Infinity API health check failed after start attempt")
                except Exception:
                    logger.error("Infinity API still not running after start attempt.")
                    raise RuntimeError("Infinity API failed to start or is not reachable at http://0.0.0.0:7997")
            except Exception as e:
                logger.error(f"Failed to start Infinity API: {e}")
                raise RuntimeError(f"Failed to start Infinity API: {e}")
        try:
            hf_embeddings = InfinityEmbeddings(
                model=model_name, infinity_api_url=infinity_api_url
            )
        except Exception as e:
            logger.error(f"Failed to load InfinityEmbeddings: {e}")
            raise RuntimeError(f"Failed to load InfinityEmbeddings: {e}, please first start the server using infinity_emb v2 --model-id (https://github.com/michaelfeil/infinity)")
    elif _embed_mode == 'huggingface':
        try:
            extra_kwargs = {'trust_remote_code': True}
            hf_embeddings = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={**extra_kwargs, **kwargs} if kwargs else extra_kwargs
            )
        except Exception as e:
            logger.error(f"Failed to load HuggingFaceEmbeddings: {e}")
            raise RuntimeError(f"Failed to load HuggingFaceEmbeddings: {e}")
    elif _embed_mode == 'google':
        try:
            hf_embeddings = GoogleGenerativeAIEmbeddings(model=model_name, 
                                                         task_type="retrieval_query",
                                                         **kwargs)
        except Exception as e:
            logger.error(f"Failed to load GoogleGenerativeAIEmbeddings: {e}")
            raise RuntimeError(f"Failed to load GoogleGenerativeAIEmbeddings: {e}")

    try:
        cross_encoder = HuggingFaceCrossEncoder(model_name=cross_encoder_name, **kwargs)
    except Exception as e:
        logger.error(f"Failed to load HuggingFaceCrossEncoder: {e}")
        raise RuntimeError(f"Failed to load HuggingFaceCrossEncoder: {e}")

    if hf_embeddings is None:
        logger.error("Failed to initialize embeddings.")
    return hf_embeddings, cross_encoder

def stream_text_1(placeholder, output):
    """
    Similar to `stream_text`, but streams text line-by-line with a faster streaming speed.

    Args:
        placeholder (Streamlit object): A placeholder for rendering the streamed content.
        output (iterable): An iterable containing text to be streamed.
    """
    current_text = ""
    for line in output:
        current_text += line
        placeholder.markdown(current_text, unsafe_allow_html=True)
        time.sleep(0.01)  # Simulate streaming

def stream_answer(text):
    """
    Streams text word-by-word with a short delay between each word for a dynamic output experience.

    Args:
        text (str): The text content to stream.
    """
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.02)

def get_local_data():
    """
    Retrieves the current date and the name of the current weekday.

    Returns:
        tuple: The current date as a string and the current weekday as a string.
    """
    date = str(datetime.datetime.today().date())
    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thrusday', 'Friday', 'Saturday']
    day = datetime.datetime.today().weekday()
    day = days[day]
    return date, day

def get_generative_model(model_name='gemini-1.5-flash',
                        type='google',
                        base_url='http://localhost:11434/v1',
                        _tools=None,
                        kwargs=None):
    """
    Initializes and returns a generative language model based on the specified type.
    Args:
        model_name (str): The name of the model to use (default is 'gemini-1.5-flash').
        type (str): The type of model to initialize ('google','local','groq','openai','others'). 
                    For others add openai compatible api base url in the model_config.py file.
        base_url (str): The base URL for the local model if type is 'local'.
        _tools (list, optional): A list of tools to bind to the model.
        kwargs (dict, optional): Additional keyword arguments for model initialization.
    Returns:
        llm: An instance of the generative language model.
    """
    if kwargs is None:
        kwargs = {}
    if type == 'google':
        extra_kwargs = {'generation_config': {"response_mime_type": "application/json"}}
        kwargs = {**kwargs, **extra_kwargs}
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            **kwargs,
        )
    elif type == 'local':
        llm = ChatOpenAI(
            base_url=base_url,
            model=model_name,
            **kwargs
        )
    elif type == 'groq':
        from langchain_groq import ChatGroq
        llm = ChatGroq(
            model=model_name,
            **kwargs
            # other params...
        )
    elif type == 'openai':
        llm = ChatOpenAI(
            model=model_name,
            **kwargs
        )
    elif type == 'others':
        llm = ChatOpenAI(
            model=model_name,
            **kwargs
        )
    if _tools:
        llm.bind_tools(_tools)
    return llm

def log_results(query, context, date, day):
    """
    Logs search queries and the generated context to a local file for later reference.
    TODO: Sanitize sensitive data before logging and add log rotation.
    Args:
        query (str): The search query.
        context (str): The search context or result.
        date (str): The current date.
        day (str): The current day of the week.
    """
    logger.info(f"Logging results for query: {query}")
    with open("search_context.txt", "a") as f:
        context = "==" * 80 + "\n" + "QUERY:" + query + "\n" + "Context:" + context
        f.write(context)

def ordered_set_by_key(data):
    """
    Removes duplicate documents based on the 'page_content' attribute while preserving order.

    Args:
        data (list): A list of documents or items.

    Returns:
        list: A list of unique documents based on 'page_content'.
    """
    seen = set()
    unique_items = []

    # Sort the data based on the specified key
    for item in data:
        # If the key value is not in seen, add it to the unique list
        if item.page_content not in seen:
            seen.add(item.page_content)
            unique_items.append(item)

    return unique_items

def remove_consecutive_newlines(text):
    """
    Removes more than three consecutive newline characters from the text, replacing them with spaces.

    Args:
        text (str): The input text.

    Returns:
        str: The modified text without consecutive newlines.
    """
    # Regular expression to match 4 or more consecutive newline characters
    pattern = r"\n{3,}"

    # Replace the matched pattern with a single space
    return re.sub(pattern, "", text)

def remove_main_url(url):
    """
    Removes the trailing part of the URL after ".com" to simplify URLs.

    Args:
        url (str): The input URL.

    Returns:
        str: The base URL truncated after ".com".
    """
    return url.split(".com")[0] + ".com"

def extract_markdown_tables(filename, md_text):
    """
    Extracts markdown tables from a given text.
    TODO: Handle edge cases for malformed tables and add more robust parsing.
    Args:
        md_text (str): The markdown text.

    Returns:
        list: A list of markdown tables found in the input text.
    """
    logger.debug(f"Extracting markdown tables from {filename}")
    # Define a regex pattern to match markdown tables
    table_regex = re.compile(
        r'(\|(?:[^\n]+\|)+\n'  # Match table header
        r'\|(?:\s*[-:]+\s*\|)+\n'  # Match separator line
        r'(?:\|(?:[^\n]+\|)+\n)*)',  # Match table rows
        re.MULTILINE
    )

    # Find all markdown tables in the text
    tables = table_regex.findall(md_text)
    tables = [Document(table) for table in tables]
    print(tables)
    for i, t in enumerate(tables):
        tables[i].metadata['url'] = filename
        tables[i].metadata['source'] = filename
    return tables

def extract_urls(text):
    """
    Extracts URLs from the given text using a regular expression pattern.

    Args:
        text (str): The input text to search for URLs.

    Returns:
        list: A list of extracted URLs.
    """
    # Regular expression pattern to match URLs
    pattern = r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b'

    # Find all matches using the pattern
    urls = re.findall(pattern, text)

    return urls

def extract_subqueries(text):
    """
    Extracts subqueries from the text by searching for strings enclosed in square brackets.

    Args:
        text (str): The input text to extract subqueries from.

    Returns:
        list: A list of extracted subqueries.
    """
    # Regex to extract everything inside the square brackets
    pattern = r'\[([^\]]+)\]'

    # Find the matching part that is inside the square brackets
    match = re.search(pattern, text)

    if match:
        # Extract the matched string and split by commas, then strip quotes and spaces
        subqueries = match.group(1).split(",")
        subqueries = [query.strip().strip('"') for query in subqueries]
        return subqueries
    return []

def extract_urls_from_query(text):
    """
    Extracts all URLs from the given text.

    Args:
        text (str): The input text containing URLs.

    Returns:
        list: A list of URLs found in the text.
    """
    # Regular expression pattern to match URLs (http, https, www)
    url_pattern = r'(https?://[^\s]+|www\.[^\s]+)'

    # Find all URLs in the text using the pattern
    urls = re.findall(url_pattern, text)

    return urls

import logging
import re

import fitz
from bs4 import BeautifulSoup
from markdownify import markdownify
import pymupdf4llm
import sys
import os
from model_config import *
from openai import OpenAI
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



from utils.utils import *

# Configure logging
# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_html(soup):
    """
    Cleans an HTML document by removing unwanted elements such as header, footer, navigation, lists, and advertisements.
    """
    try:
        for tag in soup(['header', 'footer', 'nav', 'aside', 'li']):
            tag.decompose()
        for tag in soup.find_all(class_=['menu', 'sidebar', 'advertisement']):
            tag.decompose()
        return str(soup)
    except Exception as e:
        logger.error(f"Error cleaning HTML: {e}", exc_info=True)
        return str(soup)

def process_content(url, content_type, content):
    """
    Processes the content based on the file type (PDF or HTML). Converts PDFs to markdown and cleans HTML content 
    by removing unnecessary elements and converting to markdown.
    """
    try:
        logger.info(f"Processing content from URL: {url} with content_type: {content_type}")
        if url.endswith('.pdf') and content_type == 'internal_pdf':
            try:
                logger.info("Processing internal PDF.")
                markdown_content = f"Content from {url}\n\n" + pymupdf4llm.to_markdown(url)
            except Exception as e:
                logger.error(f"Error processing internal PDF: {e}", exc_info=True)
                return ""
        elif url.endswith('.pdf') or 'application/pdf' in content_type:
            try:
                logger.info("Processing PDF from stream.")
                pdf_document = fitz.open(stream=content, filetype="pdf")
                text_content = pymupdf4llm.to_markdown(pdf_document)
                markdown_content =  f"Content from {url}\n\n" + markdownify(text_content)
            except Exception as e:
                logger.error(f"Error processing PDF: {e}", exc_info=True)
                return ""
        elif 'text/html' in content_type:
            logger.info("Processing HTML content.")
            soup = BeautifulSoup(content, 'html.parser', from_encoding="iso-8859-1",
                                    )
            soup = clean_html(soup)
            markdown_content = markdownify(str(soup), strip=['a'])
            markdown_content = remove_consecutive_newlines(markdown_content)
            markdown_content = re.sub(r"\S{21,}", "", markdown_content)
        else:
            try:
                logger.info("Processing HTML content.")
                soup = BeautifulSoup(content, 'html.parser', from_encoding="iso-8859-1",
                                     )
                soup = clean_html(soup)
                markdown_content = markdownify(str(soup), strip=['a'])
                markdown_content = remove_consecutive_newlines(markdown_content)
                markdown_content = re.sub(r"\S{21,}", "", markdown_content)
            except Exception as e:
                try: 
                    if any(url.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.svg']):
                        logger.info("Converting image to markdown caption")
                        client = OpenAI(base_url=openai_compatible[model_config['llm_type']]
                                        ,api_key=llm_api_key)
                        md = MarkItDown(llm_client=client, 
                                        llm_model=model_config['llm_model_name'],
                                        llm_prompt='Answer in 2 sections 1. OCR output if there is any text (without losing structure) 2. What exactly is this?')
                        result = md.convert(url)
                        markdown_content =  f"Content from {url}\n\n" + result.text_content
                    else:
                        md = MarkItDown(enable_plugins=False) # Set to True to enable plugins
                        markdown_content =  f"Content from {url}\n\n" + md.convert(url).text_content
                except:
                    logger.error(f"Error processing HTML: {e}", exc_info=True)
                    return ""
        logger.info("Content processed successfully.")

        return markdown_content
    except Exception as e:
        logger.error(f"Error in process_content: {e}", exc_info=True)
        return ""

def process_content_pdf(file):
    """
    Processes a local PDF file by converting it to markdown.
    """
    try:
        logger.info(f"Processing local PDF file: {file.name}")
        return pymupdf4llm.to_markdown('tmp/' + file.name)
    except Exception as e:
        logger.error(f"Error processing local PDF: {e}", exc_info=True)
        return ""

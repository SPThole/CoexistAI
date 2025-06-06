import logging
import re

import fitz
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import pymupdf4llm

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
                markdown_content = pymupdf4llm.to_markdown(url)
            except Exception as e:
                logger.error(f"Error processing internal PDF: {e}", exc_info=True)
                return ""
        elif url.endswith('.pdf') or 'application/pdf' in content_type:
            try:
                logger.info("Processing PDF from stream.")
                pdf_document = fitz.open(stream=content, filetype="pdf")
                text_content = pymupdf4llm.to_markdown(pdf_document)
                markdown_content = md(text_content)
            except Exception as e:
                logger.error(f"Error processing PDF: {e}", exc_info=True)
                return ""
        else:
            try:
                logger.info("Processing HTML content.")
                soup = BeautifulSoup(content, 'html.parser', from_encoding="iso-8859-1")
                soup = clean_html(soup)
                markdown_content = md(str(soup), strip=['a'])
                markdown_content = remove_consecutive_newlines(markdown_content)
                markdown_content = re.sub(r"\S{21,}", "", markdown_content)
            except Exception as e:
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

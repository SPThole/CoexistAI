import asyncio
import aiohttp
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
import re
import time
import random
from typing import List, Optional, Union
from utils.knowledge_base import create_knowledge_base
from utils.websearch_utils import urls_to_docs
from langchain_text_splitters import TokenTextSplitter
from utils.retriever_utils import create_vectorstore_async
import chromadb
from chromadb.config import Settings
import hashlib
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

def get_sitemap_urls(base_url: str, headers: dict) -> List[str]:
    """
    Attempt to fetch and parse sitemap.xml for additional URLs.
    """
    sitemap_urls = []
    sitemap_url = urljoin(base_url, '/sitemap.xml')
    try:
        response = requests.get(sitemap_url, headers=headers, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for loc in root.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                url = loc.text
                if url and urlparse(url).netloc == urlparse(base_url).netloc:
                    sitemap_urls.append(url)
            logger.info(f"Found {len(sitemap_urls)} URLs in sitemap")
    except Exception as e:
        logger.info(f"No sitemap found or error parsing: {e}")
    return sitemap_urls

def crawl_website(base_url: str, depth: Optional[int] = None, max_pages: int = 100, min_delay: float = 1.0, max_delay: float = 3.0, url_keyword: Optional[str] = None) -> List[str]:
    """
    Crawl a website starting from base_url up to the specified depth (or full website if depth is None).
    Includes random delays between requests to avoid rate limiting.
    
    Args:
        base_url: The starting URL to crawl
        depth: Maximum depth to crawl (None for full website crawl, default: None)
        max_pages: Maximum number of pages to collect
        min_delay: Minimum delay between requests in seconds (default: 1.0)
        max_delay: Maximum delay between requests in seconds (default: 3.0)
        url_keyword: Optional keyword to filter URLs by presence in the URL string
        
    Returns:
        List of URLs found during crawling
    """
    visited = set()
    collected_urls = set()
    
    base_domain = urlparse(base_url).netloc
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    # Try to get URLs from sitemap
    sitemap_urls = get_sitemap_urls(base_url, headers)
    sitemap_urls = [url.split('#')[0].split('?')[0] for url in sitemap_urls if url not in visited][:max_pages // 2]  # Limit to half max_pages
    if url_keyword:
        sitemap_urls = [url for url in sitemap_urls if url_keyword.lower() in url.lower()]
    
    if depth is None:
        # Full website crawl without depth limit
        to_visit = [base_url] + sitemap_urls
        
        while to_visit and len(collected_urls) < max_pages:
            current_url = to_visit.pop(0)
            
            if current_url in visited:
                continue
                
            visited.add(current_url)
            collected_urls.add(current_url)
                
            try:
                # Use requests for simplicity, could be made async later
                response = requests.get(current_url, headers=headers, timeout=15, allow_redirects=True)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'lxml')
                
                # Find all links (anchors and frames)
                links = []
                for link in soup.find_all('a', href=True):
                    links.append(link['href'])
                for frame in soup.find_all(['frame', 'iframe'], src=True):
                    links.append(frame['src'])
                
                logger.info(f"Found {len(links)} links on {current_url}")
                
                for href in links:
                    full_url = urljoin(current_url, href)
                    
                    # Only include URLs from the same domain
                    if urlparse(full_url).netloc == base_domain and full_url not in visited:
                        # Skip fragments and query params that don't change the page
                        clean_url = full_url.split('#')[0].split('?')[0]
                        if clean_url not in visited:
                            if url_keyword and url_keyword.lower() not in clean_url.lower():
                                continue
                            to_visit.append(clean_url)
                            
                # Add random delay between requests to avoid rate limiting
                delay = random.uniform(min_delay, max_delay)
                logger.info(f"Waiting {delay:.2f} seconds before next request...")
                time.sleep(delay)
                            
            except Exception as e:
                logger.warning(f"Error crawling {current_url}: {e}")
                # Still add a delay even on error to be respectful
                delay = random.uniform(min_delay, min(max_delay, min_delay + 1.0))  # Shorter delay on error
                time.sleep(delay)
                continue
    else:
        # Depth-limited crawl
        sitemap_urls = get_sitemap_urls(base_url, headers)
        sitemap_urls = [url.split('#')[0].split('?')[0] for url in sitemap_urls if url not in visited][:max_pages // 2]  # Limit to half max_pages
        if url_keyword:
            sitemap_urls = [url for url in sitemap_urls if url_keyword.lower() in url.lower()]
        
        if depth == 0:
            to_visit = [(base_url, 0)]
        else:
            # For depth > 0, first scrape the base_url to get immediate links
            try:
                response = requests.get(base_url, headers=headers, timeout=15, allow_redirects=True)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'lxml')
                
                # Find all links (anchors and frames)
                links = []
                for link in soup.find_all('a', href=True):
                    links.append(link['href'])
                for frame in soup.find_all(['frame', 'iframe'], src=True):
                    links.append(frame['src'])
                
                initial_links = []
                for href in links:
                    full_url = urljoin(base_url, href)
                    
                    # Only include URLs from the same domain
                    if urlparse(full_url).netloc == base_domain:
                        # Skip fragments and query params that don't change the page
                        clean_url = full_url.split('#')[0].split('?')[0]
                        if url_keyword and url_keyword.lower() not in clean_url.lower():
                            continue
                        initial_links.append(clean_url)
                
                # Remove duplicates
                initial_links = list(set(initial_links))
                
                # Add random delay after initial scrape
                delay = random.uniform(min_delay, max_delay)
                logger.info(f"Initial scrape done, waiting {delay:.2f} seconds...")
                time.sleep(delay)
                
            except Exception as e:
                logger.warning(f"Error scraping base_url {base_url}: {e}")
                initial_links = []
                # Still add a delay
                delay = random.uniform(min_delay, min(max_delay, min_delay + 1.0))
                time.sleep(delay)
            
            to_visit = [(url, 1) for url in initial_links + sitemap_urls]
        
        while to_visit and len(collected_urls) < max_pages:
            current_url, current_depth = to_visit.pop(0)
            
            if current_url in visited or current_depth > depth:
                continue
                
            visited.add(current_url)
            collected_urls.add(current_url)
            
            if current_depth > depth:
                continue
                
            try:
                # Use requests for simplicity, could be made async later
                response = requests.get(current_url, headers=headers, timeout=15, allow_redirects=True)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'lxml')
                
                # Find all links (anchors and frames)
                links = []
                for link in soup.find_all('a', href=True):
                    links.append(link['href'])
                for frame in soup.find_all(['frame', 'iframe'], src=True):
                    links.append(frame['src'])
                
                logger.info(f"Found {len(links)} links on {current_url}")
                
                for href in links:
                    full_url = urljoin(current_url, href)
                    
                    # Only include URLs from the same domain
                    if urlparse(full_url).netloc == base_domain and full_url not in visited:
                        # Skip fragments and query params that don't change the page
                        clean_url = full_url.split('#')[0].split('?')[0]
                        if clean_url not in visited:
                            if url_keyword and url_keyword.lower() not in clean_url.lower():
                                continue
                            to_visit.append((clean_url, current_depth + 1))
                            
                # Add random delay between requests to avoid rate limiting
                delay = random.uniform(min_delay, max_delay)
                logger.info(f"Waiting {delay:.2f} seconds before next request...")
                time.sleep(delay)
                            
            except Exception as e:
                logger.warning(f"Error crawling {current_url}: {e}")
                # Still add a delay even on error to be respectful
                delay = random.uniform(min_delay, min(max_delay, min_delay + 1.0))  # Shorter delay on error
                time.sleep(delay)
                continue
    
    logger.info(f"Total collected URLs: {len(collected_urls)}")
    return list(collected_urls)

def filter_docs_by_keywords(docs_map: dict, keywords: List[str]) -> dict:
    """
    Filter documents based on keywords presence in content.
    
    Args:
        docs_map: Dictionary mapping URLs to list of documents
        keywords: List of keywords to filter by
        
    Returns:
        Filtered docs_map containing only documents with keywords
    """
    if not keywords:
        return docs_map
        
    filtered_docs = {}
    
    for url, docs in docs_map.items():
        filtered_docs[url] = []
        for doc in docs:
            content_lower = doc.page_content.lower()
            if any(keyword.lower() in content_lower for keyword in keywords):
                filtered_docs[url].append(doc)
                
        # Remove URLs with no documents after filtering
        if not filtered_docs[url]:
            del filtered_docs[url]
    
    return filtered_docs

async def crawl_and_create_kb(
    url_or_urls: Union[str, List[str]], 
    keywords: Optional[List[str]] = None, 
    depth: Optional[int] = None,
    crawl: bool = True,
    min_delay: float = 1.0,
    max_delay: float = 3.0,
    max_pages: int = 100,
    url_keyword: Optional[str] = None,
    hf_embeddings = None
) -> tuple[str, List[str]]:
    """
    Crawl website(s) and create a knowledge base from the content.
    
    Args:
        url_or_urls: Single URL to crawl or list of URLs to scrape directly
        keywords: Optional list of keywords to filter content by
        depth: Maximum crawl depth for crawling (None for full website crawl, default: None)
        crawl: Whether to crawl (TruFe) or process URLs directly (False)
        min_delay: Minimum delay between requests in seconds (default: 1.0)
        max_delay: Maximum delay between requests in seconds (default: 3.0)
        max_pages: Maximum number of pages to collect during crawling (default: 100)
        url_keyword: Optional keyword to filter URLs by presence in the URL string
        hf_embeddings: HuggingFace embeddings instance
        
    Returns:
        Tuple of (collection_name, list_of_scraped_urls)
    """
    if isinstance(url_or_urls, str):
        # Single URL
        if crawl:
            # Crawl the website
            logger.info(f"Crawling website: {url_or_urls} with depth {depth if depth is not None else 'unlimited'}")
            urls_to_process = crawl_website(url_or_urls, depth=depth, min_delay=min_delay, max_delay=max_delay, max_pages=max_pages, url_keyword=url_keyword)
            logger.info(f"Found {len(urls_to_process)} URLs to process")
        else:
            # Process single URL directly
            urls_to_process = [url_or_urls]
            logger.info(f"Processing single URL: {url_or_urls}")
    else:
        # List of URLs
        if crawl:
            # Crawl each URL in the list
            logger.info(f"Crawling {len(url_or_urls)} URLs with depth {depth if depth is not None else 'unlimited'}")
            all_urls = []
            for url in url_or_urls:
                logger.info(f"Crawling starting from: {url}")
                crawled_urls = crawl_website(url, depth=depth, min_delay=min_delay, max_delay=max_delay, max_pages=max_pages, url_keyword=url_keyword)
                all_urls.extend(crawled_urls)
            urls_to_process = list(set(all_urls))  # Remove duplicates
            logger.info(f"Found {len(urls_to_process)} total URLs to process")
        else:
            # Process URLs directly
            urls_to_process = url_or_urls
            logger.info(f"Processing {len(urls_to_process)} provided URLs directly")
    
    if not urls_to_process:
        raise ValueError("No URLs to process")
    
    # Filter by URL keyword if provided
    if url_keyword:
        logger.info(f"Filtering URLs by keyword: {url_keyword}")
        urls_to_process = [url for url in urls_to_process if url_keyword.lower() in url.lower()]
        logger.info(f"After URL keyword filtering: {len(urls_to_process)} URLs")
    
    if not urls_to_process:
        raise ValueError("No URLs to process after filtering")
    
    # Convert URLs to documents
    docs_map = await urls_to_docs(urls_to_process, local_mode=False, split=False)
    
    # Filter by keywords if provided
    if keywords:
        logger.info(f"Filtering content by keywords: {keywords}")
        docs_map = filter_docs_by_keywords(docs_map, keywords)
        logger.info(f"After filtering: {sum(len(docs) for docs in docs_map.values())} documents from {len(docs_map)} URLs")
    
    # Flatten all documents
    all_docs = []
    for docs in docs_map.values():
        all_docs.extend(docs)
    
    if not all_docs:
        raise ValueError("No documents found after processing and filtering")
    
    logger.info(f"Total documents: {len(all_docs)}")
    
    # Split documents
    text_splitter = TokenTextSplitter(chunk_size=512, chunk_overlap=128)
    all_docs = text_splitter.split_documents(all_docs)
    
    logger.info(f"Total documents after splitting: {len(all_docs)}")
    
    # Create collection name
    crawl_mode = "crawl" if crawl else "direct"
    if isinstance(url_or_urls, str):
        base_name = urlparse(url_or_urls).netloc.replace('.', '_')  # Replace dots with underscores
    else:
        base_name = "url_list"
    
    if keywords:
        # Sanitize keywords - replace spaces and special chars with underscores
        sanitized_keywords = [k.replace(' ', '_').replace('-', '_') for k in keywords[:3]]
        base_name += f"_keywords_{'_'.join(sanitized_keywords)}"
    
    if url_keyword:
        base_name += f"_urlkeyword_{url_keyword.replace(' ', '_').replace('-', '_')}"
    
    sorted_urls = ''.join(sorted(urls_to_process))
    hash_suffix = hashlib.md5(sorted_urls.encode()).hexdigest()[:8]
    collection_name = f"{crawl_mode}_{base_name}_{hash_suffix}"
    
    # Ensure collection name is valid: starts/ends with alphanumeric, contains only allowed chars
    import re
    collection_name = re.sub(r'[^a-zA-Z0-9._-]', '_', collection_name)  # Replace invalid chars with _
    collection_name = collection_name.strip('_')  # Remove leading/trailing underscores
    
    # Ensure minimum length and valid start/end
    if not collection_name or len(collection_name) < 3:
        collection_name = f"crawl_{hash_suffix}"
    
    # Ensure starts with alphanumeric
    if not collection_name[0].isalnum():
        collection_name = f"crawl_{collection_name}"
    
    # Ensure ends with alphanumeric  
    if not collection_name[-1].isalnum():
        collection_name = f"{collection_name}_{hash_suffix[:4]}"
    
    # Create vectorstore
    client = chromadb.PersistentClient(path="./chroma_db", settings=Settings(anonymized_telemetry=False, allow_reset=True))
    
    # Delete existing collection if it exists
    try:
        client.delete_collection(collection_name)
        logger.info(f"Deleted existing collection {collection_name}")
    except Exception as e:
        logger.info(f"Collection {collection_name} not found or error deleting: {e}")
    
    try:
        await create_vectorstore_async(
            docs=all_docs,
            collection_name=collection_name,
            hf_embeddings=hf_embeddings,
            top_k=3,
            ensemble_weights=[0.4, 0.6],
            local_mode=True,
            persist_directory="./chroma_db"
        )
        logger.info(f"Knowledge base created: {collection_name}")
    except Exception as e:
        logger.error(f"Error creating knowledge base: {e}")
        raise
    
    return collection_name, urls_to_process
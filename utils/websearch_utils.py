import asyncio
import aiohttp
import concurrent.futures
import hashlib
import logging
import os
import re
import requests
import time
import random
import json
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from functools import partial
from langchain.docstore.document import Document
from langchain.retrievers import ContextualCompressionRetriever, EnsembleRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.retrievers import BM25Retriever
from langchain_community.utilities import SearxSearchWrapper
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import MarkdownHeaderTextSplitter, TokenTextSplitter
from markdownify import markdownify as md
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_search import YoutubeSearch
from markitdown import MarkItDown
from pathlib import Path
from rank_bm25 import BM25Okapi


import chromadb

from utils.utils import *
from utils.answer_generation import *
from utils.reddit_utils import *
from utils.process_content import process_content

chromadb.api.client.SharedSystemClient.clear_system_cache()

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(handler)

# Global blacklist for unreachable domains
UNREACHABLE_DOMAINS_BLACKLIST = set()


class SearchWeb:
    """
    A class for performing web searches using Searx and scraping content from web pages.

    Attributes:
        port (int): The port number for the Searx search wrapper.
        searcher (SearxSearchWrapper): An instance of SearxSearchWrapper for querying search engines.
    """

    def __init__(self, port):
        """
        Initializes the SearchWeb class with the given Searx server port.

        Args:
            port (int): The port number for Searx search service.
        """
        self.searcher = SearxSearchWrapper(searx_host=f"http://localhost:{port}")

    def query_search(self, query, engines=['google'], num_results=5):
        """
        Performs a search using the Searx engine and retrieves search results.

        Args:
            query (str): The search query.
            engines (list, optional): The search engines to use. Defaults to ['google'].
            num_results (int, optional): The number of search results to retrieve. Defaults to 5.

        Returns:
            list: The search results from Searx.
        """
        try:
            search_results = self.searcher.results(
                query,
                num_results=num_results,
                engines=engines
            )
            logger.info(f"Search results for query '{query}': {search_results}")
            return search_results
        except Exception as e:
            logger.error(f"Error during search for query '{query}': {e}")
            return []

    def scrape_text(self, url):
        """
        Scrapes the plain text content from the specified URL, removing HTML tags and unwanted elements.

        Args:
            url (str): The URL to scrape text from.

        Returns:
            str: The cleaned text content from the URL, or None if the request fails.
        """
        try:
            # Handle GitHub raw URLs
            if 'github.com' in url:
                url = url.replace('github', 'raw.githubusercontent')
            
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, timeout=15, headers=headers)
            response.raise_for_status()

            page_content = response.content

            soup = BeautifulSoup(page_content, 'html.parser')

            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            text = re.sub(r'<.*?>', '', text)

            logger.info(f"Scraped text from URL: {url}")
            return text
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error while scraping {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"General error while scraping {url}: {e}")
            return None

    def scrape_top_results(self, urls):
        """
        Scrapes the text content from a list of URLs.

        Args:
            urls (list): A list of URLs to scrape content from.

        Returns:
            list: A list of text content from the URLs.
        """
        out = []
        for url in urls:
            try:
                text = self.scrape_text(url)
                out.append(text)
            except Exception as e:
                logger.error(f"Error scraping URL {url}: {e}")
                out.append(None)
        return out


async def process_url(
    url,
    query,
    text_splitter,
    used_urls,
    hf_embeddings,
    cross_encoder,
    rerank,
    top_k,
    subquery,
    search_snippets_orig,
    model,
    local_mode=False,
    split=True
):
    """
    Processes a single URL by retrieving documents, splitting text, and ranking the content.
    Uses async/process pool-based document retrieval and robust logging.

    Args:
        url (str): The URL to process.
        query (str): The main query string.
        text_splitter (TokenTextSplitter): Text splitter for splitting documents into chunks.
        used_urls (list): List of URLs already processed.
        hf_embeddings: Hugging Face embeddings for document embedding.
        cross_encoder: Cross-encoder for reranking.
        rerank (bool): Whether to rerank results.
        top_k (int): Number of top results to retrieve.
        subquery (str): The query or subquery to search.
        search_snippets_orig (dict): Dictionary of original search snippets.
        model: Language model for generating answers.
        local_mode (bool): Whether to process locally stored content (e.g., PDFs).
        split (bool): Whether to split the text into chunks.

    Returns:
        tuple: Processed context, retrieved documents, document list, and URL.
    """
    try:
        # Use async document retrieval
        docs = await urls_to_docs([url], local_mode=local_mode, split=split)
        logger.info(f"Processed {len(docs)} docs for URL: {url}")
    except Exception as e:
        logger.error(f"Error processing {url}: {e}")
        return None, None, None, url

    for i, d in enumerate(docs):
        if not local_mode:
            docs[i].page_content = remove_urls(d.page_content)
        docs[i].metadata['url'] = url
        docs[i].metadata['query'] = query

    # Special handling for Reddit and YouTube URLs
    if 'reddit.com' in url:
        try:
            logger.info(f"Processing Reddit URL with wait: {url}")
            await asyncio.sleep(random.randint(1, 3))  # Async sleep to avoid rate limiting
            response = reddit_reader_response(
                subreddit=None, url_type='url', n=5, k=5,
                custom_url=url, time_filter=None,
                search_query=None, sort_type=None,
                model=model
            )
            docs.append(Document(response, metadata={'source': url, 'url': url}))
            logger.info(f"Appended Reddit response for {url}")
        except Exception as e:
            logger.error(f"Error processing Reddit URL {url}: {e}")
    if 'youtube' in url:
        try:
            logger.info(f"Processing YouTube URL: {url}")
            response = youtube_transcript_response(url, f"Summarise for {subquery}", model)
            docs.append(Document(response, metadata={'source': url, 'url': url}))
            logger.info(f"Appended YouTube transcript for {url}")
        except Exception as e:
            logger.error(f"Error processing YouTube URL {url}: {e}")

    if split:
        try:
            docs = text_splitter.split_documents(docs)
            logger.info(f"Split docs for {url} into {len(docs)} chunks")
        except Exception as e:
            logger.error(f"Error splitting docs for {url}: {e}")

    # Log start of encoding
    encoding_start = time.time()
    logger.info(f"Encoding start for URL: {url}")

    try:
        chromadb.api.client.SharedSystemClient.clear_system_cache()
        vectorstore = Chroma.from_documents(
            documents=docs,
            collection_name="rag-chroma",
            embedding=hf_embeddings,
        )
        sem_retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})
        bm25_retriever = BM25Retriever.from_documents(docs)
        bm25_retriever.k = top_k
        ensemble_retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, sem_retriever], weights=[0.25, 0.75]
        )
    except Exception as e:
        logger.error(f"Error setting up retrievers for {url}: {e}")
        return None, None, None, url

    encoding_end = time.time()
    logger.info(f"Encoding end for URL: {url}, Time taken: {encoding_end - encoding_start:.2f} seconds")

    if rerank:
        try:
            rerank_start = time.time()
            logger.info(f"Reranking start for URL: {url}")
            compressor = CrossEncoderReranker(model=cross_encoder, top_n=5)
            ensemble_retriever = ContextualCompressionRetriever(
                base_compressor=compressor,
                base_retriever=ensemble_retriever
            )
            rerank_end = time.time()
            logger.info(f"Reranking end for URL: {url}, Time taken: {rerank_end - rerank_start:.2f} seconds")
        except Exception as e:
            logger.error(f"Error during reranking for {url}: {e}")

    # TODO: Consider improving query and filter logic for more flexible retrieval
    try:
        query_filter = {"name": {"$in": [query]}}
        url_filter = {"name": {"$in": [url]}}
        combined_filter = {"$and": [query_filter, url_filter]}
        retrieved_docs = ensemble_retriever.invoke(
            subquery, search_kwargs={"k": top_k}, filter=combined_filter
        )
        logger.info(f"Retrieved {len(retrieved_docs)} docs for {url}")
    except Exception as e:
        logger.error(f"Error retrieving docs for {url}: {e}")
        return None, None, None, url

    # Build context string
    try:
        if not local_mode:
            context = [
                f"search result::title:{d.metadata.get('title', '')} url:{d.metadata['source'].replace('https://r.jina.ai/', '')}  \ncontent: {d.page_content}\n"
                for i, d in enumerate(retrieved_docs)
            ]
        else:
            context = [
                f"search result: File:{d.metadata.get('source', '').replace('https://r.jina.ai/', '')}  \ncontent: {d.page_content}\n"
                for i, d in enumerate(retrieved_docs)
            ]
        context = '\n'.join(context).strip()
        logger.info(f"Built context for {url}")
    except Exception as e:
        logger.error(f"Error building context for {url}: {e}")
        context = ''

    return context, retrieved_docs, docs, url


async def context_to_docs(
    urls_list,
    subqueries,
    search_snippets,
    search_snippets_orig,
    query,
    top_k,
    hf_embeddings,
    rerank=False,
    cross_encoder=None,
    model=None,
    local_mode=False,
    split=True
):
    """
    Retrieves and processes documents from a list of URLs, converts them into a retrievable format.
    Uses parallel execution and robust logging. Handles errors gracefully and logs all major steps.

    Args:
        urls_list (list): List of lists of URLs to process (one sublist per subquery).
        subqueries (list): List of subqueries for each URL group.
        search_snippets (list): List of search snippet documents.
        search_snippets_orig (dict): Dictionary of original search snippets.
        query (str): The query string.
        top_k (int): The number of top results to retrieve.
        hf_embeddings: Hugging Face embeddings for vector retrieval.
        rerank (bool, optional): Whether to rerank results. Defaults to False.
        cross_encoder: Cross-encoder model for reranking.
        model: Language model for generating content.
        local_mode (bool, optional): Whether to process locally stored content (e.g., PDFs). Defaults to False.
        split (bool, optional): Whether to split documents into chunks. Defaults to True.

    Returns:
        tuple: Combined context string, list of retrieved documents, and list of all processed documents.
    """
    logger.info(f"Starting async context_to_docs for {len(urls_list)} URL groups.")
    text_splitter = TokenTextSplitter(chunk_size=512, chunk_overlap=128)
    contexts = []
    rtr_docs = []
    used_urls = []
    total_docs = []

    # Create async tasks for parallel URL processing
    async def process_url_async_wrapper(url, subquery_idx):
        """Async wrapper for process_url to handle individual URL processing"""
        try:
            logger.info(f"Starting async processing for URL: {url}")
            
            # Call the async version of process_url
            context, retrieved_docs, docs, processed_url = await process_url(
                url=url,
                query=query,
                text_splitter=text_splitter,
                used_urls=used_urls,
                hf_embeddings=hf_embeddings,
                cross_encoder=cross_encoder,
                rerank=rerank,
                top_k=top_k,
                subquery=subqueries[subquery_idx],
                search_snippets_orig=search_snippets_orig,
                model=model,
                local_mode=local_mode,
                split=split
            )
            
            # Process search snippets context replacement
            for k in search_snippets:
                if context:
                    context = context.replace(
                        k.metadata['source'],
                        k.metadata['source'] + f"title:{k.metadata.get('title', '')}"
                    )
            
            return {
                'url': processed_url,
                'context': context,
                'retrieved_docs': retrieved_docs,
                'docs': docs,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Async processing failed for URL {url}: {e}")
            return {
                'url': url,
                'context': None,
                'retrieved_docs': None,
                'docs': None,
                'success': False,
                'error': str(e)
            }

    # Collect all URL processing tasks
    all_tasks = []
    for u, urls in enumerate(urls_list):
        if not urls:
            logger.warning(f"No URLs provided for subquery {u}.")
            continue
        
        for url in urls:
            task = process_url_async_wrapper(url, u)
            all_tasks.append(task)
    
    if not all_tasks:
        logger.warning("No URLs to process.")
        search_snippets_context = [
            f"search result:: title:{d.metadata.get('title', '')} url:{d.metadata['source'].replace('https://r.jina.ai/', '')}  \ncontent: {d.page_content}\n"
            for d in search_snippets
        ]
        search_snippets_context = '\n'.join(search_snippets_context)
        return search_snippets_context, [], []

    # Execute all tasks in parallel
    logger.info(f"Processing {len(all_tasks)} URLs in parallel using asyncio.gather")
    results = await asyncio.gather(*all_tasks, return_exceptions=True)
    
    # Process results
    successful_results = 0
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"URL processing task failed with exception: {result}")
            continue
            
        if result['success'] and result['context'] and result['retrieved_docs'] and result['docs']:
            contexts.append(result['context'])
            rtr_docs.append(result['retrieved_docs'])
            total_docs.extend(result['docs'])
            used_urls.append(result['url'])
            successful_results += 1
            logger.info(f"Successfully processed and added context/docs for URL: {result['url']}")
        else:
            logger.warning(f"No valid docs/context for URL: {result['url']}")
            if not result['success']:
                logger.error(f"Processing error for {result['url']}: {result.get('error', 'Unknown error')}")

    logger.info(f"Async parallel processing complete. Successfully processed {successful_results}/{len(all_tasks)} URLs")

    search_snippets_context = [
        f"search result:: title:{d.metadata.get('title', '')} url:{d.metadata['source'].replace('https://r.jina.ai/', '')}  \ncontent: {d.page_content}\n"
        for d in search_snippets
    ]
    search_snippets_context = '\n'.join(search_snippets_context)
    final_context = '\n\n'.join(contexts).strip() + '\n' + search_snippets_context

    logger.info(f"async context_to_docs complete. Total contexts: {len(contexts)}, total docs: {len(total_docs)}")
    return final_context, rtr_docs, total_docs


def text_to_docs(texts_with_metadata):
    """
    Converts a list of text snippets with metadata into a list of Document objects.

    Args:
        texts_with_metadata (list): A list of dictionaries, each containing a 'snippet' (text content) and
                                    'link' (source URL), and optionally a 'title'.

    Returns:
        list: A list of Document objects, where each document contains the 'snippet' as page content and
              'link' and 'title' as metadata.
    """
    docs = []
    for t in texts_with_metadata:
        try:
            doc = Document(
                page_content=t['snippet'],
                metadata={'source': t['link'], 'title': t.get('title', '')}
            )
            docs.append(doc)
            logger.info(f"Created Document for source: {t.get('link', 'N/A')}")
        except Exception as e:
            logger.error(f"Failed to create Document for entry: {t}. Error: {e}")
    return docs


def remove_urls(text):
    """Removes URLs and Markdown-style links from a string.

    Args:
        text: The string to remove URLs from.

    Returns:
        The string with URLs and Markdown-style links removed.
    """
    try:
        # Pattern for plain URLs
        url_pattern = r'(https?://|www\.)\S+'
        # Pattern for Markdown-style links
        markdown_link_pattern = r'\[([^\]]+)\]\((https?://|www\.)\S+\)'
        # Remove plain URLs
        text = re.sub(url_pattern, '', text)
        # Remove Markdown-style links (replace with just the link text)
        text = re.sub(markdown_link_pattern, r'\1', text)
        logger.info("URLs and markdown links removed from text.")
        return text
    except Exception as e:
        logger.error(f"Error removing URLs from text: {e}")
        return text


def extract_domain_from_url(url):
    """
    Extracts the domain from a URL for blacklisting purposes.
    
    Args:
        url (str): The URL to extract domain from
        
    Returns:
        str: The domain name (without www. prefix)
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix if present
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception as e:
        logger.error(f"Error extracting domain from URL {url}: {e}")
        return None


async def check_url_reachability(url, timeout=10):
    """
    Checks if a URL is reachable using an async HEAD request.
    
    Args:
        url (str): The URL to check
        timeout (int): Timeout in seconds for the request
        
    Returns:
        bool: True if URL is reachable, False otherwise
    """
    try:
        timeout_config = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            async with session.head(url, allow_redirects=True) as response:
                # Consider 2xx and 3xx status codes as reachable
                is_reachable = 200 <= response.status < 400
                logger.info(f"URL {url} reachability check: {response.status} - {'Reachable' if is_reachable else 'Unreachable'}")
                return is_reachable
    except Exception as e:
        logger.warning(f"URL {url} is unreachable: {e}")
        return False


async def check_urls_reachability(urls):
    """
    Checks reachability of multiple URLs concurrently.
    
    Args:
        urls (list): List of URLs to check
        
    Returns:
        dict: Dictionary mapping URLs to their reachability status (True/False)
    """
    if not urls:
        return {}
    
    logger.info(f"Checking reachability of {len(urls)} URLs")
    tasks = [check_url_reachability(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    reachability_map = {}
    for url, result in zip(urls, results):
        if isinstance(result, Exception):
            logger.error(f"Error checking URL {url}: {result}")
            reachability_map[url] = False
        else:
            reachability_map[url] = result
    
    reachable_count = sum(1 for status in reachability_map.values() if status)
    logger.info(f"Reachability check complete: {reachable_count}/{len(urls)} URLs are reachable")
    return reachability_map


def add_domains_to_blacklist(urls):
    """
    Adds domains from unreachable URLs to the global blacklist.
    
    Args:
        urls (list): List of URLs whose domains should be blacklisted
    """
    global UNREACHABLE_DOMAINS_BLACKLIST
    
    for url in urls:
        domain = extract_domain_from_url(url)
        if domain and domain not in UNREACHABLE_DOMAINS_BLACKLIST:
            UNREACHABLE_DOMAINS_BLACKLIST.add(domain)
            logger.info(f"Added domain {domain} to blacklist")
    
    logger.info(f"Current blacklist contains {len(UNREACHABLE_DOMAINS_BLACKLIST)} domains: {list(UNREACHABLE_DOMAINS_BLACKLIST)}")


def modify_query_with_blacklist(query):
    """
    Modifies a search query to exclude blacklisted domains using -site: operator.
    
    Args:
        query (str): The original search query
        
    Returns:
        str: Modified query with blacklisted domains excluded
    """
    global UNREACHABLE_DOMAINS_BLACKLIST
    
    if not UNREACHABLE_DOMAINS_BLACKLIST:
        return query
    
    # Add -site: exclusions for each blacklisted domain
    exclusions = [f"-site:{domain}" for domain in UNREACHABLE_DOMAINS_BLACKLIST]
    modified_query = f"{query} {' '.join(exclusions)}"
    
    logger.info(f"Modified query with {len(exclusions)} domain exclusions: {modified_query}")
    return modified_query


def query_to_search_results(query, search_response, websearcher, num_results=3, max_retries=2):
    """
    Performs a web search for each query in the search response and extracts the URLs and search snippets.
    Includes URL reachability checking, retry logic, and domain blacklisting to avoid unreachable sites.

    Args:
        query (str): The original user query.
        search_response (list): A list of search queries or subqueries.
        websearcher (object): An instance of a web searcher (e.g., SearxSearchWrapper) to perform the search.
        num_results (int, optional): The number of results to retrieve for each search query. Defaults to 3.
        max_retries (int, optional): Maximum number of retries when all URLs are unreachable. Defaults to 2.

    Returns:
        tuple: A tuple containing:
            - search_snippets (list): A list of search result snippets for all queries.
            - search_results (list): The raw search results for the last query processed.
            - search_results_urls (list): A list of lists, where each sublist contains URLs from the search results of a query.
    """
    async def perform_search_with_reachability_check(search_queries, current_num_results):
        """
        Inner async function to perform search and check URL reachability.
        """
        all_search_snippets = []
        all_search_results = []
        all_search_results_urls = []
        all_urls_found = set()  # Track all URLs to avoid duplicates
        
        for r in search_queries:
            try:
                # Modify query to exclude blacklisted domains
                modified_query = modify_query_with_blacklist(r)
                results = websearcher.query_search(modified_query, num_results=current_num_results)
                logger.info(f"Search results fetched for subquery: {r} (modified: {modified_query})")
            except Exception as e:
                logger.error(f"Error fetching search results for subquery '{r}': {e}")
                results = []
            
            # Add mentioned URLs as empty-snippet results
            mentioned_url = extract_urls_from_query(query)
            for u in mentioned_url:
                if u not in all_urls_found:
                    results.append({'link': u, 'snippet': ''})
                    all_urls_found.add(u)
            
            try:
                urls = [s['link'] for s in results if 'link' in s and s['link'] not in all_urls_found]
                # Update the set of all URLs found
                all_urls_found.update(urls)
                all_search_results_urls.append(urls)
                all_search_snippets.extend(results)
            except Exception as e:
                logger.error(f"Error processing search results for subquery '{r}': {e}")
                all_search_snippets.extend(results)
            all_search_results = results  # Keep last results for return
        
        return all_search_snippets, all_search_results, all_search_results_urls, list(all_urls_found)
    
    try:
        # Initialize variables
        search_snippets = []
        search_results = []
        search_results_urls = []
        retry_count = 0
        
        while retry_count <= max_retries:
            logger.info(f"Search attempt {retry_count + 1}/{max_retries + 1}")
            
            # Use the same number of results for all attempts
            current_num_results = num_results
            
            # Perform search (this needs to be called in an async context)
            try:
                # Since we're in a sync function but need async operations, we need to handle this
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're already in an async context, create a task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run, 
                            perform_search_with_reachability_check(search_response, current_num_results)
                        )
                        search_snippets, search_results, search_results_urls, all_urls = future.result()
                else:
                    # If no event loop is running, we can use asyncio.run
                    search_snippets, search_results, search_results_urls, all_urls = asyncio.run(
                        perform_search_with_reachability_check(search_response, current_num_results)
                    )
            except Exception as e:
                logger.error(f"Error in search execution: {e}")
                # Fallback to synchronous search without reachability checking
                mentioned_url = extract_urls_from_query(query)
                search_results_urls = []
                search_snippets = []
                search_results = []
                all_urls = []
                
                for r in search_response:
                    try:
                        modified_query = modify_query_with_blacklist(r)
                        results = websearcher.query_search(modified_query, num_results=current_num_results)
                        logger.info(f"Fallback search results fetched for subquery: {r}")
                    except Exception as e:
                        logger.error(f"Error fetching search results for subquery '{r}': {e}")
                        results = []
                    
                    # Add mentioned URLs as empty-snippet results
                    for u in mentioned_url:
                        results.append({'link': u, 'snippet': ''})
                    
                    try:
                        urls = [s['link'] for s in results if 'link' in s]
                        all_urls.extend(urls)
                        search_results_urls.append(urls)
                        search_snippets.extend(results)
                    except Exception as e:
                        logger.error(f"Error processing search results for subquery '{r}': {e}")
                        search_snippets.extend(results)
                    search_results = results
                
                # If we have URLs, break out of retry loop
                if all_urls:
                    logger.info(f"Fallback search successful with {len(all_urls)} URLs")
                    break
            
            # Check URL reachability if we have URLs
            if all_urls:
                try:
                    # Check reachability
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, check_urls_reachability(all_urls))
                            reachability_map = future.result()
                    else:
                        reachability_map = asyncio.run(check_urls_reachability(all_urls))
                    
                    # Count reachable URLs
                    reachable_urls = [url for url, is_reachable in reachability_map.items() if is_reachable]
                    unreachable_urls = [url for url, is_reachable in reachability_map.items() if not is_reachable]
                    
                    logger.info(f"Reachability check: {len(reachable_urls)}/{len(all_urls)} URLs are reachable")
                    
                    # If we have reachable URLs, we're done
                    if reachable_urls:
                        logger.info(f"Found {len(reachable_urls)} reachable URLs, search successful")
                        # Add unreachable domains to blacklist for future searches
                        if unreachable_urls:
                            add_domains_to_blacklist(unreachable_urls)
                        break
                    else:
                        # All URLs are unreachable, add domains to blacklist and retry
                        logger.warning(f"All {len(all_urls)} URLs are unreachable, adding domains to blacklist")
                        add_domains_to_blacklist(all_urls)
                        
                        # If this was our last retry, break
                        if retry_count >= max_retries:
                            logger.error(f"Max retries ({max_retries}) reached, returning results anyway")
                            break
                        
                        # Continue to next retry
                        retry_count += 1
                        logger.info(f"Retrying search with updated blacklist (attempt {retry_count + 1})")
                        continue
                        
                except Exception as e:
                    logger.error(f"Error checking URL reachability: {e}")
                    # If reachability check fails, proceed with the URLs we have
                    break
            else:
                # No URLs found, try next iteration if retries available
                if retry_count >= max_retries:
                    logger.warning("No URLs found after all retries")
                    break
                retry_count += 1
                continue
        
        logger.info(f"Search completed after {retry_count + 1} attempts with {len(search_snippets)} snippets")
        return search_snippets, search_results, search_results_urls
        
    except Exception as e:
        logger.error(f"Error in query_to_search_results: {e}")
        return [], [], []


async def query_web_response(
    query,
    date,
    day,
    websearcher,
    hf_embeddings,
    rerank,
    cross_encoder,
    model,
    text_model,
    num_results=3,
    document_paths=None,
    local_mode=False,
    split=True
):
    """
    Performs a web search and retrieves results, then generates a response based on those results.
    Uses robust logging and improved error handling. All print statements replaced with logger.

    Args:
        query (str): The input query.
        date (str): The current date.
        day (str): The current day of the week.
        websearcher (SearchWeb): The web search engine wrapper.
        hf_embeddings: Hugging Face embeddings for retrieval.
        rerank (bool): Whether to rerank results.
        cross_encoder: Cross-encoder model for reranking.
        model: Language model for processing responses.
        text_model: Language model for text generation.
        num_results (int, optional): Number of search results to retrieve. Defaults to 3.
        document_paths (list, optional): List of paths for local documents. Defaults to None.
        local_mode (bool, optional): Whether to process local documents. Defaults to False.
        split (bool, optional): Whether to split documents into chunks. Defaults to True.

    Returns:
        tuple: Generated response, sources, search results, retrieved documents, and context.
    """
    try:
        search_response,is_summary,is_covered_urls = await query_agent(query, model, date, day)
        if len(search_response) == 0:
            search_response = [query]
            logger.info(f"Search response generated for query '{query}' using pure query.")
        if is_summary:
            split=False
        search_response = [text.replace('"', '') for text in search_response]
        logger.info(f"Search phrases for query '{query}': {search_response}")
    except Exception as e:
        logger.error(f"Error generating search response for query '{query}': {e}")
        return None, None, None, None, None, None, None

    if websearcher is None or local_mode:
        logger.warning("Please add list of paths as input, earlier it used to be list of list")
        all_paths=[]
        for k in document_paths:
            all_paths.extend(get_all_paths(k))
        all_paths = [all_paths]
        logger.info(f"Total paths for '{query}': {all_paths}")
        # Only time doc is considered for different subqueries and only first is getting considered
        search_snippets, search_results, search_results_urls = [], [], all_paths * len(search_response)
        search_snippets_orig = {}
        logger.warning("No websearcher provided; using document_paths only.")
    else:
        try:
            extracted_urls = extract_urls_from_query(query)
            if len(extracted_urls)>0:
                for u in extracted_urls:
                    if ('reddit' in u) or ('youtube' in u):
                        is_covered_urls = True
                    else:
                        is_summary = True
                        is_covered_urls = False
            if extract_urls_from_query(query) and not is_covered_urls:
                logger.info(f"Extracted URLs from query '{query}': {extract_urls_from_query(query)}")
                search_snippets_orig = []
                for u in extract_urls_from_query(query):
                    search_snippets_orig.append({'snippet':'',
                                            'link':u,
                                            'title':u})
                search_results = search_snippets_orig
                search_results_urls = [extract_urls_from_query(query)]
            else:
                search_snippets_orig, search_results, search_results_urls = query_to_search_results(
                    query, search_response, websearcher, num_results
                )
            search_snippets = text_to_docs(search_snippets_orig)
            try:
                search_snippets_orig = {k['link']: k['snippet'] for k in search_snippets_orig if 'link' in k.keys()}
            except Exception as e:
                logger.warning(f"No good searches found or error building search_snippets_orig: {e}")
            logger.info(f"Search results fetched for query '{query}'.")
        except Exception as e:
            logger.error(f"Error fetching search results for query '{query}': {e}")
            return None, None, None, None, None, None, None

    try:
        
        context, rtr_docs, total_docs = await context_to_docs(
            search_results_urls,
            search_response,
            search_snippets,
            search_snippets_orig,
            query,
            2,
            hf_embeddings,
            rerank,
            cross_encoder=cross_encoder,
            model=text_model,
            local_mode=local_mode,
            split=split
        )
        logger.info(f"Async context generated to answer query '{query}'.")
    except Exception as e:
        logger.error(f"Error generating context for query '{query}': {e}")
        return None, None, None, None, None, None, None

    try:
        log_results(query, context, '', '')
        logger.info(f"Logged results for query '{query}'.")
    except Exception as e:
        logger.warning(f"Error logging results for query '{query}': {e}")

    try:
        if not is_summary or (is_covered_urls):
            logger.info(f"Generating Answer for query '{query}' using async response gen.")
            response_1, sources = await response_gen(text_model, query, context)
        else:
            logger.info(f"Generating summary for query '{query}' using async summarizer.")
            response_1 = await summarizer(query, total_docs, text_model, 16)
            sources = str(search_results_urls)
        logger.info(f"Async response generated for query '{query}'.")
    except Exception as e:
        logger.error(f"Error generating async response for query '{query}': {e}")
        return None, None, None, None, None, None, None

    return response_1, sources, search_response, search_results, rtr_docs, total_docs, context


async def url_to_markdown(url, executor, local_mode=False):
    """
    Asynchronously converts a URL or local file to markdown using process_content.
    Handles both local files and HTTP URLs, with logging and error handling.

    Args:
        url (str): The URL or local file path to process.
        executor (concurrent.futures.Executor): The executor for running blocking code.
        local_mode (bool, optional): If True, treat url as a local file. Defaults to False.

    Returns:
        str or None: The processed markdown content, or None if an error occurred.
    """
    try:
        if local_mode:
            # Local mode: read file from disk
            content_type = "internal_pdf"
            content = ""
            if not os.path.isfile(url):
                logger.error(f"The file {url} does not exist.")
                raise FileNotFoundError(f"The file {url} does not exist.")
            logger.info(f"Processing local file: {url}")
            # Run process_content in executor for local file
            markdown_content = await asyncio.get_event_loop().run_in_executor(
                executor, process_content, url, content_type, content
            )
        else:
            # Remote mode: fetch content from URL
            timeout = aiohttp.ClientTimeout(total=30)
            logger.info(f"Fetching URL: {url}")
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    content_type = response.headers.get('Content-Type', '')
                    content = await response.read()
                    logger.info(f"Fetched content from {url} with type {content_type}")
                    # Run process_content in executor for URL content
                    markdown_content = await asyncio.get_event_loop().run_in_executor(
                        executor, process_content, url, content_type, content
                    )
        logger.info(f"Processed markdown for: {url}")
        return markdown_content
    except FileNotFoundError as fnf:
        logger.error(f"File not found: {fnf}")
        return None
    except aiohttp.ClientError as ce:
        logger.error(f"HTTP error for {url}: {ce}")
        return None
    except Exception as e:
        logger.error(f"An error occurred processing {url}: {e}")
        # TODO: Add more granular error handling if needed (e.g., for content parsing)
        return None


async def urls_to_docs(urls, local_mode=False, split=True):
    """
    Asynchronously converts a list of URLs to document objects, optionally from local files.
    Uses async and ProcessPoolExecutor for efficient parallel processing.

    Args:
        urls (list): List of URLs to process.
        local_mode (bool, optional): Whether to process local files. Defaults to False.

    Returns:
        list: List of processed document objects.
    """
    docs = []
    if not urls:
        logger.warning("0 URLs were given to urls_to_docs.")
        return docs

    # Use a process pool for CPU-bound work (process_content)
    loop = asyncio.get_event_loop()
    with ProcessPoolExecutor() as executor:
        # Schedule all url_to_markdown tasks concurrently
        tasks = [url_to_markdown(url, executor, local_mode=local_mode) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                logger.error(f"Error fetching or processing URL {url}: {result}")
            elif result is None:
                logger.warning(f"No content returned for URL {url}")
            else:
                try:
                    if local_mode:
                        headers_to_split_on = [
                            ("#", "Header 1"),
                            ("##", "Header 2"),
                            ("###", "Header 3"),
                        ]
                        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
                        
                        if split:
                            split_docs = markdown_splitter.split_text(result)
                        else:
                            split_docs = [Document(page_content=result)]
                        for i, d in enumerate(split_docs):
                            split_docs[i].metadata['source'] = url
                            split_docs[i].metadata['url'] = url
                        docs.extend(split_docs)
                    else:
                        doc = Document(result)
                        doc.metadata['source'] = url
                        docs.append(doc)
                    logger.info(f"Successfully processed and added document(s) for URL: {url}")
                except Exception as e:
                    logger.error(f"Error creating Document(s) for URL {url}: {e}")
    logger.info(f'Total URLs processed: {len(docs)}')
    return docs

def youtube_transcript_response(query, task, model,n=3):
    overall_context = ''
    if "youtube.com" in query:
        try:
            md = MarkItDown(enable_plugins=False) # Set to True to enable plugins
            result = md.convert(query)
            prompt = result.text_content 
        except:
            try:
                video_id = query.split("=")[1]
                srt = YouTubeTranscriptApi.get_transcript(video_id)
                transcript = ' '.join([s['text'] for s in srt])
                prompt = prompts['youtube_summary_prompt'].format(task=task, transcript=transcript)
            except Exception as e:
                logger.error(f"Error summarizing URL {url}: {e}")
                return "Error generating summary."
        response = model.invoke(prompt)
        overall_context = overall_context + f"\n\nVideo: {query}\nTranscript Summary: {response}\n\n"
    else:
        
        videos = json.loads(YoutubeSearch(query, max_results=10).to_json())['videos'][:n]
        for k in videos:
            video_id = k['id']
            title = k['title']  
            channel = k['channel']
            url = f"https://www.youtube.com/watch?v={video_id}"
            logger.info(f"Found YouTube video: {title} by {channel} at {url}")
            try:
                md = MarkItDown(enable_plugins=False) # Set to True to enable plugins
                result = md.convert(url)
                prompt = result.text_content 
            except:
                try:
                    srt = YouTubeTranscriptApi.get_transcript(video_id)
                    transcript = ' '.join([s['text'] for s in srt])
                    prompt = prompts['youtube_summary_prompt'].format(task=task, transcript=transcript)
                except:
                    logger.error("error with youtube video")
            try:
                response = model.invoke(prompt)
            except:
                logger.error("error with LLM")
            overall_context += f"\n\nVideo: {title} by {channel}\nURL: {url}\nTranscript Summary: {response}\n\n"
    print(f"Generated YouTube context for query '{query}': {overall_context}")
    return overall_context

def generate_doc_hash(text):
    """
    Generates a hash for the input document text.

    Args:
        text (str): The text of the document.

    Returns:
        str: The generated SHA256 hash of the document.
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

async def summary_of_url(query, url, model, local_mode=False):
    """
    Generates a summary of the content at the specified URL or local file path.

    Args:
        query (str): The query string to use for summarization.
        url (str): The URL or local file path to summarize.
        model: The language model to use for generating the summary.
        local_mode (bool, optional): If True, treat url as a local file. Defaults to False.

    Returns:
        str: The generated summary of the content.
    """
    try:
        docs = []
        if local_mode:
            urls = get_all_paths(url)
        else:
            urls = [url]
        for url in urls:
            docs.extend(await urls_to_docs([url], local_mode=local_mode))
        if not docs:
            logger.warning(f"No documents found for URL: {url}")
            return "No content found to summarize."
        content= ''
        for d in docs:
            content = content + 'source:' + url  + '\n\ncontent:' + d.page_content
        summary = model.invoke(f"Summarise the following content to answer {query}:\n{content}")
        return summary.content
    except Exception as e:
        logger.error(f"Error summarizing URL {url}: {e}")
        return "Error generating summary."
    
def is_file_folder(root_path):
    root = Path(root_path)
    if not root.exists():
        return "Not a valid path"
    if root.is_file():
        return "File"
    elif root.is_dir():
        return "Folder"
    else:
        return "Unknown"
    
def get_all_paths(root_path):
    paths = []
    type = is_file_folder(root_path)
    if type=='Folder':
        for dirpath, dirnames, filenames in os.walk(root_path):
            # Add directory itself
            paths.append(dirpath)
            # Add all files in this directory
            for filename in filenames:
                paths.append(os.path.join(dirpath, filename))
    elif type=='File':
        paths=[root_path]
    else:
        paths=None
    return paths

async def fetch_html(url, client):
    headers = {
        "User-Agent": (
            "Mozilla/5.0"
        )
    }
    resp = await client.get(url, headers=headers)
    resp.raise_for_status()
    return resp.text

async def extract_clickable_elements(url):
    async with httpx.AsyncClient(timeout=10) as client:
        html = await fetch_html(url, client)
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        # Anchor tags
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True) or a.get('aria-label') or a.get('title')
            href = a['href']
            if text and href and not href.startswith('#'):
                full_url = urljoin(url, href)
                results.append({'title': text, 'url': full_url})

        # Elements with onclick (e.g., location.href)
        for elem in soup.find_all(attrs={"onclick": True}):
            text = elem.get_text(strip=True) or elem.get('aria-label') or elem.get('title')
            onclick = elem['onclick']
            match = re.search(r"location\.href=['\"]([^'\"]+)['\"]", onclick)
            js_url = match.group(1) if match else None
            if text and js_url:
                full_url = urljoin(url, js_url)
                results.append({'title': text, 'url': full_url})

        return results

def bm25_search(elements, query,topk=10):
    def tokenize(text):
        return text.lower().split()
    titles = [el['title'] for el in elements]
    tokenized_corpus = [tokenize(title) for title in titles]
    bm25 = BM25Okapi(tokenized_corpus)
    tokenized_query = tokenize(query)
    scores = bm25.get_scores(tokenized_query)
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    ranked_results = [
        {'title': elements[i]['title'], 'url': elements[i]['url'], 'score': scores[i]}
        for i in ranked_indices if scores[i] >= 0
    ]
    return ranked_results[:topk]

async def get_topk_bm25_clickable_elements(url, query, topk=10):
    elements = await extract_clickable_elements(url)
    ranked = bm25_search(elements, query, topk)
    return ranked
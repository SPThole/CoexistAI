from utils.websearch_utils import *
from utils.reddit_utils import *
from utils.map import * 
from fastapi import FastAPI, Request
from pydantic import BaseModel
from utils.utils import *
from utils.map import *
from utils.git_utils import *
import subprocess
from fastapi_mcp import FastApiMCP
import json
import os
from model_config import *


# Use config values for model and embedding paths
llm_model_name = model_config.get("llm_model_name", 'google/gemma-3-12b')
llm_type = model_config.get("llm_type", 'local')
llm_tools = model_config.get("llm_tools",None)
llm_base_url = openai_compatible.get(model_config['llm_type'], 
                                     'https://api.openai.com/v1')



llm_kwargs = model_config.get("llm_kwargs", {'temperature': 0.1, 
                                            'max_tokens': None, 
                                            'timeout': None, 
                                            'api_key':llm_api_key,
                                            'max_retries': 2})

embed_kwargs = model_config.get("embed_kwargs", {})
embedding_model_name = model_config.get("embedding_model_name", "models/embedding-001")
embed_mode = model_config.get("embed_mode", "gemini")
cross_encoder_name = model_config.get("cross_encoder_name", "BAAI/bge-reranker-base")


if not is_searxng_running():
    subprocess.run([
        "docker", "run", "--rm",
        "-d", "-p", "30:8080",
        "-v", f"{os.getcwd()}/searxng:/etc/searxng",
        "-e", "BASE_URL=http://localhost:30/",
        "-e", "INSTANCE_NAME=my-instance",
        "searxng/searxng"
    ])
else:
    print("SearxNG docker container is already running.")

llm = get_generative_model(
    model_name=llm_model_name,
    type=llm_type,
    base_url=llm_base_url,
    _tools=None,
    kwargs=llm_kwargs
)

hf_embeddings, cross_encoder = load_model(embedding_model_name, 
                                          _embed_mode=embed_mode,
                                          cross_encoder_name=cross_encoder_name,
                                          kwargs=embed_kwargs)

text_splitter = TokenTextSplitter(chunk_size=512, chunk_overlap=128)

searcher = SearchWeb(30)
date, day = get_local_data()
app = FastAPI(title='coexistai')

@app.get('/')
async def root():
    return {"message": "Welcome to CoexistAI!"}

class WebSearchRequest(BaseModel):
    query: str
    rerank: bool = True
    num_results: int = 3
    local_mode: bool = False
    split: bool = True
    document_paths: list[str] = []  # List of paths for local documents

class YouTubeSearchRequest(BaseModel):
    query: str
    prompt: str
    n: int = 1  # Number of videos to summarize, default is 1

class RedditSearchRequest(BaseModel):
    subreddit: str = None
    url_type: str = "hot"
    n: int = 3
    k: int = 1
    custom_url: str = None
    time_filter: str = "all"
    search_query: str = None
    sort_type: str = "relevance"

class MapSearchRequest(BaseModel):
    start_location: Optional[str] = None  # Start location can be a string or None
    end_location: Optional[str] = None  # End location can be a string or None
    pois_radius: int = 500  # Default radius for POIs in meters
    amenities: str = "restaurant|cafe|bar|hotel"  # Default amenities to search for
    limit: int = 3  # Default number of results to return
    task: str = "route_and_pois"  # Default task is to find a route

class WebSummarizeRequest(BaseModel):
    query: str
    url: str
    local_mode: bool = False

class GitTreeRequest(BaseModel):
    repobaseurl: str  

class GitSearchRequest(BaseModel):
    repobaseurl: str 
    parttoresearch: str
    query: str
    type: str

class LocalFolderTreeRequest(BaseModel):
    folder_path:str
    level: str = 'broad-first'
    prefix: str = ''

class ResearchCheckRequest(BaseModel):
    query: str
    toolsshorthand: str  # Default budget for deep research, can be adjusted as needed

class ClickableElementRequest(BaseModel):
    url:str
    query:str
    topk:int=10

@app.post('/clickable-elements', operation_id="get_website_structure")
async def get_website_structure(request: ClickableElementRequest):
    """
    Retrieves the top-k clickable elements from a given URL based on a query.
    This will help you to find out if there are any clickable elements on the page that match the query.
    You can use this to find deeper links since connected pieces of information are often linked together.
    Args:
        url (str): The URL to search for clickable elements.
        query (str): The query to filter the clickable elements.
        topk (int): The number of top clickable elements to return.
    Returns:
        list: A list of dictionaries containing the title, URL, and score of each clickable element.
    """
    return await get_topk_bm25_clickable_elements(request.url, request.query, request.topk)

@app.post('/local-folder-tree', operation_id="get_local_folder_tree")
async def get_local_folder_tree(request: LocalFolderTreeRequest):
    """
    Async Markdown folder tree.
    Args:
        folder_path (str): Root directory.
        level (str):
            - 'full': Show all folders and files, recursively, except hidden/system/cache entries.
            - 'broad-first': Only show immediate (top-level) folders and files (no nesting).
            - 'broad-second': Show top-level folders/files and their immediate child folders/files (two levels, no deeper).
        prefix (str): Indentation (internal)
    Returns:
        str: Markdown tree string
    """
    return await folder_tree(request.folder_path, level=request.level, prefix=request.prefix)

@app.post('/git-tree-search',operation_id="get_git_tree")
async def get_git_tree(request:GitTreeRequest):
   """
    Retrieves and returns the directory tree structure of a GitHub repository or a local Git repository.

    Args:
        url (str): The base URL of the GitHub repository (e.g., 'https://github.com/user/repo')
                   or the path to the local repository on your system.

    Returns:
        str: The directory tree structure as a string.
    """
   return await git_tree_search(request.repobaseurl)

@app.post('/git-search',operation_id="get_git_search")
async def get_git_search(request:GitSearchRequest):
   """
    Fetches the content of a specific part (directory or file) from either and does what asked in users query.
    First use get_git_tree to understand the structure of the repo and which part might be useful to answer users query
    - a GitHub repository (via URL), or
    - a local Git repository (via local path).

    Args:
        base_url (str): The base URL of the GitHub repository (e.g., 'https://github.com/user/repo'),
                        or the local path to the root of the repository.
        part (str): The path inside the repository you wish to access (e.g., 'basefolder/subfolder'). use get_git_tree for getting specific part if needed
        query (str): Users query
        type (str): "Folder" or "file"
    Returns:
        str: Response of the users query based on the content fetched
    """
   content = await git_specific_content(request.repobaseurl,request.parttoresearch,request.type)
   prompt = f"""You are a professional coder, your task is to answer the users query based on the content fetched from git repo
User Query: {request.query}
Fetched Content: {content}
"""

   result = llm.invoke(
        prompt
    )
   return result.content
   
@app.post('/web-search',operation_id="get_web_search")
async def websearch(request: WebSearchRequest):
    """
    Performs a web search and retrieves results, then generates a response based on those results.
    It also throws back the next steps, you should carry out your research until there are no next steps left.
    Args:
        query (str): The input query.
        rerank (bool): Whether to rerank results.
        num_results (int, optional): Number of search results to retrieve. Defaults to 3. (can take values from 1-5)
        document_paths (list of str, optional): List of paths for local documents/folders. Defaults to empty list. for an example [path1,path2,path3]. if different tasks are related to different documents
        local_mode (bool, optional): Whether to process local documents. Defaults to False.
        split (bool, optional): Whether to split documents into chunks. Defaults to True.

    Returns:
        tuple: Generated response, sources, search results, retrieved documents, and context.
    """
    # You may need to adjust these arguments based on your actual setup
    # For demonstration, using None for models and embeddings
    result = await query_web_response(
        query=request.query,
        date=date,
        day=day,
        websearcher=searcher,  # Replace with your actual searcher instance if needed
        hf_embeddings=hf_embeddings,
        rerank=request.rerank,
        cross_encoder=cross_encoder,
        model=llm,
        text_model=llm,
        num_results=min(2,request.num_results),
        document_paths=request.document_paths,
        local_mode=request.local_mode,
        split=request.split
    )
    return "result:" + result[0] + '\n\nsources:' + result[1]

@app.post('/web-summarize', operation_id="get_web_summarize")
async def websummarize(request: WebSummarizeRequest):
    """Generates a summary of a web page based on the provided query and URL.
    Args:
        query (str): The input query.
        url (str): The URL of the web page to summarize.
        model (str): The model to use for summarization.
        local_mode (bool): Whether to process local documents.
    Returns:
        dict: A dictionary containing the generated summary and sources."""
    result = await summary_of_url(
        query=request.query,
        url=request.url,
        model=llm,  # Replace with your actual model if needed
        local_mode=request.local_mode
    )
    return result

@app.post('/youtube-search', operation_id="get_youtube_search")
async def youtube_search(request: YouTubeSearchRequest):
    """Performs a YouTube search and return summaries of it.
    Args:
        query (str): The YouTube video URL if provided else search term
        prompt (str): The prompt to generate a response from the transcript.
        n (int): Number of videos to summarize if search term is provided instead of URL.
    Returns:
        dict: response from the YouTube transcripts based on the given query"""
    # You may need to adjust the model argument as per your setup
    result = youtube_transcript_response(
        request.query,
        request.prompt,
        n = request.n, #number of videos to summarise
        model=llm  # Replace with your actual model if needed
    )
    return result

@app.post('/reddit-search', operation_id="get_reddit_search")
async def reddit_search(request: RedditSearchRequest):
    """Performs a Reddit search and retrieves posts based on the provided parameters.
    Args:
        subreddit (str): The subreddit to search in. When search_query is provided
        url_type (str): The type of Reddit URL to fetch (e.g., 'search','hot', 'new','top','best','controversial','rising').
                        set to 'search' if specific search_query is provided
        n (int): Number of posts to retrieve.
        k (int): Number of comments on each post to return after processing. When more perspectives needed increase this.
        custom_url (str): Custom URL for Reddit search.
        time_filter (str): Time filter for the search (e.g., 'all', 'day').
        search_query (str): Search query for Reddit posts.
        sort_type (str): Sorting type for the results.
        Returns:                                            
            dict: A dictionary containing the results of the Reddit search."""  
    # You may need to adjust the model argument as per your setup
    if request.search_query:
        request.url_type = 'search'
    result = reddit_reader_response(
        subreddit=request.subreddit,
        url_type=request.url_type,
        n=request.n,
        k=request.k,
        custom_url=request.custom_url,
        time_filter=request.time_filter,
        search_query=request.search_query,
        sort_type=request.sort_type,
        model=llm  # Replace with your actual model if needed
    )
    return result

@app.post('/map-search', operation_id="get_map_search")
async def map_search(request: MapSearchRequest):
    """Performs a map search and retrieves the route and points of interest like  (POIs) between two locations.
    Args:
        start_location (optional str): The starting location for the route. can be None as well
        end_location (optional str): The destination location for the route.can be None as well
        pois_radius (int): Radius in meters to search for points of interest around the route.
        amenities (str): Types of amenities to search for, separated by '|'. For example, "restaurant|cafe|bar|hotel".
        limit (int): Maximum number of POIs to return.
        task (str): The task to perform, either "location_only" - if lat long of start and end location is needed,
            else by default is "route_and_pois" - if route and POIs are needed.
    Returns:
        dict: location or route and POIs or both"""
    result = generate_map(request.start_location,
                        request.end_location,
                        pois_radius=request.pois_radius,
                        amenities=request.amenities,
                        limit=request.limit,
                        task=request.task,
                        )
    return result

@app.post('/check-response', operation_id="get_response_check")
async def check_response(request: ResearchCheckRequest):
    """
    Evaluates whether the agent's collected information is complete for writing answer to the user's query. 
    If any aspect is missing, list them all in bullet format
    Args:
        query (str): The user's original query.
        toolsshorthand (str):  Exact Facts/Information collected in bullets from every past tool usage which would be useful to answer
    Returns:
        str: Suggestions for improvement or confirmation that all aspects are addressed.
    """
    system_prompt = f"""You are a professional researcher.
Review the following user query and the agent's short hand of informations collected. 
If not explicitly asked for deep research, you should just check if most necessary information and all aspects present in query are covered, NO NEED TO SUGGEST EXTRA, SINCE ITS QUICK QUERY
Determine if the shorthand fully addresses every aspect and intent of the query.
If any part is missing or could be improved, list the specific aspects or suggestions for further research or value addition.(IF DEEP RESEARCH ASKED EXPLICITLY)
If the response is complete, state that all aspects have been addressed.

User Query: {request.query}
Agent Shorthand: {request.toolsshorthand}
"""

    result = llm.invoke(
        system_prompt
    )
    return result.content

mcp = FastApiMCP(app,include_operations=['get_web_search',
                                         'get_web_summarize',
                                         'get_youtube_search',
                                         'get_reddit_search',
                                         'get_map_search',
                                         "get_git_tree",
                                         "get_git_search",
                                         "get_local_folder_tree",
                                         "get_response_check",
                                         "get_website_structure"
                                         ],)
mcp.mount()
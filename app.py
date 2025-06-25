from utils.websearch_utils import *
from utils.reddit_utils import *
from utils.map import * 
from fastapi import FastAPI, Request
from pydantic import BaseModel
from utils.utils import *
import subprocess

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

# Local LLMs are supported via OpenAI route, more support will be added soon..
if not os.environ['GOOGLE_API_KEY']: # If its already set via export, it won't override
    os.environ['GOOGLE_API_KEY'] = "YOUR_API_KEY"

llm = get_generative_model(model_name='gemini-2.0-flash',
                    type='google',
                    _tools=None,
                    kwargs={'temperature': 0.1, 'max_tokens': None, 'timeout': None, 'max_retries': 2, 
                            'api_key': os.environ['GOOGLE_API_KEY']})

text_splitter = TokenTextSplitter(chunk_size=512, chunk_overlap=128)
hf_embeddings, cross_encoder = load_model("models/embedding-001",_embed_mode='gemini')
searcher = SearchWeb(30)

app = FastAPI(title='coexistai')

@app.get('/')
async def root():
    return {"message": "Welcome to CoexistAI!"}

class WebSearchRequest(BaseModel):
    query: str
    date: str
    day: str
    rerank: bool = False
    num_results: int = 3
    local_mode: bool = False
    split: bool = True
    document_paths: list = []

class YouTubeSearchRequest(BaseModel):
    url: str
    prompt: str

@app.post('/websearch')
async def websearch(request: WebSearchRequest):
    # You may need to adjust these arguments based on your actual setup
    # For demonstration, using None for models and embeddings
    result = await query_web_response(
        query=request.query,
        date=request.date,
        day=request.day,
        websearcher=searcher,  # Replace with your actual searcher instance if needed
        hf_embeddings=hf_embeddings,
        rerank=request.rerank,
        cross_encoder=cross_encoder,
        model=llm,
        text_model=llm,
        num_results=request.num_results,
        document_paths=request.document_paths,
        local_mode=request.local_mode,
        split=request.split
    )
    return {"result": result}

@app.post('/youtube-search')
async def youtube_search(request: YouTubeSearchRequest):
    # You may need to adjust the model argument as per your setup
    result = youtube_transcript_response(
        request.url,
        request.prompt,
        model=llm  # Replace with your actual model if needed
    )
    return {"result": result}

class RedditSearchRequest(BaseModel):
    subreddit: str = None
    url_type: str = "hot"
    n: int = 10
    k: int = 5
    custom_url: str = None
    time_filter: str = "all"
    search_query: str = None
    sort_type: str = "relevance"

@app.post('/reddit-search')
async def reddit_search(request: RedditSearchRequest):
    # You may need to adjust the model argument as per your setup
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
    return {"result": result}
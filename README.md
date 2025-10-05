# CoexistAI

CoexistAI is a modular, developer-friendly research assistant framework. It enables you to build, search, summarize, and automate research workflows using LLMs, web search, Reddit, YouTube, git and mapping tools—all with simple API calls or Python functions.

<p align="center">
  <img src="artifacts/logo.jpeg" alt="CoexistAI Logo" width="200"/>
</p>

## 🎙️ New Features & Updates
-  🔥 _Docker Installation available (Thanks for all the feedback, hope this makes installations easy)_. For a containerized setup with Docker, follow the instructions in [README.docker.md](README.docker.md).
- **Text → Podcast**: Instantly turn written content into engaging podcast episodes—ideal for on-the-go listening or repurposing articles/notes/blogs. Example: Converted [this article](https://www.theatlantic.com/newsletters/archive/2025/08/ai-high-school-college/684057/) to a podcast. **[Listen here](output/podcasts/podcast_58fc33d6.wav)**
- **Text → Speech**: Convert text to high-quality audio using advanced TTS. Check [Notebook](coexist_tutorial.ipynb) for examples.
- **Flexible Integration**: Generate audio files via FastAPI or MCP—integrate with agents or use standalone.
- **Direct Location Search**: Search for any place, not just routes.
- **Advanced Reddit Search**: Custom phrases with BM25 ranking for sharper discovery.
- **YouTube Power-Up**: Search/summarize videos or URLs with custom prompts.
- **File/Folder Exploration**: Explore local folders/files with vision support for images (.png, .jpg, etc.).
- **Sharper Web Search**: More focused, actionable results.
- **MCP Support Everywhere**: Full integration with LM Studio and other MCP hosts. [See Guide](README_MCP.md)
- **GitHub & Local Repo Explorer**: Ask questions about codebases (GitHub or local).

## 🚀 Features

- **Web Explorer**: Query the web, summarize results, and extract context using LLMs.
- **Reddit Explorer**: Fetch and summarize reddit via search phrase or subreddit focused queries
- **YouTube Transcript Explorer**: Search youtube with search phrases and summarise/QA any video
- **Map Explorer**: Generate maps, explore routes, locations with points of interest like hotels, cafes near given locations.
- **Github Explorer**: Explore/summarise/explain/QA any github or even local git codebases
- **Pluggable LLMs and Embedders**: Use any LLMs Google Gemini, OpenAI, Ollama, and any embedders
- **Async & Parallel**: Fast, scalable, and robust asynchronous execution.
- **Notebook & API Ready**: Use as a Python library or via a FAST API.
- **MCP ready**: Spins up the MCP server on the fly along with FAST API server

---

## 🛠️ Installation
**Prerequisite:** Make sure Docker is installed and the Docker daemon is running.

### Method 1: Docker (Recommended) New 🔥 
For a containerized setup with Docker, follow the instructions in [README.docker.md](README.docker.md). This method uses Method A (helper script) to automate the process and provides an Admin UI for easy configuration.

### Method 2: Local Setup
1. **Clone the repository:**
   ```sh
   git clone https://github.com/SPThole/CoexistAI.git coexistai
   cd coexistai
   ```

2. **Configure your model and embedding settings:**
   
   - [NEW] Edit `config/model_config.json` to set your preferred LLM and embedding model.
   - Edit above file to set your preferred SearxNG host and port (if needed)
   - Add LLM and Embedder API Key (for google mode both would be same)
   - Example (for full local mode):
  
  ```json
  {
  "llm_model_name": "jan-nano", 
  "llm_type": "local", # based on baseurl dict given below
  "embed_mode": "infinity_emb",
  "embedding_model_name": "nomic-ai/nomic-embed-text-v1",
  "llm_kwargs": {
                "temperature": 0.1,
                "max_tokens": null,
                "timeout": null,
                "max_retries": 2
                },
  "embed_kwargs": {},
  "llm_api_key": "dummy",
  "HOST_APP": "localhost",
  "PORT_NUM_APP": 8000,
  "HOST_SEARXNG": "localhost",
  "PORT_NUM_SEARXNG": 8080,
  "openai_compatible": {
                "google": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "local": "http://localhost:1234/v1",
                "groq": "https://api.groq.com/openai/v1",
                "openai": "https://api.openai.com/v1",
                "others": "https://openrouter.ai/api/v1"
                  }
  }
  ```
   - See the file for all available options and defaults.
   - If you using others llm type, then check the openai_compatible url dict for others key, you can generally find it by "googling YOUR provider name openai api base compatilble url"

3. **Run the setup script:**
   - For macOS or Linux with zsh:
     ```sh
     zsh quick_setup.sh
     ```
   - For Linux with bash:
     ```sh
     bash quick_setup.sh
     ```

   > The script will:
   > - Pull the SearxNG Docker image
   > - Create and activate a Python virtual environment
   > - **USER ACTION NEEDED** Set your `GOOGLE_API_KEY` (edit the script to use your real key). [Obtain your API key (Currently Gemini, OpenAI and ollama is supported)](https://ai.google.dev/gemini-api/docs/api-key) from your preferred LLM provider. (Only needed when google mode is set, else set in model_config.py)
   > - Start the SearxNG Docker container
   > - Install Python dependencies
   > - Start the FastAPI server

4. **That’s it!**  
   The FastAPI and MCP server will start automatically and you’re ready to go.

**Note:**  
- Make sure Docker, Python 3, and pip are installed on your system.  
- Edit quick_setup.sh to set your real `GOOGLE_API_KEY` before running (needed if using google models) 
- Windows users can use [WSL](https://docs.microsoft.com/en-us/windows/wsl/) or Git Bash to run the script, or follow manual setup steps.

---

### Get Your API Key (optional if you want to use gemini llm/google embedders)

[Obtain your API key (Currently Gemini, OpenAI and ollama is supported)](https://ai.google.dev/gemini-api/docs/api-key) from your preferred LLM provider. Once you have the key, update the `app.py` file or your environment variables as follows:

```python
import os
os.environ['GOOGLE_API_KEY'] = "YOUR_API_KEY"
```

Alternatively, you can set the API key in your shell before starting the server:

```bash
export YOUR_LLM_API_KEY=your-api-key-here
```
> **Note:** For optimal quality and speed, use Google models with `embedding-001` embeddings and Gemini Flash models. They provide free API keys.

Update the place (default: India) in utils/config.py for personalized results

## 🔧 How to use FASTAPI/tools
**Remove comments after // before pasting**
Swagger UI: http://127.0.0.1:8000/docs  if you haven't changed the host and port

### 1. Web Search
**Search the web, summarize, and get actionable answers—automatically.**

**Endpoint:**  
POST `/web-search`

**Request Example:**
```json
{
  "query": "Top news of today worldwide", // Query you want to ask; if you provide a URL and ask to summarise, it will summarize the full page.
  "rerank": true, // Set to true for better result ranking.
  "num_results": 2, // Number of top results per subquery to explore (higher values = more tokens, slower/more costly).
  "local_mode": false, // Set to true to explore local documents (currently, only PDF supported).
  "split": true, // Set to false if you want full pages as input to LLMs; false may cause slower/more costly response.
  "document_paths": [] // If local_mode is true, add a list of document paths, e.g., ["documents/1706.03762v7.pdf"]
}

```

or QA/sumamrise local documents 

```json
{
  "query": "Summarise this research paper",
  "rerank": true,
  "num_results": 3,
  "local_mode": true,
  "split": true,
  "document_paths": ["documents/1706.03762v7.pdf"] // Must be a list.
}
```

---

### 2. Summarize Any Web Page
**Summarize any article or research paper by URL.**

**Endpoint:**  
POST `/web-summarize`

**Request Example:**
```json

{
  "query": "Write a short blog on the model", // Instruction or question for the fetched page content.
  "url": "https://huggingface.co/unsloth/Qwen3-8B-GGUF", // Webpage to fetch content from.
  "local_mode": false // Set to true if summarizing a local document.
}

```

---

### 3. YouTube Search 
**Search YouTube (supports prompts and batch).**

**Endpoint:**  
POST `/youtube-search`

**Request Example:**
```json

{
  "query": "switzerland itinerary", // Query to search on YouTube; if a URL is provided, it fetches content from that URL. url should be in format: https://www.youtube.com/watch?v=videoID
  "prompt": "I want to plan my Switzerland trip", // Instruction or question for using the fetched content.
  "n": 2 // Number of top search results to summarize (only works if query is not a URL).
}
```

---

### 4. Reddit Deep Dive
**Custom Reddit search, sort, filter, and get top comments.**

**Endpoint:**  
POST `/reddit-search`

**Request Example:**
```json

{
  "subreddit": "", // Subreddit to fetch content from (use if url_type is not 'search').
  "url_type": "search", // 'search' for phrase search; "url" for url, otherwise, use 'hot', 'top', 'best', etc.
  "n": 3, // Number of posts to fetch.
  "k": 1, // Number of top comments per post.
  "custom_url": "", // Use if you already have a specific Reddit URL.
  "time_filter": "all", // Time range: 'all', 'today', 'week', 'month', 'year'.
  "search_query": "gemma 3n reviews", // Search phrase (useful if url_type is 'search').
  "sort_type": "relevance" // 'top', 'hot', 'new', 'relevance' — controls how results are sorted.
}

```

---

### 5. Map & Location/Route Search
**Find places, routes, and nearby points of interest.**

**Endpoint:**  
POST `/map-search`

**Request Example:**
```json

{
  "start_location": "MG Road, Bangalore", // Starting point.
  "end_location": "Lalbagh, Bangalore", // Destination.
  "pois_radius": 500, // Search radius in meters for amenities.
  "amenities": "restaurant|cafe|bar|hotel", // Amenities to search near start or end location.
  "limit": 3, // Maximum number of results if address not found exactly.
  "task": "route_and_pois" // Use 'location_only' for address/coordinates only, or 'route_and_pois' for routes and POIs.
}
```

OR search for any single location (open street map has api rate limit)

```json

{
  "start_location": "MG Road, Bangalore",
  "end_location": "Lalbagh, Bangalore",
  "pois_radius": 500,
  "amenities": "restaurant|cafe|bar|hotel",
  "limit": 3,
  "task": "location_only"
}

```

---

### 6. GitHub & Local Repo Directory Tree
**Get the directory structure of any GitHub or local repo.**

**Endpoint:**  
POST `/git-tree-search`

**Request Example:**
```json

{
  "repobaseurl": "https://github.com/SPThole/CoexistAI/" // Base URL of the repository to explore.
}
```
or for local repo:
```json

{
"repobaseurl": "/home/user/projects/myrepo"
}

```

---

### 7. Ask Questions or Search Inside GitHub/Local Code
**Fetch, search, and analyze code in any repo.**

**Endpoint:**  
POST `/git-search`

**Request Example:**
```json

{
  "repobaseurl": "https://github.com/google-deepmind/gemma", // Base URL of the repository.
  "parttoresearch": "research/t5gemma/t5gemma.py", // Folder or file path relative to the base URL.
  "query": "explain t5gemma", // Instruction or question to answer from the file/folder.
  "type": "file" // Either 'file' or 'folder'.
}
```
or:
```json

{
"repobaseurl": "https://github.com/openai",
"parttoresearch": "openai-cookbook/examples/mcp",
"query": "Write a medium blog, for beginners",
"type": "folder"
}

```
---

## 🧑‍💻 Usage in Python (use method 2 install else use requests to hit fastapi endpoints)
- [see example notebook](coexist_tutorial.ipynb)

- [Example Usage patterns](demo_queries.ipynb)

```python
from utils.websearch_utils import query_web_response
from utils.reddit_utils import reddit_reader_response

# Web Exploration
result = await query_web_response(
  query="latest AI research in the last 7 days",
  date="2025-07-08",
  day="Tuesday",
  websearcher=searcher, #Searxng 
  hf_embeddings=hf_embeddings,#embedder
  rerank=True,
  cross_encoder=cross_encoder,#reranker
  model=llmgoogle, #replace with llm
  text_model=llmgoogle,#replace with llm
  num_results=1,#topk results for each subquery
  document_paths=[],
  local_mode=False, # True if you have local files in document_paths
  split=True
)

result = await query_web_response(
  query="summarise in the form of linkedin post https://modelcontextprotocol.io/introduction",
  date="2025-07-08",
  day="Tuesday",
  websearcher=searcher, #Searxng 
  hf_embeddings=hf_embeddings,#embedder
  rerank=True,
  cross_encoder=cross_encoder,#reranker
  model=llmgoogle, #replace with llm
  text_model=llmgoogle,#replace with llm
  num_results=1,#topk results for each subquery
  document_paths=[],
  local_mode=False, # True if you have local files in document_paths
  split=True
)

##  Reddit Exploration
summary = reddit_reader_response(
  subreddit="",
  url_type="search",
  n=5,
  k=2,
  custom_url=None,# Replace with llm
  time_filter="month",
  search_query="Gemma 3N reviews",
  sort_type="relevance",
  model=llmgoogle
)

## Map Exploration
from utils.map import generate_map
# Generate a map with route and POIs
html_path = generate_map("MG Road, Bangalore", "Indiranagar, Bangalore", 500, "hotel", 3)
locations = generate_map("MG Road, Bangalore", "Indiranagar, Bangalore", 500, "", 3,"location_only")

## Youtube Exploration
from utils.websearch_utils import *
learnings = youtube_transcript_response("https://www.youtube.com/watch?v=DB9mjd-65gw",
                            "Summarise this podcast and share me top learnings as a data scientist",
                            llmgoogle)

podcast = youtube_transcript_response("History of India top 5 interesting facts",
                            "Make a podcast of this in Hindi, 5 minutes long",
                            llmgoogle,
                            1)

## Git exploration
from utils.git_utils import *
tree = await git_tree_search("https://github.com/SPThole/CoexistAI")
content = await git_specific_content("https://github.com/SPThole/CoexistAI","README.md","file")
```

---

## 🤖 Advanced Patterns & Extensibility

- **Plug in your own LLMs**: Swap out Google Gemini for OpenAI, Ollama, or any LangChain-supported model.
- **Custom Tools**: Add your own tools to the agent system for new capabilities (see `utils/` for examples).
- **Async/Parallel**: All web and document search utilities are asynchronous for high performance.
- **MCP Servers**: Connect your local apps like lmstudio with coexistAI MCP server, all local

---

## 🤝 Contributing

Pull requests, issues, and feature suggestions are welcome! Please open an issue or PR on GitHub.

---

## ⚖️ Legality & Responsible Use

**Non-Commercial Use Only:** CoexistAI is intended strictly for research, prototyping, and educational purposes. Commercial or production use of this project or its outputs is **not permitted**.

**Web and Reddit Data:** CoexistAI uses public web scraping and Reddit JSON endpoints. It does not use the official Reddit API. Always respect robots.txt, site terms, and copyright law when using this tool.

**YouTube & Other Sources:** Use responsibly and in accordance with the terms of service of each data provider.

**Compliance:** You are responsible for ensuring your use of this tool complies with all relevant terms, conditions, and laws.

---

## 📄 License
This project is licensed under a custom Non-Commercial Research and Educational Use License. Use of this software is permitted only for non-commercial research, prototyping, and educational purposes. Commercial or production use is strictly prohibited. See the LICENSE file for full terms and conditions.

---

## ⭐ Star & Share
If you find this project useful, please star the repo and share it with your network!

---

## 📬 Contact

For questions, reach out via GitHub Issues or open a discussion.


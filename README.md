# CoexistAI

CoexistAI is a modular, developer-friendly research assistant framework built on FastAPI and LangChain. It enables you to build, search, summarize, and automate research workflows using LLMs, web search, Reddit, YouTube, and mapping tools—all with simple API calls or Python functions.

<p align="center">
  <img src="artifacts/logo.jpeg" alt="CoexistAI Logo" width="200"/>
</p>

## New Updates: Read More about updates [Here](README_MCP.md)

- **Smarter, cheaper prompts:** Built-in guardrails help you save API costs with smarter prompt handling, especially for paid LLMs. Max documents limits of summarization.
- **Direct location search:** You can now search for any place, not just find routes!
- **Advanced Reddit search:** Use your own phrases; results ranked better with BM25 for sharper discovery.
- **YouTube power-up:** Search and summarize YouTube using your own search or video URLs and even add a prompt for custom responses.
- **Sharper web search:** More focused and actionable results than ever before.
- **MCP support everywhere:** Now fully connect coexistai to LM Studio and other MCP hosts—seamless integration! (See Guide Below)
- **GitHub & local repo explorer:** Explore directory trees or ask questions about code—works with both GitHub and local repos!


## 🚀 Features

- **Web Search API**: Query the web, summarize results, and extract context using LLMs.
- **Reddit Summarizer**: Fetch and summarize top posts and comments from any subreddit.
- **YouTube Transcript Summarizer**: Summarize YouTube videos by extracting transcripts.
- **Map & Route Generation**: Generate maps and routes with points of interest.
- **Pluggable LLMs**: Use Google Gemini, OpenAI, Ollama, and more.
- **Async & Parallel**: Fast, scalable, and robust asynchronous execution.
- **Notebook & API Ready**: Use as a Python library or via a FAST API.

---

## 🛠️ Installation

### METHOD 1 (Less flexible but faster):

1. **Clone the repository:**
   ```sh
   git clone https://github.com/SPThole/CoexistAI.git coexistai
   cd coexistai
   ```

2. **Run the setup script:**
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
   > - Set your `GOOGLE_API_KEY` (edit the script to use your real key). [Obtain your API key (Currently Gemini, OpenAI and ollama is supported)](https://ai.google.dev/gemini-api/docs/api-key) from your preferred LLM provider.
   > - Start the SearxNG Docker container
   > - Install Python dependencies
   > - Start the FastAPI server

3. **That’s it!**  
   The FastAPI server will start automatically and you’re ready to go.

**Note:**  
- Make sure Docker, Python 3, and pip are installed on your system.  
- Edit quick_setup.sh to set your real `GOOGLE_API_KEY` before running.  
- Windows users can use [WSL](https://docs.microsoft.com/en-us/windows/wsl/) or Git Bash to run the script, or follow manual setup steps.

---

## Method 2: Tedious but gives flexibility

1. Clone repo
```bash
# Clone the repo
git clone https://github.com/SPThole/CoexistAI.git
cd CoexistAI

# Install dependencies
pip install -r requirements.txt
```

🔎 SearxNG Setup:

CoexistAI can use a local or remote [SearxNG](https://github.com/searxng/searxng) instance for privacy-friendly, customizable web search aggregation.

### Install SearxNG (Docker recommended)


```bash
docker pull docker.io/searxng/searxng:latest
```

- By default, SearxNG will be available at `http://localhost:8080`.
- You can edit `settings.yml` for advanced configuration (see `searxng/settings.yml` in this repo for a template).
- if not just copy the folder searxng from this repo, at the same relative location in your machine

3. Run the following command: 
```bash
docker run --rm \
       -d -p 30:8080 \
       -v "${PWD}/searxng:/etc/searxng" \
       -e "BASE_URL=http://localhost:$PORT/" \
       -e "INSTANCE_NAME=my-instance" \
       searxng/searxng
```

4. Use SearxNG in Your Queries

- The web search utilities will automatically use your configured SearxNG instance for search aggregation.
- For best results, ensure SearxNG is running before starting the FastAPI server or using the Python API.

5.  Enabling API

### Start the FastAPI server

```bash
uvicorn app:app --reload
```

If using local infinity embedding server (https://github.com/michaelfeil/infinity):

```bash
infinity_emb v2 --model-id hf_model_name
```

### Get Your API Key

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

### Web Search Endpoint

### 1. Web Search
**Search the web, summarize, and get actionable answers—automatically.**

**Endpoint:**  
POST `/web-search`

**Request Example:**
```

{
  "query": "Top news of today worldwide",
  "rerank": true,
  "num_results": 3,
  "local_mode": false,
  "split": true,
  "document_paths": []
}

```

or QA/sumamrise local documents 

```
{
  "query": "Summarise this research paper",
  "rerank": true,
  "num_results": 3,
  "local_mode": true,
  "split": true,
  "document_paths": [["documents/1706.03762v7.pdf"]] # has to be list of list
}

```

---

### 2. Summarize Any Web Page
**Summarize any article or research paper by URL.**

**Endpoint:**  
POST `/web-summarize`

**Request Example:**
```

{
  "query": "Write a short blog on the model",
  "url": "https://huggingface.co/unsloth/Qwen3-8B-GGUF",
  "local_mode": false
}

```

---

### 3. YouTube Search 
**Search YouTube (supports prompts and batch).**

**Endpoint:**  
POST `/youtube-search`

**Request Example:**
```

{
  "query": "switzerland itinerary",
  "prompt": "I want to plan my switzerland trip",
  "n": 2 # top n searches to summarise 
}
```

---

### 4. Reddit Deep Dive
**Custom Reddit search, sort, filter, and get top comments.**

**Endpoint:**  
POST `/reddit-search`

**Request Example:**
```

{
  "subreddit": "",
  "url_type": "search",
  "n": 3,
  "k": 1,
  "custom_url": "",
  "time_filter": "all",
  "search_query": "gemma 3n reviews",
  "sort_type": "relevance"
}

```

---

### 5. Map & Location/Route Search
**Find places, routes, and nearby points of interest.**

**Endpoint:**  
POST `/map-search`

**Request Example:**
```

{
  "start_location": "MG Road, Bangalore",
  "end_location": "Lalbagh, Bangalore",
  "pois_radius": 500,
  "amenities": "restaurant|cafe|bar|hotel",
  "limit": 3,
  "task": "route_and_pois"
}

```

OR search for any single location (open street map has api rate limit)

```

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
```

{
  "repobaseurl": "https://github.com/SPThole/CoexistAI/"
}

```
or for local repo:
```

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
```

{
"repobaseurl": "https://github.com/google-deepmind/gemma",
"parttoresearch": "gemma/research/t5gemma/t5gemma.py",
"query": "explain t5gemma",
"type": "file"
}

```
or:
```

{
"repobaseurl": "https://github.com/openai",
"parttoresearch": "openai-cookbook/examples/mcp",
"query": "Write a medium blog, for beginners",
"type": "folder"
}

```
---

## 🧑‍💻 Usage in Python

```python
from utils.websearch_utils import query_web_response
from utils.reddit_utils import reddit_reader_response

# Web search
result = await query_web_response(
  query="latest AI research",
  date="2025-05-28",
  day="Wednesday",
  websearcher=None,
  hf_embeddings=None,
  rerank=False,
  cross_encoder=None,
  model=None, #replace with llm
  text_model=None,
  num_results=3,
  document_paths=[],
  local_mode=False, # True if you have local files in document_paths
  split=True
)

# Reddit summarization
summary = reddit_reader_response(
  subreddit="OpenAI",
  url_type="hot",
  n=5,
  k=3,
  custom_url=None,# Replace with llm
  time_filter="all",
  search_query=None,
  sort_type="relevance",
  model=None
)
```

---

## 🌍 Example: Map Generation

```python
from utils.map import generate_map
# Generate a map with route and POIs
html_path = generate_map("MG Road, Bangalore", "Indiranagar, Bangalore", 500, "hotel", 3)
```

---

## 📚 Notebooks

- The Coexist tutorial can be found in `coexist_tutorial.ipynb`.

---

## 🤖 Advanced Patterns & Extensibility

- **Plug in your own LLMs**: Swap out Google Gemini for OpenAI, Ollama, or any LangChain-supported model.
- **Custom Tools**: Add your own tools to the agent system for new capabilities (see `utils/` for examples).
- **Async/Parallel**: All web and document search utilities are asynchronous for high performance.

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


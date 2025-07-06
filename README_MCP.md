# coexistai v0.0.2 – What's New & How to Use

<p align="center">
  <img src="artifacts/v002mcplogo.jpeg" alt="CoexistAI MCP Logo" width="200"/>
</p>


## 🚀 What's New in v2

- **Smarter, cheaper prompts:** Built-in guardrails help you save API costs with smarter prompt handling, especially for paid LLMs. Max documents limits of summarization.
- **Direct location search:** You can now search for any place, not just find routes!
- **Advanced Reddit search:** Use your own phrases; results ranked better with BM25 for sharper discovery.
- **YouTube power-up:** Search and summarize YouTube using your own search or video URLs and even add a prompt for custom responses.
- **Sharper web search:** More focused and actionable results than ever before.
- **MCP support everywhere:** Now fully connect coexistai to LM Studio and other MCP hosts—seamless integration! (See Guide Below)
- **GitHub & local repo explorer:** Explore directory trees or ask questions about code—works with both GitHub and local repos!

---

## 🔍 What Can You Do? (API Highlights & Examples)

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

### 🧑‍💻 Integrate coexistai as an MCP Server (LM Studio, Cursor, etc.)

Starting LM Studio 0.3.17, LM Studio acts as an Model Context Protocol (MCP) Host. This means you can connect MCP servers to the app and make them available to your models. 


You can now run coexistai as an MCP server—**plug it into LM Studio** or any other MCP-compatible tool!

### How to Integrate with LM Studio

1. Download lm studio> 0.3.17 (https://lmstudio.ai/docs/app)

2. Find the [MCP guide](https://lmstudio.ai/docs/app/plugins/mcp)

<p align="center">
  <img src="artifacts/lmstudio.png" alt="CoexistAI MCP Logo" width="600"/>
</p>

1. **Edit your `mcp.json` in LM Studio:**
    - Go to the Program tab → `Install > Edit mcp.json`
    - Add coexistai as a server. Example:
    ```json
    {
        "mcpServers": {
             "coexistai": {
                "url": "http://127.0.0.1:8000/mcp"
        }
    }
    }
    ```
    - Replace with your actual server address and token (if needed).

2. **Or use an "Add to LM Studio" button** (if provided on coexistai website).

**Security note:** Only use MCP servers you trust—servers can access files/network.

---

## 🏆 Best Local Model

For fastest, highest-quality local LLM results, I have personally liked following:  
**unsloth/Qwen3-8B-GGUF**

---

## 🛠 Quick Start

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
   > - Start the FastAPI and MCP server, BOTH.

3. **That’s it!**  
   The FastAPI and MCP server will start automatically and you’re ready to go.

**Note:**  
- Make sure Docker, Python 3, and pip are installed on your system.  
- Edit quick_setup.sh to set your real `GOOGLE_API_KEY` before running.  
- Windows users can use [WSL](https://docs.microsoft.com/en-us/windows/wsl/) or Git Bash to run the script, or follow manual setup steps.


Let me know if you want further formatting tweaks or more sections!

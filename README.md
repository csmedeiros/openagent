# 🤖 OpenAgent

OpenAgent is a general-purpose AI agent built with [LangGraph](https://langchain-ai.github.io/langgraph/). It combines web research, file system operations, shell execution, and code capabilities into a single autonomous agent — all accessible from an interactive terminal CLI.

---

## 🧰 Tools

OpenAgent (v0.0.2) is a standalone general-purpose agent with the following tools:

### 📋 Task & File Management
| Tool | Description |
|---|---|
| `write_todos` | Create and update a structured task plan (must be used first) |
| `read_file` | Read file contents with line range support |
| `write_file` | Write or append content to files |
| `glob_search` | Find files matching a glob pattern |
| `grep_search` | Search for text across files |
| `shell_tool` | Execute shell commands (60s timeout) |

### 🌐 Web Research & Scraping (via [Scrapling](https://github.com/D4Vinci/Scrapling) MCP)
| Tool | Protection Level | Description |
|---|---|---|
| `search_web` | — | Primary web search via Tavily (use first to discover URLs) |
| `get` | Low / Mid | Fast HTTP GET for standard websites |
| `bulk_get` | Low / Mid | Batch HTTP GET for multiple URLs |
| `fetch` | Mid / High | Playwright-based browser fetch (JS rendering) |
| `bulk_fetch` | Mid / High | Batch Playwright fetch |
| `stealthy_fetch` | High (Cloudflare) | Stealth browser fetch for bot-protected sites |
| `bulk_stealthy_fetch` | High (Cloudflare) | Batch stealth fetch |

> **Scraping tool selection guide:** Start with `get`. If content is missing or blocked, escalate to `fetch`, then `stealthy_fetch`.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Anaconda or a Python virtual environment
- A running **Scrapling MCP server** on `http://localhost:8000/mcp`
- A running **MLflow server** (optional, for tracing)

### Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# Edit .env and add your API keys

# 4. (Optional) Start MLflow for tracing
mlflow server --port 1234

# 5. Start the Scrapling MCP server
# Follow the Scrapling MCP setup instructions

# 6. Run the CLI
cd openagent-core/src/agents
python cli.py
```

### CLI Usage

```bash
python cli.py
```

**Slash commands inside the CLI:**

| Command | Description |
|---|---|
| `/help` | Show available commands |
| `/exit` `/quit` | Exit the CLI |
| `/clear` | Start a fresh conversation thread |
| `/agent <name>` | Switch to another agent |
| `/agents` | List all available agents |
| `/history` | Show message count in current thread |

---

## 📁 Project Structure

```
openagent/
├── openagent-core/
│   └── src/
│       └── agents/
│           ├── openagent.py          # Main agent
│           ├── cli.py               # Interactive terminal CLI
│           ├── models.py            # Centralized LLM configuration
│           ├── prompts/             # System prompts (versioned)
│           │   └── openagent_sys_prompt_v0.0.2.md
│           ├── tools/               # Custom LangChain tools
│           │   ├── scrapling_tools.py   # Scrapling MCP client
│           │   ├── search_web.py        # Tavily web search
│           │   ├── read_file.py
│           │   ├── write_file.py
│           │   ├── run_shell.py
│           │   ├── write_todos.py
│           │   └── playwright_tools/    # Playwright browser tools
│           ├── middleware/          # LangChain middleware (TodoList, Summarization)
│           └── utils/               # Shared utilities (summarization node, logging)
├── requirements.txt
└── .env                             # Environment variables (gitignored)
```

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file at the project root:

```bash
# Azure OpenAI (required)
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/

# LangFuse (optional — for conversation tracing)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Tavily (required for search_web)
TAVILY_API_KEY=tvly-...

# Browser visibility (optional, default: true)
HEADLESS=true
```

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────┐
│                   OpenAgent v0.0.2                 │
│            (General-Purpose Single Agent)          │
│                                                    │
│  Tools:                                            │
│  ┌──────────────┐  ┌────────────────────────────┐  │
│  │  File & Shell │  │  Web (Scrapling MCP)       │  │
│  │  write_todos  │  │  search_web                │  │
│  │  read_file    │  │  get / bulk_get            │  │
│  │  write_file   │  │  fetch / bulk_fetch        │  │
│  │  shell_tool   │  │  stealthy_fetch / bulk     │  │
│  │  glob/grep    │  └────────────────────────────┘  │
│  └──────────────┘                                  │
│                                                    │
│  Infrastructure: LangGraph + MemorySaver           │
│  Summarization: Auto-summarizes long conversations │
└────────────────────────────────────────────────────┘
         │
   ┌─────┴──────┐
   │  CLI (cli.py)│  ← Interactive terminal interface
   └────────────┘
```

The agent graph flow:

```
START → [should_summarize?] → agent → [tools_condition] → tools → [should_summarize?] → agent ...
                    ↓
                summarize → agent
```

---

## 🔒 Security

⚠️ **Important:**
- `shell_tool` executes arbitrary shell commands
- Scraping tools access the public internet
- The working directory is restricted to `~/Documents/openagent_tests/`
- Never run untrusted user input without proper sandboxing in production

---

## 🐛 Troubleshooting

**`Module not found` errors:**
```bash
# Add src to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/openagent-core/src"   # Linux/macOS
set PYTHONPATH=%PYTHONPATH%;openagent-core\src               # Windows
```

**Scrapling tools not loading:**
```
Ensure the Scrapling MCP server is running at http://localhost:8000/mcp
```

**Token counter error (`NoneType has no attribute 'startswith'`):**
```
Set model_name explicitly in models.py or ensure your Azure deployment name
is a recognized OpenAI model name for tiktoken. The summarization node
has a fallback estimator for custom deployments.
```

**MLflow connection error:**
```bash
mlflow server --port 1234
```

---

## 📚 References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Scrapling](https://github.com/D4Vinci/Scrapling)
- [Tavily Search API](https://docs.tavily.com)
- [LangFuse Tracing](https://cloud.langfuse.com)

---

## 📝 License

MIT

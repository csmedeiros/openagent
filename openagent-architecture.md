# OpenAgent — Diagrama Completo da Arquitetura

## 1. Grafo Principal (LangGraph StateGraph)

```
                        ┌─────────────────────────────────────────────┐
                        │           OpenAgentState                    │
                        │  ─────────────────────────────────────────  │
                        │  messages: list[BaseMessage]                │
                        │  files: Annotated[List[str], add]           │
                        │  todos: list[Todo]                          │
                        │  browser_initialized: bool                  │
                        │  is_last_message: bool                      │
                        └─────────────────────────────────────────────┘

                                         │
                                      START
                                         │
                                         ▼
                            ┌────────────────────────┐
                            │    should_summarize     │  ◄── Conditional Edge
                            │  (token count check)    │      Triggers at 100k tokens
                            └────────────────────────┘
                               │                  │
                    tokens < 100k            tokens ≥ 100k
                               │                  │
                               ▼                  ▼
                    ┌──────────────┐    ┌──────────────────┐
                    │              │    │    summarize      │
                    │              │    │  ────────────────  │
                    │              │    │  trim_messages()  │
                    │              │    │  → keep ~20k tok  │
                    │              │    │  → LLM summary    │
                    │              │    └──────────────────┘
                    │              │             │
                    │              │             │ (always)
                    │              │             │
                    │              ▼             ▼
                    │         ┌─────────────────────┐
                    └────────►│       agent          │
                              │  ───────────────────  │
                              │  SystemMessage +     │
                              │    sys_prompt        │
                              │  model.bind_tools()  │
                              │  → claude-sonnet-4-6 │
                              │    (Anthropic Foundry)│
                              └─────────────────────┘
                                   │            │
                          has tool_calls    no tool_calls
                                   │            │
                                   ▼            ▼
                         ┌──────────────┐    ┌──────┐
                         │    tools     │    │ END  │
                         │  (ToolNode)  │    └──────┘
                         └──────────────┘
                                   │
                                   ▼
                      ┌────────────────────────┐
                      │    should_summarize     │  ◄── Re-check after tools
                      └────────────────────────┘
                         │                  │
              tokens < 100k            tokens ≥ 100k
                         │                  │
                         ▼                  ▼
                    ┌─────────┐    ┌──────────────────┐
                    │  agent  │    │    summarize      │ ──► agent
                    └─────────┘    └──────────────────┘
```

## 2. Tools Disponíveis no Nó `agent`

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TOOLS (ToolNode)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─── Filesystem ──────────────────────────────────────────────┐   │
│  │  read_file      Lê arquivo com line numbers (start/end)     │   │
│  │  write_file     Cria/sobrescreve arquivo (append opcional)  │   │
│  │  edit_file      Substitui range de linhas (start_line/      │   │
│  │                 end_line → new_content)                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─── Shell ───────────────────────────────────────────────────┐   │
│  │  shell_tool     Executa comando shell no WORKSPACE_ROOT     │   │
│  │                 (subprocess em thread, timeout 60s)          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─── Web / Research ──────────────────────────────────────────┐   │
│  │  search_web     Busca web via Tavily API (até 10 results)   │   │
│  │  scrapling_*    Tools MCP remotas (localhost:8000/mcp)       │   │
│  │                 → scraping/browser automation                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─── Planning / Output ───────────────────────────────────────┐   │
│  │  write_todos           Cria/atualiza lista de tarefas       │   │
│  │  provide_download_link Gera link file:// clicável           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 3. Infraestrutura de Suporte

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          MODELS (models.py)                              │
│  ────────────────────────────────────────────────────────────────────    │
│  get_model()        → init_chat_model("claude-sonnet-4-6", anthropic)   │
│  get_vision_model() → init_chat_model("claude-sonnet-4-6", anthropic)   │
│  model (LazyProxy)  → get_model() on first access                       │
│                                                                          │
│  Provider: Anthropic Foundry (Azure endpoint)                            │
│  Env: ANTHROPIC_FOUNDRY_BASE_URL / ANTHROPIC_FOUNDRY_API_KEY            │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                    SUMMARIZATION PIPELINE                                 │
│  ────────────────────────────────────────────────────────────────────    │
│  should_summarize()         Conditional edge (≥100k tokens → summarize) │
│  summarize_messages_node()  trim_messages(last, ~20k tokens)            │
│                             + LLM-generated summary of removed messages │
│  token_counter()            model.get_num_tokens / fallback estimator   │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                    MESSAGE TRUNCATION (safety net)                        │
│  ────────────────────────────────────────────────────────────────────    │
│  MAX_CONTEXT_TOKENS = 30k       (hard cap for pre-LLM truncation)       │
│  MAX_SINGLE_MESSAGE_CHARS = 30k (single message cap)                    │
│  group_messages()               Keep AI+ToolMessage pairs together      │
│  truncate_messages()            Group-based tail truncation              │
└──────────────────────────────────────────────────────────────────────────┘
```

## 4. CLI (cli.py)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          CLI REPL                                         │
│  ────────────────────────────────────────────────────────────────────    │
│                                                                          │
│  Agent Registry:                                                         │
│    ├── coder       (agents.coder)       ← não encontrado no repo        │
│    ├── researcher  (agents.researcher)  ← não encontrado no repo        │
│    └── openagent   (agents.openagent)   ← ATIVO                        │
│                                                                          │
│  Streaming: graph.astream_events(v2)                                     │
│    ├── on_chat_model_stream → acumula texto                             │
│    ├── on_tool_start        → Panel com nome + inputs                   │
│    ├── on_tool_end          → Summary (✓/✗)                             │
│    └── final                → Markdown rendered (rich.markdown)          │
│                                                                          │
│  Slash Commands: /help /exit /clear /agent /agents /history              │
│  Checkpointer: MemorySaver (in-memory)                                   │
│  Tracing: MLflow + Langfuse (optional)                                   │
│  Rendering: Rich (Console, Panel, Markdown, Theme)                       │
└──────────────────────────────────────────────────────────────────────────┘
```

## 5. Subagent Delegation (task.py — message tool)

```
                    ┌──────────────┐
                    │  OpenAgent   │
                    │   (agent)    │
                    └──────┬───────┘
                           │
                    calls message()
                    tool with agent=
                    "coder"|"researcher"
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
     ┌────────────────┐       ┌─────────────────┐
     │  Coder Agent   │       │ Researcher Agent │
     │  (subgraph)    │       │   (subgraph)     │
     │                │       │                  │
     │  Receives:     │       │  Receives:       │
     │  - context msg │       │  - context msg   │
     │  - files list  │       │  - files list    │
     │  - state       │       │  - state         │
     │                │       │                  │
     │  Returns:      │       │  Returns:        │
     │  - ToolMessage │       │  - ToolMessage   │
     │  - state merge │       │  - state merge   │
     └────────────────┘       └─────────────────┘

     NOTE: coder/researcher modules not yet in repo.
     The `message` tool is defined but not included
     in the current openagent tools list.
```

## 6. Fluxo Completo de uma Mensagem

```
User Input (CLI)
      │
      ▼
  HumanMessage
      │
      ▼
  should_summarize ──────────► tokens ≥ 100k? ──► summarize ──┐
      │ (no)                                                    │
      ▼                                                         │
    agent  ◄────────────────────────────────────────────────────┘
      │
      ├── SystemPrompt (sys_prompt + FILES + WORKDIR)
      ├── model = claude-sonnet-4-6 (Anthropic Foundry)
      ├── bind_tools([read_file, write_file, edit_file,
      │               shell_tool, write_todos, search_web,
      │               provide_download_link, scrapling_*])
      │
      ▼
  LLM Response
      │
      ├── No tool_calls → is_last_message=True → END
      │                                           │
      │                                     CLI renders
      │                                     Markdown Panel
      │
      └── Has tool_calls → ToolNode executes tools
                              │
                              ▼
                        should_summarize ──► (loop back to agent)
```

## 7. Estrutura de Arquivos

```
openagent/
├── cli.py                                    # CLI REPL principal
├── .env                                      # Credenciais e config
├── openagent-core/
│   └── src/
│       └── agents/
│           ├── openagent.py                  # Grafo principal (StateGraph)
│           ├── models.py                     # Config LLM (Anthropic Foundry)
│           ├── prompts/
│           │   ├── openagent_sys_prompt_v0.0.1.md
│           │   └── openagent_sys_prompt_v0.0.2.md
│           ├── tools/
│           │   ├── __init__.py               # Exports all tools
│           │   ├── read_file.py              # Leitura com line numbers
│           │   ├── write_file.py             # Escrita/append
│           │   ├── edit_file.py              # Edição por range de linhas
│           │   ├── run_shell.py              # Execução de comandos shell
│           │   ├── search_web.py             # Busca Tavily
│           │   ├── scrapling_tools.py        # MCP client (scraping)
│           │   ├── write_todos.py            # Task planning
│           │   ├── provide_download_link.py  # File URI links
│           │   └── task.py                   # Subagent delegation (message)
│           ├── utils/
│           │   ├── message_truncation.py     # Hard-cap truncation
│           │   ├── nodes/
│           │   │   └── summarization_node.py # LLM summarization node
│           │   └── logging/
│           │       └── default_logger.py
│           └── middleware/
│               └── summarization.py
```

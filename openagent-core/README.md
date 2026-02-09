# 🤖 OpenAgent

OpenAgent é um sistema multi-agente com LangGraph + DeepAgents que combina:
- **Researcher**: Agente especializado em pesquisa web com Playwright + Visão
- **Coder**: Agente especializado em escrita e refatoração de código
- **OpenAgent**: Orquestrador principal que delega tarefas aos subagentes

## 🚀 Quick Start

### Desenvolvimento Local

```bash
# 1. Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Instalar Playwright browsers
playwright install chromium

# 4. Configurar environment
cp .env.example .env
# Edite .env e adicione suas API keys

# 5. Executar diretamente
cd src/agents
python openagent.py
```

### LangGraph Server

```bash
# 1. Instalar LangGraph CLI
pip install langgraph-cli

# 2. Iniciar servidor
langgraph dev

# 3. Acessar
# - LangGraph Studio: Abre automaticamente
# - API: http://localhost:8123
```

## 📁 Estrutura do Projeto

```
openagent-core/
├── src/
│   └── agents/
│       ├── openagent.py       # Orquestrador principal
│       ├── researcher.py      # Agente de pesquisa web
│       ├── coder.py          # Agente de código
│       ├── tools/            # Ferramentas customizadas
│       ├── middleware/       # Middleware customizado
│       ├── prompts/          # System prompts
│       └── utils/            # Utilitários
├── requirements.txt         # Python dependencies
├── langgraph.json          # LangGraph Server configuration
└── .env                    # Environment variables (gitignored)
```

## 🔧 Configuração

### Environment Variables

Crie um arquivo `.env` na raiz do projeto:

```bash
# HuggingFace Token (obrigatório)
HF_TOKEN=hf_...

# Groq API (opcional - para modelos alternativos)
GROQ_API_KEY=gsk_...

# LangFuse (opcional - para tracing)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Browser (opcional - default: false)
HEADLESS=false
```

### Obter API Keys

- **HuggingFace**: https://huggingface.co/settings/tokens
- **Groq**: https://console.groq.com/keys
- **LangFuse**: https://cloud.langfuse.com

## 🎯 Uso

### CLI Interativo (Local)

```bash
# OpenAgent (orquestrador)
python src/agents/openagent.py

# Researcher (pesquisa web)
python src/agents/researcher.py

# Coder (desenvolvimento)
python src/agents/coder.py
```

### LangGraph Server

```bash
# 1. Iniciar servidor
langgraph dev

# 2. Acessar interface
# LangGraph Studio abre automaticamente

# 3. API REST
curl http://localhost:8123/graphs
```

### LangSmith Studio

Importe o grafo `openagent` no LangSmith Studio para debugging visual.

## 🧪 Testing

### Testar Researcher

```bash
python src/agents/researcher.py
```

### Testar Coder

```bash
python src/agents/coder.py
```


## 📊 Arquitetura

```
┌─────────────────────────────────────────┐
│          OpenAgent (Orquestrador)       │
│   - create_deep_agent                   │
│   - FilesystemBackend                   │
│   - ShellToolMiddleware                 │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
┌──────▼──────┐  ┌─────▼──────┐
│  Researcher │  │   Coder    │
│  (SubAgent) │  │ (SubAgent) │
├─────────────┤  ├────────────┤
│ • Browser   │  │ • File ops │
│ • Web scraping│ │ • Shell    │
│ • Research  │  │ • Coding   │
└─────────────┘  └────────────┘
```

## 🔒 Segurança

⚠️ **Importante**:
- ShellToolMiddleware executa comandos shell
- Playwright acessa a web
- Nunca execute código não confiável

Para produção, use sandboxing apropriado.

## 📚 Documentação

- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [LangGraph Server](https://langchain-ai.github.io/langgraph/cloud/)
- [DeepAgents Docs](https://github.com/langchain-ai/deepagents)
- [Playwright Python](https://playwright.dev/python/)

## 🐛 Troubleshooting

### "Module not found"
```bash
# Verifique PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### "Chromium not found"
```bash
playwright install chromium
```

### "API Key not found"
```bash
# Verifique .env
cat .env | grep GROQ_API_KEY
```

## 📝 License

MIT

## 🤝 Contributing

Pull requests são bem-vindos!

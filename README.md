# 🤖 OpenAgent


OpenAgent é um sistema multi-agente com LangGraph que combina:
- **OpenAgent**: Orquestrador principal, coordena e delega tarefas entre agentes especialistas.
- **Researcher**: Agente especializado em pesquisa web, scraping e extração de informações usando Playwright (navegação real, extração de texto, interação com páginas, screenshots, etc.).
- **Coder**: Agente especializado em escrita, modificação e análise de código, automação de tarefas, manipulação de arquivos e execução de comandos shell.

### Ferramentas dos Agentes

**OpenAgent**
- Planejamento de tarefas (write_todos)
- Leitura e escrita de arquivos (read_file, write_file)
- Busca por arquivos (glob_search, grep_search)
- Execução de comandos shell (shell_tool)
- Delegação de tarefas para subagentes (message)

**Researcher**
- Pesquisa web e scraping com Playwright:
        - Navegação automatizada (create_page, navigate_to)
        - Extração de texto estruturado (extract_page_text)
        - Listagem e interação com elementos (get_page_elements, click_element, fill_input)
        - Captura de screenshots (capture_screenshot)
        - Busca web (search_web)
        - Planejamento de tarefas (write_todos)

**Coder**
- Manipulação de arquivos (read_file, write_file)
- Execução de comandos shell (shell_tool)
- Busca por arquivos e conteúdo (glob_search, grep_search)
- Planejamento de tarefas (write_todos)

Veja os prompts de sistema em `src/agents/prompts/` para detalhes completos das ferramentas de cada agente.

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

# 5. Execute o MLFlow

mlflow server --port 1234

# 5. Executar diretamente (via CLI App)
cd src/agents
python cli.py
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

# CLI de demonstração (modo conversacional)
python src/agents/cli.py

# Researcher (pesquisa web)
python src/agents/researcher.py

# Coder (desenvolvimento)
python src/agents/coder.py
```

#### Como usar o CLI (cli.py)

O arquivo `cli.py` permite interagir com o OpenAgent em modo conversacional no terminal:

```bash
python src/agents/cli.py
```

Você pode digitar perguntas ou comandos, e o agente responderá de forma interativa, mostrando o raciocínio e as etapas executadas.

Comandos úteis:
- `exit`, `quit`, `bye`: encerra a sessão
- Mensagens livres: descreva a tarefa ou pergunta normalmente

O CLI é ideal para testes rápidos, demonstrações e debugging do fluxo multi-agente.

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

# 🐳 OpenAgent Docker Setup

Este guia explica como executar o OpenAgent em containers Docker com integração completa ao LangSmith Studio.

## 📋 Pré-requisitos

- Docker Desktop instalado (Mac/Windows) ou Docker Engine (Linux)
- Docker Compose v2.0+
- Chaves de API (Groq, LangFuse)
- (Opcional) LangSmith API Key para debugging visual no Studio

## 🏗️ Arquitetura

O setup completo inclui 4 serviços Docker:

1. **PostgreSQL** - Armazena checkpoints persistentes do LangGraph
2. **Redis** - Cache rápido e armazenamento de sessões
3. **LangGraph Server** - API REST na porta 8000 + integração com LangSmith Studio
4. **OpenAgent CLI** - Interface interativa para desenvolvimento rápido

## 🚀 Quick Start

### 1. Configurar Environment Variables

Copie o arquivo de exemplo e preencha suas chaves de API:

```bash
cp .env.example .env
```

Edite o arquivo `.env` e adicione suas chaves:

```bash
# Obrigatório
GROQ_API_KEY=gsk_your_actual_key_here

# Opcional - LangFuse para observabilidade
LANGFUSE_PUBLIC_KEY=pk-lf-your_key_here
LANGFUSE_SECRET_KEY=sk-lf-your_key_here

# Opcional - LangSmith Studio para debugging visual
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=lsv2_pt_your_key_here
# LANGCHAIN_PROJECT=openagent
```

### 2. Criar Workspace Directory

```bash
mkdir -p workspace
```

Este diretório será montado no container e usado como workspace pelos agentes.

### 3. Escolher Modo de Execução

Use o script `start.sh` para facilitar a inicialização:

```bash
chmod +x start.sh
```

#### Opção A: LangGraph Server (para LangSmith Studio)

```bash
./start.sh server
```

Inicia:
- PostgreSQL (checkpoint storage)
- Redis (caching)
- LangGraph Server na porta 8000

Acesse a API em: `http://localhost:8000`

#### Opção B: CLI Interativo

```bash
./start.sh cli
```

Inicia:
- PostgreSQL
- Redis
- OpenAgent CLI (modo interativo)

#### Opção C: Ambos (Server + CLI)

```bash
./start.sh both
```

Inicia todos os serviços, incluindo o servidor e depois abre o CLI.

### 4. Build Manual (se necessário)

Se preferir não usar o script:

```bash
# Build da imagem
docker-compose build

# Iniciar apenas o server
docker-compose up -d postgres redis langgraph-server

# Ou iniciar o CLI
docker-compose --profile cli run --rm openagent-cli
```

## 📁 Estrutura de Arquivos

```
openagent-core/
├── Dockerfile              # Definição da imagem Docker
├── docker-compose.yml      # Orquestração multi-serviço
├── langgraph.json         # Configuração de graphs para LangGraph Server
├── start.sh               # Script helper para inicialização
├── requirements.txt        # Dependências Python
├── .env                    # Variáveis de ambiente (não commitado)
├── .env.example           # Template de variáveis
├── workspace/             # Workspace montado no container
└── src/
    └── agents/
        ├── openagent.py    # Graph principal (orquestrador)
        ├── researcher.py   # Graph de pesquisa
        ├── coder.py        # Graph de código
        └── prompts/
```

## ⚙️ Configuração

### Environment Variables

| Variável | Descrição | Padrão | Obrigatório |
|----------|-----------|--------|-------------|
| `GROQ_API_KEY` | Chave de API do Groq | - | ✅ Sim |
| `WORKSPACE_ROOT` | Diretório de trabalho dos agentes | `/workspace` | Não |
| `HEADLESS` | Modo headless do browser | `true` | Não |
| `POSTGRES_URI` | URI do PostgreSQL | Auto | Não (auto-config) |
| `REDIS_URI` | URI do Redis | Auto | Não (auto-config) |
| `LANGFUSE_PUBLIC_KEY` | Chave pública LangFuse | - | Não |
| `LANGFUSE_SECRET_KEY` | Chave secreta LangFuse | - | Não |
| `LANGCHAIN_TRACING_V2` | Habilitar tracing LangSmith | - | Não |
| `LANGCHAIN_API_KEY` | Chave API LangSmith | - | Não |
| `LANGCHAIN_PROJECT` | Nome do projeto LangSmith | - | Não |

### Volumes

**LangGraph Server:**
- `./workspace:/workspace:rw` - Workspace persistente (read-write)
- `./src:/app/src:ro` - Código fonte (read-only)
- `./langgraph.json:/app/langgraph.json:ro` - Configuração de graphs
- `postgres_data` - Volume persistente para PostgreSQL

**OpenAgent CLI:**
- `./workspace:/workspace:rw` - Workspace persistente (read-write)
- `./src:/app/src:rw` - Código fonte (read-write para hot reload)

### Resource Limits

Configurado no `docker-compose.yml`:

- **CPU**: 1-2 cores
- **Memory**: 2-4 GB
- **Shared Memory**: 2 GB (para Chromium)

Ajuste conforme necessário para sua máquina.

## 🔧 Comandos Úteis Docker

### Parar Serviços

```bash
./start.sh stop
# ou
docker-compose down
```

### Ver Logs

```bash
./start.sh logs
# ou
docker-compose logs -f

# Logs de um serviço específico
docker-compose logs -f langgraph-server
docker-compose logs -f postgres
```

### Rebuild (após mudanças no código)

```bash
./start.sh build
# ou
docker-compose build --no-cache
```

### Executar Shell no Container

```bash
# No LangGraph Server
docker exec -it openagent-langgraph-server /bin/bash

# No container CLI (se estiver rodando)
docker exec -it openagent-cli /bin/bash
```

### Verificar Status dos Serviços

```bash
docker-compose ps
```

### Acessar PostgreSQL

```bash
docker exec -it openagent-postgres psql -U langgraph -d langgraph
```

### Acessar Redis

```bash
docker exec -it openagent-redis redis-cli
```

### Limpar Tudo (containers, volumes, imagens)

```bash
docker-compose --profile cli down -v
docker rmi openagent:latest
```

## 🐛 Troubleshooting

### Erro: "Chromium not found"

O Playwright pode não ter instalado o Chromium corretamente. Rebuild:

```bash
docker-compose build --no-cache
```

### Erro: "GROQ_API_KEY not found"

Verifique se o arquivo `.env` existe e contém a chave:

```bash
cat .env | grep GROQ_API_KEY
```

### Browser não abre em headless

Isso é esperado! O browser roda em `headless=true` no container. Para debug local (fora do Docker), use `HEADLESS=false`.

### Permissões no workspace

Se tiver problemas de permissão no `./workspace`:

```bash
chmod -R 755 workspace
```

### Container não inicia

Verifique os logs:

```bash
docker-compose logs
```

## 🔒 Segurança

⚠️ **Importante**: O container roda com algumas permissões elevadas para o Playwright funcionar:

- `seccomp:unconfined` - Necessário para Chromium
- `--no-sandbox` - Flag do Chrome para Docker

**Não use em produção** sem revisar as implicações de segurança.

Para produção, considere:
- Docker sandboxes (Docker Desktop 4.50+)
- Kubernetes com gVisor ou Kata Containers
- Execução de código em containers isolados separados

## 📊 Monitoramento e Observabilidade

### Logs

```bash
# Todos os serviços
./start.sh logs

# Serviço específico
docker-compose logs -f langgraph-server
docker-compose logs -f postgres
docker-compose logs -f redis
```

### LangFuse (Observabilidade)

Se configurado no `.env`, os traces são enviados para:
- Dashboard: https://cloud.langfuse.com
- Métricas: latência, custos, tokens utilizados
- Traces completos de execução

### LangSmith Studio (Debugging Visual)

Se configurado no `.env`:
- Studio URL: https://smith.langchain.com
- Conecte ao servidor local: `http://localhost:8000`
- Visualize grafos, states, checkpoints
- Debug interativo de agents

### Health Checks

Verificar saúde dos serviços:

```bash
# PostgreSQL
docker exec openagent-postgres pg_isready -U langgraph

# Redis
docker exec openagent-redis redis-cli ping

# LangGraph Server API
curl http://localhost:8000/health
```

## 🎨 Integração com LangSmith Studio

### 1. Configurar LangSmith

No arquivo `.env`, descomente e configure:

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_your_key_here
LANGCHAIN_PROJECT=openagent
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

### 2. Iniciar LangGraph Server

```bash
./start.sh server
```

### 3. Conectar no LangSmith Studio

1. Abra o [LangSmith Studio](https://smith.langchain.com)
2. Vá para a seção "Deployments"
3. Clique em "Connect to Local Server"
4. Use a URL: `http://localhost:8000`

### 4. Graphs Disponíveis

O `langgraph.json` expõe 3 graphs:

- **openagent** - Orquestrador principal com subagentes researcher e coder
- **researcher** - Agente de pesquisa com browser tools
- **coder** - Agente de código com file tools

### 5. Testar no Studio

No LangSmith Studio você pode:
- Visualizar o grafo de estados de cada agent
- Executar agents com inputs customizados
- Ver checkpoints salvos no PostgreSQL
- Debugar interações e fluxos de dados
- Monitorar traces e performance

## 📊 Serviços e Portas

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| LangGraph Server | 8000 | API REST + Studio integration |
| PostgreSQL | 5432 | Checkpoint storage |
| Redis | 6379 | Cache e sessões |

## 🔧 Comandos do Script start.sh

```bash
./start.sh server    # Inicia LangGraph Server (API)
./start.sh cli       # Inicia CLI interativo
./start.sh both      # Inicia Server + CLI
./start.sh stop      # Para todos os serviços
./start.sh logs      # Mostra logs (Ctrl+C para sair)
./start.sh build     # Rebuild completo das imagens
```

## 🎯 Próximos Passos

Depois de testar localmente com Docker:

1. **LangSmith Studio**: Conecte ao servidor local conforme instruções acima
2. **Production**: Configure para produção com secrets managers
3. **Deploy**: Deploy em K8s ou cloud provider com volumes persistentes

## 📞 Suporte

Se encontrar problemas:
1. Verifique os logs: `docker-compose logs`
2. Verifique o `.env`: `cat .env`
3. Rebuild from scratch: `docker-compose build --no-cache`

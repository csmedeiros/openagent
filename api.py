"""
OpenAgent API — FastAPI server para consumo do agente via frontend.

Endpoints:
    POST /chat          → Envia uma mensagem e recebe a resposta completa (JSON)
    POST /chat/stream   → Envia uma mensagem e recebe tokens via SSE (streaming)
    DELETE /chat/{thread_id} → Limpa o histórico de uma conversa
    GET  /health        → Health check

Formato de upload de arquivos (campo `files` no body JSON):
    files: [{"nome_do_arquivo.pdf": "<base64_encoded_bytes>"}, ...]
"""

import sys
import os
import asyncio
import importlib
import logging
import base64

# ─── Path Setup ──────────────────────────────────────────────────────────────
_SRC_DIR = os.path.join(os.path.dirname(__file__), "openagent-core/src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from dotenv import load_dotenv
load_dotenv()

# ─── Silence noisy loggers ────────────────────────────────────────────────────
for _name in ("mlflow", "mlflow.langchain", "opentelemetry", "alembic"):
    _log = logging.getLogger(_name)
    _log.setLevel(logging.CRITICAL)
    _log.propagate = False

# ─── FastAPI ──────────────────────────────────────────────────────────────────
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Optional, List, Dict
import json

# ─── LangChain / LangGraph ────────────────────────────────────────────────────
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="OpenAgent API",
    description="API para o chatbot OpenAgent.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Ajuste para a origem do seu frontend em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Upload dir ───────────────────────────────────────────────────────────────

_default_workspace = r"C:\Users\caiosmedeiros\Documents\openagent-tests"
UPLOAD_DIR = os.environ.get(
    "UPLOAD_DIR",
    os.path.join(os.environ.get("WORKSPACE_ROOT", _default_workspace), "uploads"),
)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def save_uploaded_files(files: List[Dict[str, str]]) -> List[str]:
    """Recebe lista de dicts {filename: base64_content}, salva e retorna os caminhos."""
    paths = []
    for file_dict in files:
        for filename, content_b64 in file_dict.items():
            # Decodifica o base64 (aceita também conteúdo plain text)
            try:
                data = base64.b64decode(content_b64)
            except Exception:
                data = content_b64.encode("utf-8")
            dest = os.path.join(UPLOAD_DIR, filename)
            with open(dest, "wb") as fh:
                fh.write(data)
            paths.append(dest)
    return paths


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = "default"
    files: Optional[List[Dict[str, str]]] = None  # [{"filename": "<base64>"}]

class ChatResponse(BaseModel):
    thread_id: str
    response: str
    uploaded_files: List[str] = []

class SettingsRequest(BaseModel):
    MODEL_PROVIDER:  Optional[str] = None
    MODEL_NAME:      Optional[str] = None
    MODEL_API_KEY:   Optional[str] = None
    MODEL_BASE_URL:  Optional[str] = None
    WORKSPACE_ROOT:  Optional[str] = None
    UPLOAD_DIR:      Optional[str] = None

# Keys that are safe to return publicly (no secrets)
_PUBLIC_KEYS = {"MODEL_PROVIDER", "MODEL_NAME", "MODEL_BASE_URL", "WORKSPACE_ROOT", "UPLOAD_DIR"}

# ─── Estado global do agente ─────────────────────────────────────────────────
# O grafo é carregado uma única vez na inicialização do servidor.

_agent_graph = None
_checkpointer = MemorySaver()

async def _get_graph():
    global _agent_graph
    if _agent_graph is None:
        from agents.openagent import get_openagent
        _agent_graph = await get_openagent()
        _agent_graph.checkpointer = _checkpointer
    return _agent_graph


def _extract_text(content) -> str:
    """Extrai texto de conteúdos que podem ser string ou lista de blocos."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif not isinstance(block, dict):
                parts.append(str(block))
        return "".join(parts)
    return str(content) if content else ""


def _make_config(thread_id: str) -> dict:
    return {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 100,
    }

# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check simples."""
    return {"status": "ok"}


@app.get("/settings")
async def get_settings():
    """Retorna as configurações atuais (sem a API key)."""
    return {
        key: os.environ.get(key, "")
        for key in sorted(_PUBLIC_KEYS)
    }


@app.post("/settings")
async def update_settings(req: SettingsRequest):
    """
    Atualiza as variáveis de ambiente em runtime e reseta o agente.
    O próximo request de chat criará um novo graph com o novo modelo.
    """
    global _agent_graph

    changed = False
    for field, value in req.model_dump(exclude_none=True).items():
        if value:  # ignora strings vazias
            os.environ[field] = value
            changed = True

    if changed:
        # Reinicia o grafo para que use o novo modelo
        _agent_graph = None
        # Limpa o cache do modelo
        try:
            from agents.models import clear_model_cache
            clear_model_cache()
        except Exception:
            pass

        # Reconstrói UPLOAD_DIR se WORKSPACE_ROOT mudou
        global UPLOAD_DIR
        UPLOAD_DIR = os.environ.get(
            "UPLOAD_DIR",
            os.path.join(os.environ.get("WORKSPACE_ROOT", _default_workspace), "uploads"),
        )
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    return {"status": "ok", "changed": changed}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Envia uma mensagem ao agente e aguarda a resposta completa.
    Ideal para frontends sem suporte a streaming.
    """
    graph = await _get_graph()
    config = _make_config(req.thread_id)

    # Salva arquivos e monta o payload de estado
    file_paths = save_uploaded_files(req.files) if req.files else []
    input_payload: Dict[str, Any] = {"messages": [HumanMessage(content=req.message)]}
    if file_paths:
        input_payload["files"] = file_paths

    result = await graph.ainvoke(input_payload, config=config)

    # Pega a última mensagem do AI
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    if not ai_messages:
        raise HTTPException(status_code=500, detail="Agente não retornou resposta.")

    response_text = _extract_text(ai_messages[-1].content)
    return ChatResponse(thread_id=req.thread_id, response=response_text, uploaded_files=file_paths)


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Envia uma mensagem ao agente e faz streaming da resposta via SSE.
    Cada evento é um JSON no formato:
      data: {"type": "token"|"tool_start"|"tool_end"|"done"|"error", ...}
    """
    graph = await _get_graph()
    config = _make_config(req.thread_id)

    # Salva arquivos antes de iniciar o stream
    file_paths = save_uploaded_files(req.files) if req.files else []
    input_payload: Dict[str, Any] = {"messages": [HumanMessage(content=req.message)]}
    if file_paths:
        input_payload["files"] = file_paths

    async def event_generator():
        # Informa ao frontend quais arquivos foram recebidos
        if file_paths:
            yield f"data: {json.dumps({'type': 'files_saved', 'paths': file_paths})}\n\n"

        try:
            async for event in graph.astream_events(
                input_payload,
                config=config,
                version="v2",
            ):
                kind = event["event"]

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    text = _extract_text(chunk.content)
                    if text:
                        payload = json.dumps({"type": "token", "content": text})
                        yield f"data: {payload}\n\n"

                elif kind == "on_chat_model_start":
                    yield f"data: {json.dumps({'type': 'message_start'})}\n\n"

                elif kind == "on_chat_model_end":
                    output = event["data"].get("output")
                    has_tool_calls = bool(getattr(output, "tool_calls", []))
                    payload = json.dumps({
                        "type": "message_end",
                        "is_last_message": not has_tool_calls,
                    })
                    yield f"data: {payload}\n\n"

                elif kind == "on_tool_start":
                    payload = json.dumps({
                        "type": "tool_start",
                        "tool": event["name"],
                        "input": str(event["data"].get("input", {}))[:300],
                    })
                    yield f"data: {payload}\n\n"

                elif kind == "on_tool_end":
                    payload = json.dumps({
                        "type": "tool_end",
                        "tool": event.get("name", ""),
                    })
                    yield f"data: {payload}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            payload = json.dumps({"type": "error", "detail": str(e)})
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.delete("/chat/{thread_id}")
async def clear_thread(thread_id: str):
    """
    Remove o histórico de uma thread (conversa).
    O MemorySaver não tem delete nativo; aqui apenas sinalizamos ao cliente.
    Para persistência real, use SqliteSaver ou PostgresSaver.
    """
    # Reinicia o checkpointer para essa thread criando um estado vazio
    # (A forma mais simples com MemorySaver é não fazer nada — a thread
    #  simplesmente não terá histórico novo se o frontend mudar o thread_id)
    return {"detail": f"Thread '{thread_id}' limpa. Use um novo thread_id para recomeçar."}


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8080, reload=True)

"""
OpenAgent CLI — A Claude Code-inspired interactive terminal for AI agents.

Usage:
    python cli.py              # starts with coder (default)
    python cli.py coder        # explicitly select coder
    python cli.py researcher   # select researcher
    python cli.py openagent    # select openagent

Slash commands inside the CLI:
    /help           Show available commands
    /exit, /quit    Exit the CLI
    /clear          Start a fresh conversation
    /agent <name>   Switch to another agent
    /agents         List available agents
    /history        Show message count in current thread
"""

import sys
import os
import time
import argparse
import asyncio
import importlib

# ─── Path Setup ──────────────────────────────────────────────────────────────
# Ajuste para funcionar na raiz do projeto
_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "openagent-core", "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join("openagent-core", ".env"))


# ─── Silence noisy loggers that pollute streaming output ─────────────────────
import logging
import warnings

def _silence_noisy_loggers():
    """Aggressively suppress mlflow, Alembic, SQLAlchemy and OpenTelemetry log noise."""
    for name in [
        "mlflow",
        "mlflow.utils.autologging_utils",
        "mlflow.tracking",
        "mlflow.langchain",
        "opentelemetry",
        "opentelemetry.attributes",
        "opentelemetry.trace",
        "alembic",
        "sqlalchemy",
    ]:
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL)
        logger.handlers = []
        logger.addHandler(logging.NullHandler())
        logger.propagate = False

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    warnings.filterwarnings("ignore", module="mlflow")
    warnings.filterwarnings("ignore", module="opentelemetry")
    warnings.filterwarnings("ignore", module="alembic")
    warnings.filterwarnings("ignore", module="sqlalchemy")

_silence_noisy_loggers()


# ─── Rich Imports ────────────────────────────────────────────────────────────
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.theme import Theme
from rich.rule import Rule

# ─── LangGraph / LangChain Imports ───────────────────────────────────────────
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage

# ─── Theme ───────────────────────────────────────────────────────────────────
THEME = Theme({
    "info":        "dim cyan",
    "warning":     "yellow",
    "danger":      "bold red",
    "success":     "bold green",
    "tool.name":   "bold yellow",
    "tool.ok":     "dim green",
    "thinking":    "dim italic magenta",
    "stats":       "dim",
    "prompt":      "bold bright_green",
    "agent.label": "bold bright_cyan",
})

console = Console(theme=THEME)

# ─── Agent Registry ──────────────────────────────────────────────────────────
AGENT_REGISTRY = {
    "coder": {
        "module": "agents.coder",
        "attr": "coder",
        "label": "Coder",
        "icon": "⌨️ ",
        "description": "Coding assistant with file system and shell tools",
    },
    "researcher": {
        "module": "agents.researcher",
        "attr": "researcher",
        "label": "Researcher",
        "icon": "🔍",
        "description": "Research assistant with browser and web search",
    },
    "openagent": {
        "module": "agents.openagent",
        "attr": "oa",
        "label": "OpenAgent",
        "icon": "🤖",
        "description": "General-purpose orchestrator agent",
    },
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_text(content) -> str:
    """Extract printable text from message content.

    Handles plain strings AND Anthropic-style content blocks
    (list of dicts with ``type: "text"``).
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                # Only extract actual text blocks, skip tool_use / thinking
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content) if content else ""


def _truncate(text: str, max_len: int = 300) -> str:
    if len(text) > max_len:
        return text[:max_len] + "…"
    return text


def _summarize_tool_output(output) -> tuple[str, bool]:
    """Return (summary_text, is_success) from a tool output.

    Handles Command objects, ToolMessages, plain strings, and errors.
    """
    import re as _re

    raw = str(output)

    # ── Command wrapping a ToolMessage (read_file / write_file) ──────
    # Pattern: ToolMessage(content='Content of file X (lines A-B):\nN lines out of M ...')
    m = _re.search(r"Content of file (.+?) \(lines (\d+-\d+)\):\\n(\d+) lines out of (\d+)", raw)
    if m:
        return f"Read {m.group(1)}  [{m.group(2)}] — {m.group(3)}/{m.group(4)} lines", True

    # File created
    m = _re.search(r"File (.+?) created", raw)
    if m:
        return f"Wrote {m.group(1)}", True

    # File appended
    m = _re.search(r"Content added in the end of file (.+?)['\"]", raw)
    if m:
        return f"Appended to {m.group(1)}", True

    # Shell tool — exit code
    m = _re.search(r"Exit code: (\d+)", raw)
    if m:
        code = int(m.group(1))
        # Extract first meaningful line of stdout
        stdout_m = _re.search(r"STDOUT:\\n(.+?)(?:\\n|$)", raw)
        brief = stdout_m.group(1)[:80] if stdout_m else ""
        if code == 0:
            return f"exit 0{' — ' + brief if brief else ''}", True
        else:
            stderr_m = _re.search(r"STDERR:\\n(.+?)(?:\\n|$)", raw)
            err_brief = stderr_m.group(1)[:80] if stderr_m else ""
            return f"exit {code}{' — ' + err_brief if err_brief else ''}", False

    # Error patterns
    if "Error" in raw or "error" in raw or "does not exist" in raw:
        # Extract just the error message, not the full repr
        m = _re.search(r"(Error[^'\"]{0,120})", raw)
        return m.group(1).strip() if m else _truncate(raw, 100), False

    # Fallback: just truncate
    return _truncate(raw, 100), True


# ─── Agent Loading ───────────────────────────────────────────────────────────


# Suporte para carregar o researcher de forma assíncrona
async def load_agent(name: str):
    """Import and return the compiled LangGraph for *name*."""
    info = AGENT_REGISTRY[name]
    mod = importlib.import_module(info["module"])
    _silence_noisy_loggers()
    # Se for researcher, chame a função async get_researcher
    if name == "researcher":
        return await mod.get_researcher()
    return getattr(mod, info["attr"])


# ─── UI Components ───────────────────────────────────────────────────────────

def print_header(agent_name: str):
    info = AGENT_REGISTRY[agent_name]
    console.print()
    console.print(
        Panel(
            Text.from_markup(
                f"[bold bright_white]OpenAgent[/bold bright_white]  ·  "
                f"[agent.label]{info['icon']} {info['label']}[/agent.label]\n"
                f"[dim]{info['description']}[/dim]\n\n"
                f"[dim]Type [bold]/help[/bold] for commands · "
                f"[bold]/exit[/bold] to quit · "
                f"[bold]/clear[/bold] for new conversation[/dim]"
            ),
            border_style="bright_blue",
            padding=(1, 3),
        )
    )
    console.print()


def print_help():
    table = Table(
        show_header=True,
        header_style="bold bright_cyan",
        border_style="dim",
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column("Command", style="bold cyan", min_width=20)
    table.add_column("Description")

    table.add_row("/help",            "Show this help message")
    table.add_row("/exit · /quit",    "Exit the CLI")
    table.add_row("/clear",           "Start a new conversation thread")
    table.add_row("/agent <name>",    "Switch agent (coder, researcher, openagent)")
    table.add_row("/agents",          "List all available agents")
    table.add_row("/history",         "Show message count in current thread")

    console.print()
    console.print(Panel(table, title="[bold]Commands[/bold]", border_style="dim", padding=(1, 1)))
    console.print()


def print_agents_list(current: str):
    console.print()
    for name, info in AGENT_REGISTRY.items():
        is_current = name == current
        marker = "[bold bright_green]→[/bold bright_green]" if is_current else " "
        label_style = "bold bright_white" if is_current else "bold"
        console.print(
            Text.from_markup(
                f"  {marker} {info['icon']} [{label_style}]{info['label']}[/{label_style}]"
                f"  [dim]({name})[/dim]  —  [dim]{info['description']}[/dim]"
            )
        )
    console.print()


# ─── Streaming Engine ────────────────────────────────────────────────────────

async def stream_response(graph, user_input: str, config: dict):
    """Stream the agent response, printing text and tool calls as they arrive.

    Everything is appended to stdout so the terminal stays scrollable.
    """
    input_payload = {"messages": [HumanMessage(content=user_input)]}

    assistant_text = ""
    tool_count = 0
    has_printed_text = False
    start_time = time.time()

    try:
        async for event in graph.astream_events(
            input_payload, config=config, version="v2"
        ):
            kind = event["event"]

            # ── Streaming text tokens ────────────────────────────────────
            if kind == "on_chat_model_stream":
                chunk_text = _extract_text(event["data"]["chunk"].content)
                if chunk_text:
                    if not has_printed_text:
                        # Blank line before first text to separate from prompt
                        console.print()
                        has_printed_text = True
                    assistant_text += chunk_text

            # ── Tool invocation ──────────────────────────────────────────
            elif kind == "on_tool_start":
                tool_count += 1
                tool_name = event["name"]
                tool_input = event["data"].get("input", {})

                # Ensure we're on a new line
                if has_printed_text and assistant_text and not assistant_text.endswith("\n"):
                    print()

                # Build a compact representation of the input
                if isinstance(tool_input, dict):
                    lines = []
                    for k, v in tool_input.items():
                        val = _truncate(str(v), 150)
                        lines.append(f"  [dim]{k}:[/dim] {val}")
                    body = "\n".join(lines)
                else:
                    body = _truncate(str(tool_input), 300)

                console.print(
                    Panel(
                        Text.from_markup(body) if body else Text("(no input)"),
                        title=f"[tool.name]⚡ {tool_name}[/tool.name]",
                        title_align="left",
                        border_style="yellow",
                        padding=(0, 1),
                    )
                )

            # ── Tool result ──────────────────────────────────────────────
            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                output = event["data"].get("output", "")
                # Custom: Friendly print for write_todos
                if tool_name == "write_todos":
                    todos = output.get("todos") if isinstance(output, dict) else None
                    if todos:
                        console.print(Panel(
                            "[bold green]✓ Plano de tarefas atualizado:[/bold green]\n" + "\n".join(f"- {t.get('content','')}" for t in todos),
                            border_style="green",
                            title="write_todos",
                            padding=(1, 2)
                        ))
                    else:
                        console.print(Text("✓ Tarefas atualizadas", style="tool.ok"))
                    console.print()
                else:
                    summary, ok = _summarize_tool_output(output)
                    icon = "✓" if ok else "✗"
                    style = "tool.ok" if ok else "danger"
                    console.print(Text(f"  {icon} {summary}", style=style))
                    console.print()

        # Após o streaming, se houver texto, renderiza como markdown
        if assistant_text:
            console.print(Panel.fit(Text.from_markup(assistant_text, style=""), title="Resposta", border_style="blue"), markup=True)

    except KeyboardInterrupt:
        console.print("\n[warning]⚠  Interrupted by user[/warning]")
    except Exception as e:
        console.print(f"\n[danger]❌ Error: {e!s}[/danger]")

    # Always end on a new line
    if has_printed_text and assistant_text and not assistant_text.endswith("\n"):
        print()

    # ── Stats bar ────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    parts = []
    if tool_count:
        parts.append(f"🔧 {tool_count} tool{'s' if tool_count != 1 else ''}")
    parts.append(f"⏱  {elapsed:.1f}s")
    console.print(Text(" · ".join(parts), style="stats"), justify="right")


# ─── Main Loop ───────────────────────────────────────────────────────────────


async def run_cli(agent_name: str):
    """Interactive REPL for the selected agent."""

    # Load agent with a brief spinner (scrollable — spinner only in-place)
    with console.status(
        f"[bold blue]Loading {AGENT_REGISTRY[agent_name]['label']} agent…",
        spinner="dots",
    ):
        graph = await load_agent(agent_name)
        checkpointer = MemorySaver()
        graph.checkpointer = checkpointer

    print_header(agent_name)

    thread_id = f"cli-{int(time.time())}"
    session_messages = 0

    # Optional tracing
    callbacks = []
    try:
        from langfuse.langchain import CallbackHandler  # noqa: PLC0415
        callbacks.append(CallbackHandler())
    except Exception:
        pass

    # ── REPL ─────────────────────────────────────────────────────────────
    while True:
        # Prompt
        try:
            console.print(Text("❯ ", style="prompt"), end="")
            user_input = input("").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]👋 Goodbye![/dim]\n")
            break

        if not user_input:
            continue

        # ── Slash commands ───────────────────────────────────────────
        if user_input.startswith("/"):
            tokens = user_input.lower().split()
            cmd = tokens[0]

            if cmd in ("/exit", "/quit"):
                console.print("[dim]👋 Goodbye![/dim]\n")
                break

            elif cmd == "/help":
                print_help()

            elif cmd == "/clear":
                thread_id = f"cli-{int(time.time())}"
                session_messages = 0
                console.print("[success]✓ New conversation started[/success]\n")

            elif cmd == "/agents":
                print_agents_list(agent_name)

            elif cmd == "/agent":
                if len(tokens) < 2:
                    console.print("[warning]Usage: /agent <name>[/warning]")
                    continue
                target = tokens[1]
                if target not in AGENT_REGISTRY:
                    console.print(
                        f"[danger]Unknown agent:[/danger] {target}. "
                        "Use [bold]/agents[/bold] to list."
                    )
                    continue
                if target == agent_name:
                    console.print(f"[dim]Already using {agent_name}[/dim]")
                    continue

                agent_name = target
                with console.status(
                    f"[bold blue]Switching to {AGENT_REGISTRY[agent_name]['label']}…",
                    spinner="dots",
                ):
                    graph = await load_agent(agent_name)
                    checkpointer = MemorySaver()
                    graph.checkpointer = checkpointer
                    thread_id = f"cli-{int(time.time())}"
                    session_messages = 0
                print_header(agent_name)

            elif cmd == "/history":
                console.print(
                    f"[info]Messages in thread:[/info] {session_messages}"
                )

            else:
                console.print(
                    f"[warning]Unknown command:[/warning] {cmd}  —  "
                    "type [bold]/help[/bold] for available commands."
                )
            continue

        # ── Normal message ───────────────────────────────────────────
        session_messages += 1

        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 100,
        }
        if callbacks:
            config["callbacks"] = callbacks

        await stream_response(graph, user_input, config)
        console.print()  # breathing room before next prompt


# ─── Entry Point ─────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        prog="openagent",
        description="OpenAgent CLI — Interactive terminal for AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python cli.py              # default: coder\n"
            "  python cli.py researcher   # start with researcher\n"
            "  python cli.py openagent    # start with openagent\n"
        ),
    )
    parser.add_argument(
        "agent",
        nargs="?",
        default="openagent",
        choices=list(AGENT_REGISTRY.keys()),
        help="Agent to start with (default: coder)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(run_cli(args.agent))
    except KeyboardInterrupt:
        console.print("\n[dim]👋 Goodbye![/dim]")


if __name__ == "__main__":
    main()

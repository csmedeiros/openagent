from dotenv import load_dotenv
import os
import sys

# Ensure 'src' is in sys.path so 'agents' package is resolvable when running directly
_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

load_dotenv()

from langchain.agents import create_agent
from langchain.agents.middleware import FilesystemFileSearchMiddleware, TodoListMiddleware, ShellToolMiddleware

from agents.middleware import SummarizationMiddleware

# Import centralized model configuration
from agents.models import model

import os
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_CURRENT_DIR, "prompts/coder_sys_prompt_v0.0.1.md"), "r") as f:
    sys_prompt = f.read()

# Local development workspace root
root_path = r"C:\Users\caiosmedeiros\Documents"

fs_middlware = FilesystemFileSearchMiddleware(root_path=root_path)
todo_middleware = TodoListMiddleware()
shell_middleware = ShellToolMiddleware(workspace_root=root_path)

from agents.tools import *
from langgraph.graph import StateGraph, START, END, MessagesState

tools = [write_file, read_file, write_todos, shell_tool]
tools.extend(fs_middlware.tools)

from langchain.messages import SystemMessage
from langchain.agents.middleware.types import OmitFromInput
from typing_extensions import NotRequired
from typing import Annotated
from langchain.agents.middleware.todo import Todo

class CoderState(MessagesState):
    todos: Annotated[NotRequired[list[Todo]], OmitFromInput] = []

from agents.utils.message_truncation import truncate_messages

def agent(state: MessagesState) -> MessagesState:
    llm = model.bind_tools(tools=tools)

    # Hard truncation safety net - prevents exceeding API token limits
    # messages = truncate_messages(state["messages"])

    response = llm.invoke([SystemMessage(content=sys_prompt)] + state["messages"])
    return MessagesState(**{
        "messages": [response]
    })

from langgraph.prebuilt import ToolNode, tools_condition

tool_node = ToolNode(
    tools=tools,
    handle_tool_errors=True
)

from agents.utils.nodes.summarization_node import *

builder = StateGraph(MessagesState)

builder.add_node("tools", tool_node)
builder.add_node("agent", agent)
builder.add_node("summarize", summarize_messages_node)

# START → check if summarization needed → summarize or go to agent
builder.add_conditional_edges(START, should_summarize)
builder.add_edge("summarize", "agent")

# agent → check if tools needed → tools or END
builder.add_conditional_edges("agent", tools_condition)

# tools → check if summarization needed before returning to agent
# This is critical: without this, the context grows without limit
# during long tool-use sessions
builder.add_conditional_edges("tools", should_summarize)

import mlflow

mlflow.set_tracking_uri("http://127.0.0.1:1234")
mlflow.set_experiment("OpenAgent")
mlflow.langchain.autolog()

coder = builder.compile()


from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()

if __name__ == "__main__":

    coder.checkpointer = checkpointer

    from langfuse.langchain import CallbackHandler

    langfuse_handler = CallbackHandler()

    def _extract_text(content) -> str:
        """Extract text from message content (handles both str and Anthropic content blocks)."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            # Anthropic returns list of dicts like [{"type": "text", "text": "..."}]
            return "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        return str(content)

    async def main():
        """Mini CLI app with tool call visualization"""
        print("=" * 80)
        print("OpenAgent CLI - Type 'exit' or 'quit' to end the conversation")
        print("=" * 80)
        print()

        from langchain_core.messages import HumanMessage

        # Thread ID for checkpointer — all messages are persisted automatically
        thread_id = "cli-session-0"

        while True:
            # Get user input
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("\nGoodbye!")
                break

            if not user_input:
                continue

            print("\nAssistant: ", end="", flush=True)

            assistant_message = ""

            # Configure callbacks — checkpointer manages message history via thread_id
            config = {
                "configurable": {"thread_id": thread_id},
            }
            if langfuse_handler:
                config["callbacks"] = [langfuse_handler]

            # Only send the NEW message; checkpointer replays previous messages automatically
            input_payload = {"messages": [HumanMessage(content=user_input)]}

            try:
                async for event in coder.astream_events(input_payload, config=config, version="v2"):
                    kind = event["event"]

                    # Stream AI response
                    if kind == "on_chat_model_stream":
                        content = event["data"]["chunk"].content
                        text = _extract_text(content)
                        if text:
                            assistant_message += text
                            print(text, end="", flush=True)

                    # Capture tool calls
                    elif kind == "on_tool_start":
                        tool_name = event["name"]
                        tool_input = event["data"].get("input", {})
                        print(f"\n\n🔧 [Tool Call: {tool_name}]", flush=True)
                        print(f"   Input: {tool_input}", flush=True)

                    # Capture tool results
                    elif kind == "on_tool_end":
                        tool_output = event["data"].get("output", "")
                        output_str = str(tool_output)
                        print(f"   Output: {output_str[:200]}{'...' if len(output_str) > 200 else ''}", flush=True)
                        print()

            except Exception as e:
                print(f"\n\n❌ Error: {e!s}")

            print("\n")

    import asyncio
    asyncio.run(main())

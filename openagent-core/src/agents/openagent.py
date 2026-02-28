import sys

sys.path.append(r"C:\Users\caiosmedeiros\Documents\Projetos Pessoais\openagent\openagent-core\src")

import mlflow
mlflow.set_experiment("OpenAgent Testing")
mlflow.langchain.autolog()

from dotenv import load_dotenv

load_dotenv()

from typing import List, Dict, Any, Annotated, TypedDict, Literal
from pydantic import BaseModel, Field
import os

# Import centralized model configuration
from agents.models import get_model, get_vision_model, model

from agents.tools import *
from agents.utils.logging import logger

# Getting the system prompt

import os

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_CURRENT_DIR, "prompts/openagent_sys_prompt_v0.0.1.md"), "r") as f:
    sys_prompt = f.read()


# Define openagent graph state

from langgraph.graph import MessagesState, StateGraph, START
from typing import TypedDict
from langchain.agents.middleware.todo import Todo
from langchain.agents.middleware.types import OmitFromInput
from typing_extensions import NotRequired

class OpenAgentState(MessagesState):
    files: Dict[str, str] = []
    todos: Annotated[NotRequired[list[Todo]], OmitFromInput]

from langchain.agents.middleware.types import OmitFromInput
from typing_extensions import NotRequired
from langchain.messages import SystemMessage
from langchain.agents.middleware import FilesystemFileSearchMiddleware
from operator import add
from langgraph.prebuilt import tools_condition
from langgraph.prebuilt import ToolNode

class OpenAgentState(MessagesState):
    files: Annotated[List[str], add]
    todos: Annotated[NotRequired[list[Todo]], OmitFromInput]
    browser_initialized: bool = False

from agents.utils.nodes.summarization_node import should_summarize, summarize_messages_node

builder = StateGraph(OpenAgentState)

tools = [write_file, read_file, shell_tool, write_todos, message]
tools.extend(FilesystemFileSearchMiddleware(root_path="/Users/claudiomedeiros/Documents/openagent/openagent-core/src/agents/tests").tools)


from agents.utils.message_truncation import truncate_messages

def agent(state: OpenAgentState) -> OpenAgentState:
    """Agent node that uses custom browser tools"""
    llm = model.bind_tools(tools=tools)

    # Hard truncation safety net - prevents exceeding API token limits
    # messages = truncate_messages(state["messages"])

    response = llm.invoke([SystemMessage(content=sys_prompt.replace("<FILES>", "\n".join(state["files"])))] + state['messages'])
    return {"messages": [response]}

builder.add_node("summarize", summarize_messages_node)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(tools=tools, handle_tool_errors=True))

builder.add_conditional_edges(START, should_summarize)
builder.add_conditional_edges("agent", tools_condition)

# tools → check if summarization needed before returning to agent
builder.add_conditional_edges("tools", should_summarize)
builder.add_edge("summarize", "agent")

from langfuse.langchain import CallbackHandler
from langchain_azure_ai.callbacks.tracers import AzureAIOpenTelemetryTracer

# callback = CallbackHandler()
# callback = AzureAIOpenTelemetryTracer(connection_string=os.getenv("AZURE_TRACING_CONNECTION_STRING"))
import mlflow

mlflow.set_tracking_uri("http://127.0.0.1:1234")
mlflow.set_experiment("OpenAgent")
mlflow.langchain.autolog()

oa = builder.compile()

# oa.config = {
#     "callbacks": [callback]
# }


# if __name__ == "__main__":
#     import asyncio
#     from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
#     from langgraph.checkpoint.memory import MemorySaver

#     async def run_cli():
#         """Simple CLI app for OpenAgent"""
#         # Setup tracing
#         langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"

#         if langfuse_enabled:
#             try:
#                 from langfuse.langchain import CallbackHandler
#                 langfuse_handler = CallbackHandler()
#                 logger.info("LangFuse tracing enabled")
#             except ImportError:
#                 langfuse_handler = None
#                 logger.warning("LangFuse not installed. Tracing disabled.")
#         else:
#             langfuse_handler = None
#             logger.info("LangFuse tracing disabled via LANGFUSE_ENABLED=false")

#         # Setup checkpointer and config
#         checkpointer = MemorySaver()
#         openagent.checkpointer = checkpointer

#         config = {
#             "configurable": {"thread_id": "1"},
#             # "callbacks": [langfuse_handler] if langfuse_handler else [],
#             "recursion_limit": 100,
#         }

#         # Welcome message
#         print("\n" + "="*80)
#         print("🤖 OpenAgent CLI")
#         print("="*80)
#         print("Type 'exit' or 'quit' to end the conversation\n")

#         while True:
#             # Get user input
#             try:
#                 user_input = input("👤 You: ").strip()
#             except (EOFError, KeyboardInterrupt):
#                 print("\n\n👋 Goodbye!")
#                 break

#             if not user_input:
#                 continue

#             if user_input.lower() in ['exit', 'quit', 'bye']:
#                 print("\n👋 Goodbye!")
#                 break

#             print("\n" + "-"*80)
#             print("🔄 Processing...")
#             print("-"*80 + "\n")

#             # Stream agent execution with updates mode to see subagent details
#             try:
#                 current_subagent = None

#                 async for event in openagent.astream(
#                     {"messages": [HumanMessage(content=user_input)]},
#                     config=config,
#                     stream_mode="updates",
#                     subgraphs=True
#                 ):
#                     print(event[1].keys())
#                     print(event)
#             except Exception as e:
#                 print(f"\n❌ Error: {str(e)}\n")
#                 logger.error(f"Error during execution: {str(e)}", exc_info=True)

#             print("-"*80 + "\n")

#         # Quais sao as ferramentas necessárias para um agente ser avaliado no GAIA?

#     # Run the async CLI
#     asyncio.run(run_cli())
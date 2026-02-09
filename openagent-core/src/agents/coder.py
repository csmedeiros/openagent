from dotenv import load_dotenv
import os

load_dotenv()

from langchain.agents import create_agent
from langchain.agents.middleware import FilesystemFileSearchMiddleware, TodoListMiddleware, ShellToolMiddleware

from agents.middleware import SummarizationMiddleware

# Import centralized model configuration
from agents.models import get_model

model = get_model(temperature=0.2)

import os
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_CURRENT_DIR, "prompts/coder_sys_prompt_v0.0.1.md"), "r") as f:
    sys_prompt = f.read()

sum_middlware = SummarizationMiddleware(model=model, trigger=("fraction", 0.6), keep=("fraction", 0.07))

# Local development workspace root
root_path = os.path.join(os.path.dirname(__file__), "tests")

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

def agent(state: MessagesState) -> MessagesState:
    llm = model.bind_tools(tools=tools)
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

builder.add_conditional_edges(START, should_summarize)
builder.add_edge("summarize", "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")

coder = builder.compile()

from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()

if __name__ == "__main__":

    coder.checkpointer = checkpointer

    from langfuse.langchain import CallbackHandler

    langfuse_handler = CallbackHandler()

    async def main():
        """Mini CLI app with tool call visualization"""
        print("=" * 80)
        print("OpenAgent CLI - Type 'exit' or 'quit' to end the conversation")
        print("=" * 80)
        print()

        from langchain_core.messages import HumanMessage, AIMessage
        messages = []

        while True:
            # Get user input
            user_input = input("You: ").strip()

            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("\nGoodbye!")
                break

            if not user_input:
                continue

            messages.append(HumanMessage(content=user_input))

            print("\nAssistant: ", end="", flush=True)

            assistant_message = ""
            tool_calls_made = []

            # Configure callbacks for this invocation
            config = {"callbacks": [langfuse_handler], "configurable": {"thread_id": "0"}} if langfuse_handler else {}

            async for event in coder.astream_events({"messages": messages}, config=config, version="v2"):
                kind = event["event"]

                # Stream AI response
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        assistant_message += content
                        print(content, end="", flush=True)

                # Capture tool calls
                elif kind == "on_tool_start":
                    tool_name = event["name"]
                    tool_input = event["data"].get("input", {})
                    print(f"\n\n🔧 [Tool Call: {tool_name}]", flush=True)
                    print(f"   Input: {tool_input}", flush=True)
                    tool_calls_made.append({"name": tool_name, "input": tool_input})

                # Capture tool results
                elif kind == "on_tool_end":
                    tool_output = event["data"].get("output", "")
                    print(f"   Output: {tool_output[:200]}{'...' if len(str(tool_output)) > 200 else ''}", flush=True)
                    print()

            print("\n")

            # Add assistant message to history
            if assistant_message:
                messages.append(AIMessage(content=assistant_message))

    import asyncio

    if __name__ == "__main__":
        asyncio.run(main())

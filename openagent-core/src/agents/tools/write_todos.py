from langchain.messages import ToolMessage
from langchain.tools import InjectedToolCallId, tool
from langgraph.types import Command

from typing import Any, TypedDict, Literal, Annotated
from langchain.agents.middleware.todo import Todo

@tool(parse_docstring=True)
def write_todos(
            todos: list[Todo], tool_call_id: Annotated[str, InjectedToolCallId]
        ) -> Command[Any]:
            """Create and manage a structured task list for your current work session.

            Use this tool to track progress on multi-step tasks by creating, updating,
            and managing todo items throughout your work session.

            Args:
                todos: List of todo items."""
            return Command(
                update={
                    "todos": todos,
                    "messages": [
                        ToolMessage(f"Updated todo list to {todos}", tool_call_id=tool_call_id)
                    ],
                }
            )
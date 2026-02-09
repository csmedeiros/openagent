from dotenv import load_dotenv
import os

load_dotenv()

from langchain.agents.middleware import TodoListMiddleware
from agents.middleware import SummarizationMiddleware

# Import centralized model configuration
from agents.models import get_vision_model

model = get_vision_model(temperature=0.3)

import os
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_CURRENT_DIR, "prompts/researcher_sys_prompt_v0.0.1.md"), "r") as f:
    sys_prompt = f.read()

sum_middlware = SummarizationMiddleware(model=model, trigger=("fraction", 0.6), keep=("fraction", 0.07))

# Local development workspace root
root_path = os.path.join(os.path.dirname(__file__), "tests")

from agents.tools import *
from langgraph.graph import StateGraph, START, MessagesState

# Browser tools from Playwright
from playwright.async_api import async_playwright


# Import necessary types and tools
from langchain.messages import SystemMessage
from typing import Dict, Annotated, Optional, Any
from playwright.async_api import Page, Browser
from langchain.tools import tool, InjectedState
from langgraph.types import Command
import re
import base64
from langchain.agents.middleware.types import OmitFromInput
from typing_extensions import NotRequired
from langchain.agents.middleware.todo import Todo

class ResearcherState(MessagesState):
    browser_initialized: bool = False
    todos: Annotated[NotRequired[list[Todo]], OmitFromInput] = []


# Define custom browser tools

from langchain.messages import ToolMessage


# Combine all tools including custom browser tools
tools = [
    write_todos,
    search_web,
    create_new_page, navigate_to, extract_page_text, capture_screenshot,
    get_page_elements, click_element, click_element_by_index, refresh_page_elements,
    fill_input
]

# Initialize browser - this will be None until async initialization

from langgraph.types import Send

async def initialize_browser(state: ResearcherState):
    """Initialize browser asynchronously with stealth mode"""
    if not state.get("browser_initialized", False):
        # Initialize the browser manager (singleton)
        manager = await BrowserManager.get_instance()
        await manager.get_browser()  # Ensure browser is started

        return {
            "browser_initialized": True,
            "messages": [SystemMessage(content="Browser instantiated. Now ready to create pages in the browser.")]
        }
    return {}

def agent(state: ResearcherState) -> ResearcherState:
    """Agent node that uses custom browser tools"""
    llm = model.bind_tools(tools=tools)
    response = llm.invoke([SystemMessage(content=sys_prompt)] + state["messages"])
    return {"messages": [response]}

from langgraph.prebuilt import ToolNode, tools_condition

tool_node = ToolNode(tools=tools, handle_tool_errors=True)

from agents.utils.nodes import *

builder = StateGraph(ResearcherState)

builder.add_node("tools", tool_node)
builder.add_node("agent", agent)
builder.add_node("summarize", summarize_messages_node)
builder.add_node("initialize_browser", initialize_browser)

# Initialize browser once at start
builder.add_edge(START, "initialize_browser")

# After initialization, check if summarization is needed before agent
builder.add_conditional_edges("initialize_browser", should_summarize)
builder.add_edge("summarize", "agent")

# Agent can call tools or finish (END)
builder.add_conditional_edges("agent", tools_condition)

# After tools execute, go back to agent
builder.add_edge("tools", "agent")

# Compile without checkpointer to avoid pickle errors with Playwright resources
# Playwright browser/context objects cannot be serialized
researcher = builder.compile()
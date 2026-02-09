from .browser_manager import BrowserManager
from langchain.tools import tool
import re

@tool(parse_docstring=True)
async def create_new_page(page_title: str) -> str:
    """Creates a new page in the browser for web navigation.

    Args:
        page_title: The title for the page, useful for you recognize the page and use it. Must not have ' ' (white spaces). Use '_' instead of white space
    """
    if not re.match(r"^[a-zA-Z0-9_]+$", page_title):
        return f"page_title '{page_title}' is invalid. Must contain only letters, numbers, or underscores (_)."

    try:
        manager = await BrowserManager.get_instance()
        await manager.create_page(page_title)
        return f"Page with title '{page_title}' created successfully."
    except Exception as e:
        return f"Page with title '{page_title}' could not be created due error:\n{str(e)}"

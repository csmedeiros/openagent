import base64
from typing import Annotated
from langchain.tools import tool, InjectedState, InjectedToolCallId
from langchain.messages import ToolMessage
from langgraph.types import Command
from .browser_manager import BrowserManager


@tool(parse_docstring=True)
async def capture_screenshot(
    page_title: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    full_page: bool = False
) -> Command:
    """
    Captures a screenshot of the specified browser page for VISUAL analysis only.

    IMPORTANT: Use this tool ONLY when you need to analyze visual elements like:
    - Images, diagrams, charts, or infographics
    - Page layout and design elements
    - Visual content that cannot be extracted as text

    For reading text content (articles, documentation, search results), use extract_page_text instead.

    Args:
        page_title: The title of the browser page to capture
        full_page: Whether to capture the full scrollable page (default: False)

    Returns:
        A Command object that adds the screenshot to the conversation for vision analysis

    Example:
        >>> # After navigating to a page with diagrams
        >>> screenshot = await capture_screenshot(page_title="my_page")
    """
    import base64

    manager = await BrowserManager.get_instance()
    page = manager.get_page(page_title)

    if page is None:
        return f"Page with title '{page_title}' does not exist."

    try:
        screenshot_bytes = await page.screenshot(full_page=full_page)
        base64_image = base64.b64encode(screenshot_bytes).decode('utf-8')

        return Command(
            update={
                "messages": [
                    ToolMessage(
                            content=[
                                {
                                    "type": "text",
                                    "text": "Captura de tela:\n"
                                },
                                {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                    }
                                }
                            ],
                            tool_call_id=tool_call_id
                        )
                    ]
            }
                )
    except Exception as e:
        return f"Error capturing screenshot: {str(e)}"

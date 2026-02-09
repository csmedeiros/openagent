from langchain.tools import tool
from .browser_manager import BrowserManager


@tool(parse_docstring=True)
async def navigate_to(url: str, page_title: str) -> str:
    """Navigates to a url in the specified page.

    Args:
        url: The url to navigate to.
        page_title: The browser page where you want to use for navigating.
    """

    if not url.startswith("https://"):
        return f"URL '{url}' is invalid. URLs must always start with 'https://'."

    manager = await BrowserManager.get_instance()
    page = manager.get_page(page_title)

    if page is None:
        return f"Page with title '{page_title}' does not exist."

    try:
        await page.goto(url, timeout=60000)
        return f"Navigated successfully to url {url}"
    except Exception as e:
        return f"Navigation to url {url} returned error:\n{str(e)}"

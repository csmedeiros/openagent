from typing import Annotated
from langchain.tools import tool
from .browser_manager import BrowserManager


@tool(parse_docstring=True)
async def refresh_page_elements(page_title: str) -> str:
    """
    Refreshes the element tracking on a page by clearing old data attributes.

    Use this tool when:
    - The page has dynamically loaded new content
    - Elements have changed and old selectors are not working
    - Before calling get_page_elements again after page changes

    Args:
        page_title: The title of the browser page to refresh

    Returns:
        Success message confirming the refresh

    Example:
        >>> # After page loads new content dynamically
        >>> await refresh_page_elements(page_title="my_page")
        >>> # Now call get_page_elements again to get fresh selectors
        >>> elements = await get_page_elements(page_title="my_page")
    """
    manager = await BrowserManager.get_instance()
    page = manager.get_page(page_title)

    if page is None:
        return f"Page with title '{page_title}' does not exist."

    try:
        # Remove all old data-pw-id attributes
        await page.evaluate("""
            () => {
                const elements = document.querySelectorAll('[data-pw-id]');
                elements.forEach(el => el.removeAttribute('data-pw-id'));
            }
        """)

        return f"Page elements refreshed successfully on '{page_title}'. You can now call get_page_elements to get updated selectors."

    except Exception as e:
        return f"Error refreshing page elements: {str(e)}"

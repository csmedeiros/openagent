from typing import Annotated
from langchain.tools import tool
from .browser_manager import BrowserManager


@tool(parse_docstring=True)
async def click_element_by_index(page_title: str, element_index: int, element_types: str = "a,button,input", wait_for_navigation: bool = True) -> str:
    """
    Clicks on an element by its index number from get_page_elements.

    This is a more reliable alternative to click_element when selectors fail.
    Use the index number [N] from get_page_elements output.

    Args:
        page_title: The title of the browser page containing the element
        element_index: The index number [N] from get_page_elements (e.g., 0, 1, 2)
        element_types: Same element types used in get_page_elements (default: "a,button,input")
        wait_for_navigation: Whether to wait for page navigation after clicking

    Returns:
        Success message with click confirmation

    Example:
        >>> # From get_page_elements output:
        >>> # [0] A: "Home" -> href="/home"
        >>> # [1] A: "About" -> href="/about"
        >>>
        >>> # Click on "About" link (index 1):
        >>> await click_element_by_index(page_title="my_page", element_index=1)
    """
    manager = await BrowserManager.get_instance()
    page = manager.get_page(page_title)

    if page is None:
        return f"Page with title '{page_title}' does not exist."

    try:
        # Get all visible elements and click the one at the specified index
        result = await page.evaluate("""
            (args) => {
                const { index, types } = args;
                const elementTypes = types.split(',').map(s => s.trim());
                const selector = elementTypes.join(',');
                const allElements = document.querySelectorAll(selector);

                // Filter visible elements (same logic as get_page_elements)
                const visibleElements = Array.from(allElements).filter(el => {
                    const rect = el.getBoundingClientRect();
                    const isVisible = rect.width > 0 && rect.height > 0 &&
                                     window.getComputedStyle(el).visibility !== 'hidden' &&
                                     window.getComputedStyle(el).display !== 'none';
                    return isVisible;
                });

                if (index >= visibleElements.length) {
                    return { error: `Index ${index} out of range. Only ${visibleElements.length} visible elements found.` };
                }

                const element = visibleElements[index];

                // Get element info
                const info = {
                    tag: element.tagName.toLowerCase(),
                    text: element.innerText?.trim().substring(0, 50) || element.value || '',
                    href: element.href || null
                };

                // Add a temporary unique ID for clicking
                const tempId = 'pw-click-' + Date.now();
                element.setAttribute('data-pw-click', tempId);

                return { success: true, tempId: tempId, info: info };
            }
        """, {"index": element_index, "types": element_types})

        if 'error' in result:
            return result['error']

        # Click using the temporary selector
        temp_selector = f"[data-pw-click='{result['tempId']}']"
        element_info = result['info']

        if wait_for_navigation:
            try:
                async with page.expect_navigation(timeout=10000, wait_until='domcontentloaded'):
                    await page.click(temp_selector, timeout=5000)
                new_url = page.url
                return f"Clicked on {element_info['tag']} \"{element_info['text']}\" (index {element_index}) successfully. Navigated to: {new_url}"
            except:
                try:
                    await page.click(temp_selector, timeout=5000)
                    return f"Clicked on {element_info['tag']} \"{element_info['text']}\" (index {element_index}) successfully. No navigation occurred."
                except Exception as e:
                    return f"Clicked element but encountered issue: {str(e)}"
        else:
            await page.click(temp_selector, timeout=5000)
            return f"Clicked on {element_info['tag']} \"{element_info['text']}\" (index {element_index}) successfully."

    except Exception as e:
        return f"Error clicking element at index {element_index}: {str(e)}"

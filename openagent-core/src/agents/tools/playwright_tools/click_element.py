from typing import Annotated
from langchain.tools import tool, InjectedState
from .browser_manager import BrowserManager


@tool(parse_docstring=True)
async def click_element(page_title: str, selector: str, element_text: str = "", wait_for_navigation: bool = True) -> str:
    """
    Clicks on an element in the specified browser page.
    Use this tool to interact with clickable elements like links, buttons, or any interactive element.
    Get the selector from the get_page_elements tool first.

    Args:
        page_title: The title of the browser page containing the element
        selector: The CSS selector for the element to click (from get_page_elements tool)
        element_text: Optional text content of the element for fallback matching
        wait_for_navigation: Whether to wait for page navigation after clicking. Set to False for elements that don't trigger navigation (like modals)
    """
    manager = await BrowserManager.get_instance()
    page = manager.get_page(page_title)

    if page is None:
        return f"Page with title '{page_title}' does not exist."

    try:
        # Try primary selector first
        element_found = False
        try:
            await page.wait_for_selector(selector, timeout=3000, state='visible')
            element_found = True
            actual_selector = selector
        except:
            # If data-pw-id selector fails, try fallback with text matching
            if element_text and selector.startswith('[data-pw-id'):
                try:
                    # Try to find element by text content as fallback
                    actual_selector = await page.evaluate("""
                        (text) => {
                            const elements = document.querySelectorAll('a, button, input, [role="button"]');
                            for (const el of elements) {
                                const elementText = (el.innerText || el.value || '').trim();
                                if (elementText.includes(text) || text.includes(elementText.substring(0, 30))) {
                                    // Add temporary selector
                                    const tempId = 'pw-temp-' + Date.now();
                                    el.setAttribute('data-pw-temp', tempId);
                                    return `[data-pw-temp="${tempId}"]`;
                                }
                            }
                            return null;
                        }
                    """, element_text[:50])

                    if actual_selector:
                        await page.wait_for_selector(actual_selector, timeout=2000, state='visible')
                        element_found = True
                except:
                    pass

            if not element_found:
                return f"Element with selector '{selector}' not found or not visible on page '{page_title}'. Try using refresh_page_elements and get_page_elements again."

        # Get element info before clicking using safer evaluation
        element_info = await page.evaluate("""
            (sel) => {
                const el = document.querySelector(sel);
                if (!el) return null;
                return {
                    tag: el.tagName.toLowerCase(),
                    text: el.innerText?.trim().substring(0, 50) || el.value || '',
                    href: el.href || null
                };
            }
        """, actual_selector)

        if not element_info:
            return f"Element with selector '{selector}' exists but could not be accessed."

        # Click the element with better error handling
        if wait_for_navigation:
            try:
                # Try to click and wait for navigation
                async with page.expect_navigation(timeout=10000, wait_until='domcontentloaded'):
                    await page.click(actual_selector, timeout=5000)
                new_url = page.url
                return f"Clicked on {element_info['tag']} \"{element_info['text']}\" successfully. Navigated to: {new_url}"
            except Exception as nav_error:
                # Navigation timeout or didn't happen - still try the click
                try:
                    await page.click(actual_selector, timeout=5000)
                    return f"Clicked on {element_info['tag']} \"{element_info['text']}\" successfully. No navigation occurred."
                except Exception as click_error:
                    return f"Clicked element but encountered issue: {str(click_error)}"
        else:
            await page.click(actual_selector, timeout=5000)
            return f"Clicked on {element_info['tag']} \"{element_info['text']}\" successfully."

    except Exception as e:
        return f"Error clicking element with selector '{selector}': {str(e)}"

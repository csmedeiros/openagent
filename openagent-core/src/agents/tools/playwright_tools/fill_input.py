from typing import Annotated
from langchain.tools import tool
from .browser_manager import BrowserManager


@tool(parse_docstring=True)
async def fill_input(page_title: str, element_index: int, value: str, element_types: str = "input,textarea") -> str:
    """
    Fills an input field or textarea with the specified value.

    Use this tool to enter text into form fields, search boxes, or any text input element.
    Get the element index from get_page_elements first (using element_types="input,textarea").

    Args:
        page_title: The title of the browser page containing the input field
        element_index: The index number [N] from get_page_elements (e.g., 0, 1, 2)
        value: The text value to fill into the input field
        element_types: Types of input elements to target (default: "input,textarea")

    Returns:
        Success message with filled value confirmation

    Example:
        >>> # From get_page_elements output:
        >>> # [0] INPUT: "Search" -> type="text"
        >>> # [1] INPUT: "Email" -> type="email"
        >>>
        >>> # Fill the email field (index 1):
        >>> await fill_input(page_title="my_page", element_index=1, value="user@example.com")
    """
    manager = await BrowserManager.get_instance()
    page = manager.get_page(page_title)

    if page is None:
        return f"Page with title '{page_title}' does not exist."

    try:
        # Get all visible input elements and fill the one at the specified index
        result = await page.evaluate("""
            (params) => {
                const { index, types } = params;
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
                    return { error: `Index ${index} out of range. Only ${visibleElements.length} visible input elements found.` };
                }

                const element = visibleElements[index];

                // Get element info
                const info = {
                    tag: element.tagName.toLowerCase(),
                    type: element.type || 'text',
                    placeholder: element.placeholder || '',
                    name: element.name || '',
                    id: element.id || ''
                };

                // Add a temporary unique ID for filling
                const tempId = 'pw-fill-' + Date.now();
                element.setAttribute('data-pw-fill', tempId);

                return { success: true, tempId: tempId, info: info };
            }
        """, {"index": element_index, "types": element_types})

        if 'error' in result:
            return result['error']

        # Fill using the temporary selector
        temp_selector = f"[data-pw-fill='{result['tempId']}']"
        element_info = result['info']

        try:
            # Clear existing value first
            await page.fill(temp_selector, '', timeout=5000)
            # Fill with new value
            await page.fill(temp_selector, value, timeout=5000)

            return f"Filled {element_info['tag']} (type={element_info['type']}, index {element_index}) with value: \"{value[:50]}{'...' if len(value) > 50 else ''}\""

        except Exception as e:
            return f"Error filling input at index {element_index}: {str(e)}"

    except Exception as e:
        return f"Error accessing input element at index {element_index}: {str(e)}"

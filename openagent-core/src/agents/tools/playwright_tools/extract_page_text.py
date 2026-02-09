from langchain.tools import tool
from .browser_manager import BrowserManager


@tool(parse_docstring=True)
async def extract_page_text(page_title: str) -> str:
    """
    Extracts structured text content from the specified browser page with element type annotations.

    This is the PRIMARY tool for understanding the page structure and content.
    Use this FIRST before attempting to interact with page elements.

    The extracted text includes markers like [BUTTON], [INPUT:type], [LINK], [FORM], etc.
    to help you identify interactive elements and understand the page layout.

    Args:
        page_title: The title of the browser page to extract text from

    Returns:
        The structured text content with element type markers

    Example:
        >>> # After navigating to a page, extract text to understand structure
        >>> text = await extract_page_text(page_title="my_page")
        >>> # Output will show: "[BUTTON] Submit [INPUT:text] Search [LINK] Home ..."
        >>> # Then use get_page_elements to get selectors for interaction
    """
    manager = await BrowserManager.get_instance()
    page = manager.get_page(page_title)

    if page is None:
        return f"Page with title '{page_title}' does not exist."

    try:
        # Extract structured text content with element type markers
        text_content = await page.evaluate("""
            () => {
                // Function to get element type and role
                function getElementInfo(el) {
                    const tag = el.tagName.toLowerCase();
                    const role = el.getAttribute('role');
                    const type = el.getAttribute('type');

                    // Determine element category
                    if (tag === 'button' || role === 'button') {
                        return '[BUTTON]';
                    } else if (tag === 'input') {
                        return `[INPUT:${type || 'text'}]`;
                    } else if (tag === 'textarea') {
                        return '[TEXTAREA]';
                    } else if (tag === 'a') {
                        return '[LINK]';
                    } else if (tag === 'article') {
                        return '[ARTICLE]';
                    } else if (tag === 'nav') {
                        return '[NAV]';
                    } else if (tag === 'header') {
                        return '[HEADER]';
                    } else if (tag === 'footer') {
                        return '[FOOTER]';
                    } else if (tag === 'form') {
                        return '[FORM]';
                    } else if (['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(tag)) {
                        return `[${tag.toUpperCase()}]`;
                    } else if (tag === 'select') {
                        return '[SELECT]';
                    } else if (role === 'listbox') {
                        return '[LISTBOX]';
                    } else if (role === 'menu') {
                        return '[MENU]';
                    }
                    return '';
                }

                // Remove script and style elements
                const scripts = document.querySelectorAll('script, style');
                scripts.forEach(el => el.remove());

                // Process the body content recursively
                function processNode(node) {
                    if (node.nodeType === Node.TEXT_NODE) {
                        return node.textContent.trim();
                    }

                    if (node.nodeType === Node.ELEMENT_NODE) {
                        const tag = getElementInfo(node);
                        let result = '';

                        // Add opening tag if it's a special element
                        if (tag) {
                            result += tag + ' ';
                        }

                        // Process children
                        for (const child of node.childNodes) {
                            result += processNode(child);
                        }

                        return result + ' ';
                    }

                    return '';
                }

                return processNode(document.body).replace(/\s+/g, ' ').trim();
            }
        """)

        return f"Structured text content from page '{page_title}':\n\n{text_content}"
    except Exception as e:
        return f"Error extracting text from page: {str(e)}"

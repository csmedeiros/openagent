from typing import Annotated
from langchain.tools import tool, InjectedState
from .browser_manager import BrowserManager


@tool(parse_docstring=True)
async def get_page_elements(page_title: str, element_types: str = "a,button,input") -> str:
    """
    Extracts interactive elements from the page with their selector paths.

    This tool retrieves all interactive elements (links, buttons, inputs, etc.) from the page
    and returns them with unique selectors that can be used with the click_element tool.

    Args:
        page_title: The title of the browser page to extract elements from
        element_types: Comma-separated list of element types to extract (default: "a,button,input")  """
    manager = await BrowserManager.get_instance()
    page = manager.get_page(page_title)

    if page is None:
        return f"Page with title '{page_title}' does not exist."

    try:
        # JavaScript to extract interactive elements with their metadata
        # Add unique data attributes to elements for reliable selection
        elements_data = await page.evaluate(f"""
            () => {{
                const elementTypes = '{element_types}'.split(',').map(s => s.trim());
                const selector = elementTypes.join(',');
                const elements = document.querySelectorAll(selector);

                return Array.from(elements).map((el, globalIndex) => {{
                    const rect = el.getBoundingClientRect();
                    const isVisible = rect.width > 0 && rect.height > 0 &&
                                     window.getComputedStyle(el).visibility !== 'hidden' &&
                                     window.getComputedStyle(el).display !== 'none';

                    // Add a unique data attribute to the element for reliable selection
                    const uniqueId = `pw-element-${{globalIndex}}-${{Date.now()}}`;
                    el.setAttribute('data-pw-id', uniqueId);

                    // Build selector - prefer data attribute for reliability
                    let uniqueSelector = `[data-pw-id="${{uniqueId}}"]`;

                    // Fallback selectors for reference
                    let fallbackSelector = '';
                    if (el.id) {{
                        fallbackSelector = `#${{el.id}}`;
                    }} else {{
                        const tagName = el.tagName.toLowerCase();
                        // Use XPath-style position for more reliable selection
                        const parent = el.parentElement;
                        if (parent) {{
                            const allSiblings = Array.from(parent.children);
                            const position = allSiblings.indexOf(el) + 1;

                            if (parent.id) {{
                                fallbackSelector = `#${{parent.id}} > :nth-child(${{position}})`;
                            }} else {{
                                // Get a more specific path
                                fallbackSelector = `${{tagName}}:nth-child(${{position}})`;
                            }}
                        }} else {{
                            fallbackSelector = tagName;
                        }}
                    }}

                    return {{
                        index: globalIndex,
                        tag: el.tagName.toLowerCase(),
                        text: el.innerText?.trim().substring(0, 100) || el.value || '',
                        href: el.href || null,
                        type: el.type || null,
                        ariaLabel: el.getAttribute('aria-label'),
                        title: el.getAttribute('title'),
                        selector: uniqueSelector,
                        fallbackSelector: fallbackSelector,
                        isVisible: isVisible
                    }};
                }}).filter(el => el.isVisible);  // Only return visible elements
            }}
        """)

        if not elements_data:
            return f"No interactive elements found on page '{page_title}'."

        # Format the output
        output_lines = [f"Interactive elements on page '{page_title}':\n"]

        for el in elements_data:
            # Build the element description
            element_type = el['tag'].upper()
            text = el['text'] or el['ariaLabel'] or el['title'] or '(no text)'

            description = f"[{el['index']}] {element_type}: \"{text}\""

            # Add additional attributes
            if el['href']:
                description += f" -> href=\"{el['href']}\""
            if el['type']:
                description += f" (type={el['type']})"

            description += f"\n    Selector: {el['selector']}"
            description += f"\n    Text: {text}"  # Include text for fallback matching

            output_lines.append(description)

        return "\n".join(output_lines)

    except Exception as e:
        return f"Error extracting elements from page: {str(e)}"

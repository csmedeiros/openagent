from pydantic_ai import Agent, RunContext
from pydantic_ai.models.huggingface import HuggingFaceModel
from pydantic_ai.providers.huggingface import HuggingFaceProvider
from dotenv import load_dotenv
from huggingface_hub import AsyncInferenceClient
from dataclasses import dataclass
from typing import Optional
import re
import base64
import os
from playwright.async_api import Page, Browser

load_dotenv()
from langfuse import get_client
 
langfuse = get_client()
 
# Verify connection
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")

Agent.instrument_all()

# Import browser manager
import sys
sys.path.append("/Users/claudiomedeiros/Documents/openagent/openagent-core/src")
from agents.tools.playwright_tools.browser_manager import BrowserManager
from langchain.agents.middleware.todo import Todo
from typing_extensions import NotRequired
from operator import add
from typing import List, Annotated


# Define dependencies dataclass for managing browser state
@dataclass
class BrowserDeps:
    """Dependencies for browser operations"""
    todos: Annotated[List[Todo], add]
    browser_manager: Optional[BrowserManager] = None

    async def get_manager(self) -> BrowserManager:
        """Get or create browser manager instance"""
        if self.browser_manager is None:
            self.browser_manager = await BrowserManager.get_instance()
        return self.browser_manager

client = AsyncInferenceClient(provider="novita")

with open("/Users/claudiomedeiros/Documents/openagent/openagent-core/src/agents/prompts/researcher_sys_prompt_v0.0.1.md", "r") as f:
    sys_prompt = f.read()

model = HuggingFaceModel("moonshotai/Kimi-K2.5", provider=HuggingFaceProvider(hf_client=client))

from pydantic import BaseModel, Field
from typing import Literal

class TaskMessage(BaseModel):
    completed: bool = Field(description="If the task is completed or not.")
    message: str = Field(description="Message to send to the user or to the OpenAgent")
    to: Literal['user', 'openagent'] = Field(description="The message receiver, if will the the user or the openagent")


# Create agent with BrowserDeps
agent = Agent(
    model=model,
    system_prompt=sys_prompt.replace("<SCHEMA>", str(TaskMessage.model_json_schema())),
    deps_type=BrowserDeps,
    retries=5,
    output_type=TaskMessage,
)

# File System Tools

@agent.tool
async def write_file(ctx: RunContext[BrowserDeps], file_path: str, content: str, append: bool = False) -> str:
    """Writes content to a file.

    Args:
        file_path: Path to the file to write (must be in /Users/claudiomedeiros/Documents/openagent/openagent-core/src/agents/tests/)
        content: Content to write to the file
        append: If True, appends to the end of the file. If False, overwrites the file.
    """
    import aiofiles
    import os

    # Validate path is within allowed directory
    allowed_root = "/Users/claudiomedeiros/Documents/openagent/openagent-core/src/agents/tests"
    abs_path = os.path.abspath(file_path)

    if not abs_path.startswith(allowed_root):
        return f"Error: file_path must be within {allowed_root}"

    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        mode = 'a' if append else 'w'
        async with aiofiles.open(abs_path, mode, encoding='utf-8') as f:
            await f.write(content)

        action = "Appended to" if append else "Wrote"
        return f"{action} file: {file_path}"
    except Exception as e:
        return f"Failed to write file: {str(e)}"


@agent.tool
async def read_file(ctx: RunContext[BrowserDeps], file_path: str) -> str:
    """Reads a text-readable file content.

    Args:
        file_path: Path to the file to read
    """
    import aiofiles
    import os

    try:
        abs_path = os.path.abspath(file_path)

        async with aiofiles.open(abs_path, 'r', encoding='utf-8') as f:
            content = await f.read()

        return content
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        return f"Failed to read file: {str(e)}"


@agent.tool
async def shell_tool(ctx: RunContext[BrowserDeps], command: str, cwd: str = None) -> str:
    """Executes a shell command asynchronously and returns the output.

    Args:
        command: The shell command to execute
        cwd: Optional working directory for the command. Defaults to tests directory.
    """
    import asyncio
    import os

    # Default to workspace tests directory
    if cwd is None:
        cwd = "/Users/claudiomedeiros/Documents/openagent/openagent-core/src/agents/tests"

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )

        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)

        output = stdout.decode() if stdout else ""
        error = stderr.decode() if stderr else ""

        if process.returncode != 0:
            return f"Command failed with code {process.returncode}:\n{error}"

        return output or "Command executed successfully (no output)"
    except asyncio.TimeoutError:
        return "Command timed out after 30 seconds"
    except Exception as e:
        return f"Failed to execute command: {str(e)}"


# Web Search Tool

@agent.tool
async def search_web(ctx: RunContext[BrowserDeps], query: str, max_results: int = 5) -> str:
    """Searches the web using Tavily and returns results.

    This tool performs a direct web search optimized for AI agents.
    Use this for quick information gathering.

    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 5, max: 10)
    """
    try:
        from tavily import TavilyClient

        max_results = min(max_results, 10)  # Cap at 10 results

        # Get Tavily API key from environment
        api_key = os.getenv('TAVILY_API_KEY')
        if not api_key:
            return "Error: TAVILY_API_KEY environment variable not set. Get your API key at https://tavily.com"

        # Initialize Tavily client
        tavily = TavilyClient(api_key=api_key)

        # Search using Tavily
        response = tavily.search(query=query, max_results=max_results)

        if not response or 'results' not in response or not response['results']:
            return f"No results found for query: {query}"

        # Format results
        formatted_results = [f"🔍 Search results for: '{query}'\n"]

        for idx, result in enumerate(response['results'], 1):
            title = result.get('title', 'No title')
            url = result.get('url', 'No URL')
            snippet = result.get('content', 'No description')

            formatted_results.append(
                f"\n{idx}. **{title}**\n"
                f"   URL: {url}\n"
                f"   {snippet[:200]}{'...' if len(snippet) > 200 else ''}\n"
            )

        return ''.join(formatted_results)

    except ImportError:
        return "Error: tavily-python library not installed. Install with: pip install tavily-python"
    except Exception as e:
        return f"Search failed: {str(e)}"


# Browser Tools

@agent.tool
async def create_new_page(ctx: RunContext[BrowserDeps], page_title: str) -> str:
    """Creates a new page in the browser for web navigation.

    Args:
        page_title: The title for the page, useful for you recognize the page and use it.
                   Must not have ' ' (white spaces). Use '_' instead of white space
    """
    if not re.match(r"^[a-zA-Z0-9_]+$", page_title):
        return f"page_title '{page_title}' is invalid. Must contain only letters, numbers, or underscores (_)."

    try:
        manager = await ctx.deps.get_manager()
        await manager.create_page(page_title)
        return f"Page with title '{page_title}' created successfully."
    except Exception as e:
        return f"Page with title '{page_title}' could not be created due error:\n{str(e)}"


@agent.tool
async def navigate_to(ctx: RunContext[BrowserDeps], page_title: str, url: str) -> str:
    """Navigates to a URL in the specified page.

    Args:
        page_title: The title of the page to navigate
        url: The URL to navigate to
    """
    try:
        manager = await ctx.deps.get_manager()
        page = manager.get_page(page_title)

        if page is None:
            return f"Page '{page_title}' not found. Create it first using create_new_page."

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return f"Successfully navigated to {url}"
    except Exception as e:
        return f"Failed to navigate to {url}: {str(e)}"


@agent.tool
async def extract_page_text(ctx: RunContext[BrowserDeps], page_title: str) -> str:
    """Extracts structured text with element markers from the page.

    Returns text with markers like [BUTTON], [INPUT:text], [LINK], [FORM], etc.
    This gives you a complete overview of the page structure.

    Args:
        page_title: The title of the page to extract text from
    """
    try:
        manager = await ctx.deps.get_manager()
        page = manager.get_page(page_title)

        if page is None:
            return f"Page '{page_title}' not found."

        # Extract text with element markers
        text_content = await page.evaluate("""
            () => {
                const result = [];
                const walk = (node) => {
                    if (node.nodeType === Node.TEXT_NODE) {
                        const text = node.textContent.trim();
                        if (text) result.push(text);
                    } else if (node.nodeType === Node.ELEMENT_NODE) {
                        const tag = node.tagName.toLowerCase();

                        if (tag === 'button') {
                            result.push(`[BUTTON] ${node.textContent.trim()}`);
                        } else if (tag === 'input') {
                            const type = node.getAttribute('type') || 'text';
                            const placeholder = node.getAttribute('placeholder') || '';
                            result.push(`[INPUT:${type}] ${placeholder}`);
                        } else if (tag === 'a') {
                            result.push(`[LINK] ${node.textContent.trim()}`);
                        } else if (tag === 'form') {
                            result.push('[FORM]');
                            for (const child of node.children) walk(child);
                            result.push('[/FORM]');
                            return;
                        } else {
                            for (const child of node.childNodes) walk(child);
                        }
                    }
                };
                walk(document.body);
                return result.join(' ');
            }
        """)

        return text_content[:10000]  # Limit to 10k chars
    except Exception as e:
        return f"Failed to extract text: {str(e)}"


@agent.tool
async def capture_screenshot(ctx: RunContext[BrowserDeps], page_title: str) -> str:
    """Captures a screenshot of the current page for visual analysis.

    Use ONLY for analyzing VISUAL elements (images, diagrams, charts, infographics, page layout).
    Do NOT use for reading text - use extract_page_text instead.

    Args:
        page_title: The title of the page to screenshot
    """
    try:
        manager = await ctx.deps.get_manager()
        page = manager.get_page(page_title)

        if page is None:
            return f"Page '{page_title}' not found."

        screenshot_bytes = await page.screenshot(full_page=True)
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')

        return f"Screenshot captured successfully. Base64 data: {screenshot_base64[:100]}..."
    except Exception as e:
        return f"Failed to capture screenshot: {str(e)}"


@agent.tool
async def get_page_elements(ctx: RunContext[BrowserDeps], page_title: str, element_types: str = "button,input,a") -> str:
    """Lists all interactive elements with their CSS selectors.

    Use this AFTER extract_page_text to get exact selectors for elements you want to interact with.

    Args:
        page_title: The title of the page
        element_types: Comma-separated element types to search for (e.g., "button,input,a")
    """
    try:
        manager = await ctx.deps.get_manager()
        page = manager.get_page(page_title)

        if page is None:
            return f"Page '{page_title}' not found."

        types = [t.strip() for t in element_types.split(',')]
        elements = []

        for element_type in types:
            locators = await page.locator(element_type).all()
            for idx, loc in enumerate(locators):
                text = await loc.text_content() or ""
                selector = f"[data-pw-id='{await loc.get_attribute('data-pw-id')}']"
                elements.append(f"[{idx}] {element_type.upper()}: \"{text.strip()[:50]}\" -> {selector}")

        return "\n".join(elements) if elements else f"No {element_types} elements found."
    except Exception as e:
        return f"Failed to get elements: {str(e)}"


@agent.tool
async def click_element(ctx: RunContext[BrowserDeps], page_title: str, selector: str) -> str:
    """Clicks an element using CSS selector from get_page_elements.

    Args:
        page_title: The title of the page
        selector: The CSS selector from get_page_elements output
    """
    try:
        manager = await ctx.deps.get_manager()
        page = manager.get_page(page_title)

        if page is None:
            return f"Page '{page_title}' not found."

        await page.click(selector, timeout=10000)
        await page.wait_for_load_state("domcontentloaded")

        return f"Successfully clicked element: {selector}"
    except Exception as e:
        return f"Failed to click element: {str(e)}"


@agent.tool
async def click_element_by_index(ctx: RunContext[BrowserDeps], page_title: str, element_type: str, index: int) -> str:
    """Alternative method to click using index numbers.

    Args:
        page_title: The title of the page
        element_type: Type of element (button, input, a, etc.)
        index: The index number from get_page_elements
    """
    try:
        manager = await ctx.deps.get_manager()
        page = manager.get_page(page_title)

        if page is None:
            return f"Page '{page_title}' not found."

        locators = await page.locator(element_type).all()

        if index >= len(locators):
            return f"Index {index} out of range. Found {len(locators)} {element_type} elements."

        await locators[index].click(timeout=10000)
        await page.wait_for_load_state("domcontentloaded")

        return f"Successfully clicked {element_type} at index {index}"
    except Exception as e:
        return f"Failed to click element: {str(e)}"


@agent.tool
async def fill_input(ctx: RunContext[BrowserDeps], page_title: str, selector: str, value: str) -> str:
    """Fills an input field using CSS selector.

    Args:
        page_title: The title of the page
        selector: The CSS selector from get_page_elements
        value: The value to fill
    """
    try:
        manager = await ctx.deps.get_manager()
        page = manager.get_page(page_title)

        if page is None:
            return f"Page '{page_title}' not found."

        await page.fill(selector, value, timeout=10000)

        return f"Successfully filled input {selector} with value: {value}"
    except Exception as e:
        return f"Failed to fill input: {str(e)}"


@agent.tool
async def refresh_page_elements(ctx: RunContext[BrowserDeps], page_title: str) -> str:
    """Refreshes element tracking after page changes.

    Use when elements have dynamically loaded or changed.

    Args:
        page_title: The title of the page
    """
    try:
        manager = await ctx.deps.get_manager()
        page = manager.get_page(page_title)

        if page is None:
            return f"Page '{page_title}' not found."

        await page.wait_for_load_state("networkidle", timeout=5000)

        return f"Page elements refreshed for '{page_title}'"
    except Exception as e:
        return f"Failed to refresh elements: {str(e)}"



if __name__ == "__main__":
    # Run the agent with streaming
    # import asyncio

    # async def stream_agent(message: str):
    #     """Stream agent execution with event details"""
    #     deps = BrowserDeps(todos=[])

    #     print(f"\n{'='*80}")
    #     print(f"🤖 Researcher Agent - Streaming Mode")
    #     print(f"{'='*80}\n")
    #     print(f"📝 Query: {message}\n")
    #     print(f"{'='*80}\n")

    #     try:
    #         async with agent.run_stream(message, deps=deps) as result:
    #             # Stream events as they arrive
    #             print("📡 Streaming events:\n")

    #             async for event in result.stream_output():
    #                 if event.kind == 'tool-call':
    #                     print(f"\n🔧 Tool Call: {event.tool_name}")
    #                     print(f"   Args: {event.tool_args}")

    #                 elif event.kind == 'tool-return':
    #                     print(f"\n✓ Tool Return: {event.tool_name}")
    #                     result_str = str(event.tool_return)[:200]
    #                     print(f"   Result: {result_str}{'...' if len(str(event.tool_return)) > 200 else ''}")

    #                 elif event.kind == 'text':
    #                     # Stream text deltas
    #                     print(event.text, end='', flush=True)

    #             print("\n\n" + "="*80)
    #             print("✓ Task completed!")
    #             print("="*80 + "\n")

    #             # Get final result
    #             final_result = await result.get_data()

    #             print(f"📊 Final Result:")
    #             print(f"  - Completed: {final_result.completed}")
    #             print(f"  - To: {final_result.to}")
    #             print(f"  - Message: {final_result.message[:200]}{'...' if len(final_result.message) > 200 else ''}\n")

    #             # Get usage info
    #             usage = result.usage()
    #             print(f"📈 Usage Statistics:")
    #             print(f"  - Total requests: {usage.requests}")
    #             print(f"  - Total tokens: {usage.total_tokens}")
    #             print(f"  - Input tokens: {usage.request_tokens}")
    #             print(f"  - Output tokens: {usage.response_tokens}")

    #     except Exception as e:
    #         print(f"\n❌ Error: {str(e)}")
    #         import traceback
    #         traceback.print_exc()

    # # Run with a test query
    # asyncio.run(stream_agent("Quais tools um agente deve ter para ser avaliado no GAIA?"))
    agent.to_cli_sync(deps=BrowserDeps(todos=[]), prog_name="Researcher")
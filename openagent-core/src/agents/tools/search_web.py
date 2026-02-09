"""
Web Search Tool using Tavily
"""
from langchain.tools import tool
import os

@tool
def search_web(query: str, max_results: int = 5) -> str:
    """Searches the web using Tavily and returns results.

    This tool performs a direct web search optimized for AI agents.
    Use this for quick information gathering and URL discovery.

    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 5, max: 10)

    Returns:
        Formatted search results with titles, URLs, and snippets
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

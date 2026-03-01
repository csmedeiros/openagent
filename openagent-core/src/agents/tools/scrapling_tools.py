from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient(
    {
        "scraper": {
            "transport": "http",  # HTTP-based remote server
            # Ensure you start your weather server on port 8000
            "url": "http://localhost:8000/mcp",
        }
    }
)

async def get_scrapling_tools():
    scrapling_tools = await client.get_tools()
    return scrapling_tools
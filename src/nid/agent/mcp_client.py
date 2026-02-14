"""
MCP (Model Context Protocol) utilities.
"""

from fastmcp import Client


def setup_mcp_client(mcp_path: str = "search.py") -> Client:
    """
    Setup MCP client.
    
    Args:
        mcp_path: Path to MCP server script
        
    Returns:
        Configured MCP client
    """
    return Client(mcp_path)


async def get_tools(mcp_client: Client) -> list[dict]:
    """
    Get tool definitions from MCP client.
    
    Args:
        mcp_client: MCP client instance
        
    Returns:
        List of tool definitions in OpenAI format
    """
    mcp_tools = await mcp_client.list_tools()
    tools = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema,
            },
        }
        for tool in mcp_tools
    ]
    return tools

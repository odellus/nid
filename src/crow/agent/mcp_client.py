"""
MCP client setup and tool extraction.

MCP servers are passed by the ACP client in new_session/load_session calls.
We just need to convert ACP MCP server objects to FastMCP clients.
"""

import logging
from typing import Any

from fastmcp import Client as MCPClient
from acp.schema import HttpMcpServer, SseMcpServer, McpServerStdio

logger = logging.getLogger(__name__)


async def create_mcp_client_from_acp(
    mcp_server: HttpMcpServer | SseMcpServer | McpServerStdio
) -> MCPClient:
    """
    Create an MCP client from ACP MCP server configuration.
    
    Args:
        mcp_server: MCP server configuration from ACP client
        
    Returns:
        FastMCP Client instance
    """
    # If no servers provided, use builtin crow-mcp-server
    # Import from installed package (NO sys.path bullshit)
    from crow_mcp_server.main import mcp as builtin_mcp
    return MCPClient(transport=builtin_mcp)


async def get_tools(mcp_client: MCPClient) -> list[dict[str, Any]]:
    """
    Extract tools from an MCP client.
    
    Args:
        mcp_client: Connected MCP client
        
    Returns:
        List of tool definitions in OpenAI format
    """
    tools_result = await mcp_client.list_tools()
    tools = []
    
    for t in tools_result:
        tools.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.inputSchema,
            }
        })
    
    logger.info(f"Retrieved {len(tools)} tools from MCP server")
    return tools


# Legacy function for backwards compatibility  
def setup_mcp_client(mcp_path: str = "search.py") -> MCPClient:
    """
    Setup MCP client (legacy compatibility).
    
    DEPRECATED: Use create_mcp_client_from_acp instead.
    """
    logger.warning("setup_mcp_client is deprecated, use create_mcp_client_from_acp")
    return MCPClient(mcp_path)

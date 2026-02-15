"""
MCP client setup and tool extraction.

MCP servers are passed by the ACP client in new_session/load_session calls.
We convert ACP MCP server objects to FastMCP clients.
"""

import logging
from typing import Any

from fastmcp import Client as MCPClient
from acp.schema import HttpMcpServer, SseMcpServer, McpServerStdio

from crow.agent.mcp_config import acp_to_fastmcp_config

logger = logging.getLogger(__name__)


async def create_mcp_client_from_acp(
    mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio]
) -> MCPClient:
    """
    Create an MCP client from ACP MCP server configurations.
    
    If no servers are provided, use the builtin crow-mcp-server.
    
    Args:
        mcp_servers: List of MCP server configurations from ACP client
        
    Returns:
        FastMCP Client instance
        
    Example:
        >>> from acp.schema import McpServerStdio
        >>> servers = [
        ...     McpServerStdio(
        ...         name="crow-builtin",
        ...         command="uv",
        ...         args=["--project", ".", "run", "server.py"],
        ...         env=[]
        ...     )
        ... ]
        >>> client = await create_mcp_client_from_acp(servers)
        >>> async with client:
        ...     tools = await client.list_tools()
    """
    if not mcp_servers:
        # No servers provided - use builtin crow-mcp-server (in-memory for performance)
        # Import from installed package (NO sys.path bullshit)
        logger.info("No MCP servers provided, using builtin crow-mcp-server")
        from crow_mcp_server.main import mcp as builtin_mcp
        return MCPClient(builtin_mcp)
    
    # Convert ACP format to FastMCP config dict
    logger.info(f"Creating FastMCP client from {len(mcp_servers)} ACP servers")
    config = acp_to_fastmcp_config(mcp_servers)
    
    # Create FastMCP client from config
    return MCPClient(config)


def create_mcp_client_from_config(config: dict[str, Any]) -> MCPClient:
    """
    Create an MCP client from a config dict (FastMCP format).
    
    This is a convenience function for using MCP directly in Python scripts.
    
    Args:
        config: MCP configuration dict in FastMCP format
        
    Returns:
        FastMCP Client instance (must be used with async with)
        
    Example:
        >>> config = {
        ...     "mcpServers": {
        ...         "crow-builtin": {
        ...             "command": "uv",
        ...             "args": ["--project", "crow-mcp-server", "run", "."],
        ...         }
        ...     }
        ... }
        >>> client = create_mcp_client_from_config(config)
        >>> async with client:
        ...     tools = await client.list_tools()
    """
    return MCPClient(config)


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

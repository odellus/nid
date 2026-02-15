"""
MCP server configuration conversion utilities.

Converts ACP protocol MCP server configurations to FastMCP client format.
"""

import logging
from typing import Any

from acp.schema import HttpMcpServer, SseMcpServer, McpServerStdio

logger = logging.getLogger(__name__)


def acp_to_fastmcp_config(
    mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio]
) -> dict[str, Any]:
    """
    Convert ACP mcp_servers to FastMCP configuration dict.
    
    ACP protocol uses structured types with List[EnvVariable] and List[HttpHeader].
    FastMCP expects dict[str, str] for environment variables and headers.
    
    Args:
        mcp_servers: List of MCP server configurations from ACP client
        
    Returns:
        FastMCP configuration dict with "mcpServers" key
        
    Example:
        >>> from acp.schema import McpServerStdio, EnvVariable
        >>> servers = [
        ...     McpServerStdio(
        ...         name="crow-builtin",
        ...         command="uv",
        ...         args=["--project", ".", "run", "server.py"],
        ...         env=[EnvVariable(name="DEBUG", value="true")]
        ...     )
        ... ]
        >>> config = acp_to_fastmcp_config(servers)
        >>> config["mcpServers"]["crow-builtin"]["command"]
        'uv'
        >>> config["mcpServers"]["crow-builtin"]["env"]["DEBUG"]
        'true'
    """
    config: dict[str, Any] = {"mcpServers": {}}
    
    for server in mcp_servers:
        if isinstance(server, McpServerStdio):
            # Convert List[EnvVariable] to dict[str, str]
            env_dict = {e.name: e.value for e in server.env}
            
            config["mcpServers"][server.name] = {
                "transport": "stdio",
                "command": server.command,
                "args": server.args,
                "env": env_dict,
            }
            
            logger.debug(
                f"Converted stdio MCP server '{server.name}': "
                f"command={server.command}, args={server.args}"
            )
            
        elif isinstance(server, HttpMcpServer):
            # Convert List[HttpHeader] to dict[str, str]
            headers_dict = {h.name: h.value for h in server.headers}
            
            config["mcpServers"][server.name] = {
                "transport": "http",
                "url": server.url,
                "headers": headers_dict,
            }
            
            logger.debug(
                f"Converted HTTP MCP server '{server.name}': url={server.url}"
            )
            
        elif isinstance(server, SseMcpServer):
            # Convert List[HttpHeader] to dict[str, str]
            headers_dict = {h.name: h.value for h in server.headers}
            
            config["mcpServers"][server.name] = {
                "transport": "sse",
                "url": server.url,
                "headers": headers_dict,
            }
            
            logger.debug(
                f"Converted SSE MCP server '{server.name}': url={server.url}"
            )
        
        else:
            logger.warning(f"Unknown MCP server type: {type(server)}, skipping")
    
    logger.info(f"Converted {len(config['mcpServers'])} MCP servers to FastMCP config")
    return config

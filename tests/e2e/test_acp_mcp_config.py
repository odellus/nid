"""
E2E test for ACP-centered MCP server configuration.

This test demonstrates the complete workflow of:
1. Creating ACP McpServerStdio configuration
2. Converting to FastMCP client via create_mcp_client_from_acp
3. Connecting to the real crow-mcp-server
4. Discovering and calling tools

This is the REAL test - no mocks, actual MCP server communication.
"""

import pytest
from acp.schema import McpServerStdio, EnvVariable

from crow.agent.mcp_client import create_mcp_client_from_acp, get_tools


class TestACPMCPConfigurationE2E:
    """End-to-end tests for ACP MCP server configuration."""
    
    @pytest.mark.asyncio
    async def test_builtin_server_via_in_memory(self):
        """Test that empty mcp_servers list uses builtin server."""
        # Empty list should use builtin crow-mcp-server (in-memory)
        client = await create_mcp_client_from_acp([])
        
        async with client:
            # Should be able to list tools from builtin server
            tools = await client.list_tools()
            
            # Builtin server should have our tools
            tool_names = [t.name for t in tools]
            assert len(tools) > 0, "Builtin server should have at least one tool"
            
            # Should have file_editor tool
            assert any("file_editor" in name for name in tool_names), \
                "Builtin server should have file_editor tools"
    
    @pytest.mark.asyncio
    async def test_stdio_server_configuration(self):
        """
        Test ACP stdio server configuration with builtin server.
        
        This demonstrates the user's use case of running crow-mcp-server
        via uv as a stdio MCP server.
        """
        # Configure crow-mcp-server as a stdio server (user's actual use case)
        servers = [
            McpServerStdio(
                name="crow-builtin",
                command="uv",
                args=[
                    "--project",
                    "/home/thomas/src/projects/mcp-testing/crow-mcp-server",
                    "run",
                    "/home/thomas/src/projects/mcp-testing/crow-mcp-server/crow_mcp_server/main.py",
                ],
                env=[EnvVariable(name="DEBUG", value="false")],
            )
        ]
        
        # Create FastMCP client from ACP configuration
        client = await create_mcp_client_from_acp(servers)
        
        async with client:
            # List tools from the server
            tools = await client.list_tools()
            
            # Should have tools from crow-mcp-server
            tool_names = [t.name for t in tools]
            assert len(tools) > 0, "crow-mcp-server should have tools"
            
            # Check for specific tools
            assert any("file_editor" in name for name in tool_names), \
                "Should have file_editor tools"
            
            print(f"\n✓ Discovered {len(tools)} tools from stdio server:")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description[:50]}...")
    
    @pytest.mark.asyncio
    async def test_tool_calling_via_acp_config(self):
        """Test calling tools via ACP-configured MCP server."""
        # Use builtin server (in-memory for speed)
        client = await create_mcp_client_from_acp([])
        
        async with client:
            # Call file_editor with view command
            result = await client.call_tool(
                "file_editor",
                {
                    "command": "view",
                    "path": "/home/thomas/src/projects/mcp-testing/README.md"
                }
            )
            
            # Should get a result
            assert result is not None
            assert hasattr(result, "content")
            
            # Result should contain file contents
            content_text = result.content[0].text
            assert "crow" in content_text.lower() or "mcp" in content_text.lower(), \
                "Should contain README content"
            
            print(f"\n✓ Successfully called file_editor tool")
            print(f"  Result length: {len(content_text)} chars")
    
    @pytest.mark.asyncio
    async def test_get_tools_converts_to_openai_format(self):
        """Test that get_tools properly converts MCP tools to OpenAI format."""
        # Use builtin server
        client = await create_mcp_client_from_acp([])
        
        async with client:
            # Get tools in OpenAI format
            tools = await get_tools(client)
            
            # Should have tools
            assert len(tools) > 0
            
            # Each tool should be in OpenAI format
            for tool in tools:
                assert tool["type"] == "function"
                assert "function" in tool
                assert "name" in tool["function"]
                assert "description" in tool["function"]
                assert "parameters" in tool["function"]
                
                # Parameters should be a JSON schema
                params = tool["function"]["parameters"]
                assert isinstance(params, dict)
                assert "type" in params
                assert params["type"] == "object"
            
            print(f"\n✓ Converted {len(tools)} tools to OpenAI format")
            print(f"  Sample tool: {tools[0]['function']['name']}")

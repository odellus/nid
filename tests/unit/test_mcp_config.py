"""
Unit tests for MCP configuration conversion.

Tests the dialectical constraint: ACP protocol format MUST convert to FastMCP format.
Following TDD - write tests FIRST, then make them pass.
"""

import pytest
from acp.schema import (
    EnvVariable,
    HttpHeader,
    HttpMcpServer,
    McpServerStdio,
    SseMcpServer,
)

from crow.agent.mcp_config import acp_to_fastmcp_config


class TestStdioServerConversion:
    """Test conversion of McpServerStdio to FastMCP config."""
    
    def test_basic_stdio_server(self):
        """Test basic stdio server conversion."""
        servers = [
            McpServerStdio(
                name="test-server",
                command="python",
                args=["server.py"],
                env=[],
            )
        ]
        
        config = acp_to_fastmcp_config(servers)
        
        assert "mcpServers" in config
        assert "test-server" in config["mcpServers"]
        
        server_config = config["mcpServers"]["test-server"]
        assert server_config["transport"] == "stdio"
        assert server_config["command"] == "python"
        assert server_config["args"] == ["server.py"]
        assert server_config["env"] == {}
    
    def test_stdio_server_with_env_vars(self):
        """Test stdio server with environment variables."""
        servers = [
            McpServerStdio(
                name="test-server",
                command="python",
                args=["server.py"],
                env=[
                    EnvVariable(name="DEBUG", value="true"),
                    EnvVariable(name="API_KEY", value="secret123"),
                ],
            )
        ]
        
        config = acp_to_fastmcp_config(servers)
        env = config["mcpServers"]["test-server"]["env"]
        
        # Test conversion from List[EnvVariable] to dict[str, str]
        assert env["DEBUG"] == "true"
        assert env["API_KEY"] == "secret123"
        assert len(env) == 2
    
    def test_stdio_server_with_uv(self):
        """Test stdio server using uv (real use case from user)."""
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
                env=[],
            )
        ]
        
        config = acp_to_fastmcp_config(servers)
        server_config = config["mcpServers"]["crow-builtin"]
        
        assert server_config["command"] == "uv"
        assert "--project" in server_config["args"]
        assert "/home/thomas/src/projects/mcp-testing/crow-mcp-server" in server_config["args"]
    
    def test_multiple_stdio_servers(self):
        """Test conversion of multiple stdio servers."""
        servers = [
            McpServerStdio(
                name="server1",
                command="python",
                args=["s1.py"],
                env=[],
            ),
            McpServerStdio(
                name="server2",
                command="node",
                args=["s2.js"],
                env=[EnvVariable(name="NODE_ENV", value="production")],
            ),
        ]
        
        config = acp_to_fastmcp_config(servers)
        
        assert len(config["mcpServers"]) == 2
        assert "server1" in config["mcpServers"]
        assert "server2" in config["mcpServers"]
        assert config["mcpServers"]["server2"]["env"]["NODE_ENV"] == "production"


class TestHttpServerConversion:
    """Test conversion of HttpMcpServer to FastMCP config."""
    
    def test_basic_http_server(self):
        """Test basic HTTP server conversion."""
        servers = [
            HttpMcpServer(
                type="http",
                name="api-server",
                url="https://api.example.com/mcp",
                headers=[],
            )
        ]
        
        config = acp_to_fastmcp_config(servers)
        
        assert "api-server" in config["mcpServers"]
        server_config = config["mcpServers"]["api-server"]
        
        assert server_config["transport"] == "http"
        assert server_config["url"] == "https://api.example.com/mcp"
        assert server_config["headers"] == {}
    
    def test_http_server_with_headers(self):
        """Test HTTP server with authentication headers."""
        servers = [
            HttpMcpServer(
                type="http",
                name="api-server",
                url="https://api.example.com/mcp",
                headers=[
                    HttpHeader(name="Authorization", value="Bearer token123"),
                    HttpHeader(name="X-Custom-Header", value="custom-value"),
                ],
            )
        ]
        
        config = acp_to_fastmcp_config(servers)
        headers = config["mcpServers"]["api-server"]["headers"]
        
        # Test conversion from List[HttpHeader] to dict[str, str]
        assert headers["Authorization"] == "Bearer token123"
        assert headers["X-Custom-Header"] == "custom-value"
        assert len(headers) == 2


class TestSseServerConversion:
    """Test conversion of SseMcpServer to FastMCP config."""
    
    def test_basic_sse_server(self):
        """Test basic SSE server conversion."""
        servers = [
            SseMcpServer(
                type="sse",
                name="sse-server",
                url="https://sse.example.com/events",
                headers=[],
            )
        ]
        
        config = acp_to_fastmcp_config(servers)
        
        assert "sse-server" in config["mcpServers"]
        server_config = config["mcpServers"]["sse-server"]
        
        assert server_config["transport"] == "sse"
        assert server_config["url"] == "https://sse.example.com/events"
        assert server_config["headers"] == {}
    
    def test_sse_server_with_headers(self):
        """Test SSE server with headers."""
        servers = [
            SseMcpServer(
                type="sse",
                name="sse-server",
                url="https://sse.example.com/events",
                headers=[
                    HttpHeader(name="X-API-Key", value="key123"),
                ],
            )
        ]
        
        config = acp_to_fastmcp_config(servers)
        headers = config["mcpServers"]["sse-server"]["headers"]
        
        assert headers["X-API-Key"] == "key123"


class TestMixedServerTypes:
    """Test conversion of mixed server types."""
    
    def test_stdio_and_http_servers(self):
        """Test conversion of both stdio and HTTP servers."""
        servers = [
            McpServerStdio(
                name="local-server",
                command="python",
                args=["local.py"],
                env=[],
            ),
            HttpMcpServer(
                type="http",
                name="remote-server",
                url="https://remote.example.com/mcp",
                headers=[HttpHeader(name="Auth", value="token")],
            ),
        ]
        
        config = acp_to_fastmcp_config(servers)
        
        assert len(config["mcpServers"]) == 2
        
        # Check stdio server
        local = config["mcpServers"]["local-server"]
        assert local["transport"] == "stdio"
        assert local["command"] == "python"
        
        # Check http server
        remote = config["mcpServers"]["remote-server"]
        assert remote["transport"] == "http"
        assert remote["url"] == "https://remote.example.com/mcp"
        assert remote["headers"]["Auth"] == "token"
    
    def test_all_three_server_types(self):
        """Test conversion of stdio, http, and sse servers together."""
        servers = [
            McpServerStdio(
                name="stdio-srv",
                command="python",
                args=["s.py"],
                env=[EnvVariable(name="DEBUG", value="1")],
            ),
            HttpMcpServer(
                type="http",
                name="http-srv",
                url="https://http.example.com/mcp",
                headers=[],
            ),
            SseMcpServer(
                type="sse",
                name="sse-srv",
                url="https://sse.example.com/events",
                headers=[],
            ),
        ]
        
        config = acp_to_fastmcp_config(servers)
        
        assert len(config["mcpServers"]) == 3
        assert config["mcpServers"]["stdio-srv"]["transport"] == "stdio"
        assert config["mcpServers"]["http-srv"]["transport"] == "http"
        assert config["mcpServers"]["sse-srv"]["transport"] == "sse"


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_server_list(self):
        """Test conversion of empty server list."""
        config = acp_to_fastmcp_config([])
        
        assert "mcpServers" in config
        assert len(config["mcpServers"]) == 0
    
    def test_server_name_preserved(self):
        """Test that server names are preserved exactly."""
        servers = [
            McpServerStdio(
                name="my-custom-server-name",
                command="python",
                args=["s.py"],
                env=[],
            )
        ]
        
        config = acp_to_fastmcp_config(servers)
        
        assert "my-custom-server-name" in config["mcpServers"]
    
    def test_empty_env_still_included(self):
        """Test that empty env dict is still included in config."""
        servers = [
            McpServerStdio(
                name="test",
                command="python",
                args=["s.py"],
                env=[],
            )
        ]
        
        config = acp_to_fastmcp_config(servers)
        
        # FastMCP expects env key even if empty
        assert "env" in config["mcpServers"]["test"]
        assert config["mcpServers"]["test"]["env"] == {}
    
    def test_empty_headers_still_included(self):
        """Test that empty headers dict is still included in config."""
        servers = [
            HttpMcpServer(
                type="http",
                name="test",
                url="https://test.com",
                headers=[],
            )
        ]
        
        config = acp_to_fastmcp_config(servers)
        
        # FastMCP expects headers key even if empty
        assert "headers" in config["mcpServers"]["test"]
        assert config["mcpServers"]["test"]["headers"] == {}


class TestConversionConstraints:
    """Test semantic constraints of the conversion."""
    
    def test_env_values_are_strings(self):
        """Test that all env values are converted to strings."""
        servers = [
            McpServerStdio(
                name="test",
                command="python",
                args=["s.py"],
                env=[
                    EnvVariable(name="PORT", value="8080"),  # Already string
                    EnvVariable(name="DEBUG", value="true"),  # Boolean as string
                ],
            )
        ]
        
        config = acp_to_fastmcp_config(servers)
        env = config["mcpServers"]["test"]["env"]
        
        # All values must be strings for FastMCP
        assert all(isinstance(v, str) for v in env.values())
    
    def test_header_values_are_strings(self):
        """Test that all header values are converted to strings."""
        servers = [
            HttpMcpServer(
                type="http",
                name="test",
                url="https://test.com",
                headers=[
                    HttpHeader(name="X-Count", value="42"),
                ],
            )
        ]
        
        config = acp_to_fastmcp_config(servers)
        headers = config["mcpServers"]["test"]["headers"]
        
        # All values must be strings for FastMCP
        assert all(isinstance(v, str) for v in headers.values())
    
    def test_no_acp_objects_in_output(self):
        """Test that output contains only primitive types, no ACP objects."""
        servers = [
            McpServerStdio(
                name="test",
                command="python",
                args=["s.py"],
                env=[EnvVariable(name="K", value="V")],
            )
        ]
        
        config = acp_to_fastmcp_config(servers)
        
        # Recursively check no ACP types in the config
        def check_primitive(obj):
            if isinstance(obj, dict):
                all(check_primitive(v) for v in obj.values())
            elif isinstance(obj, list):
                all(check_primitive(v) for v in obj)
            else:
                # Should be str, int, float, bool, or None
                assert isinstance(obj, (str, int, float, bool, type(None)))
        
        check_primitive(config)

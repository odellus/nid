"""
Unit tests for MCP client lifecycle management.

These tests verify:
- AsyncExitStack pattern properly manages MCP clients
- Cleanup happens even with exceptions
- Resources are tracked and cleaned up
- No resource leaks occur
"""

import asyncio
from contextlib import AsyncExitStack

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAsyncExitStackLifecycle:
    """Test AsyncExitStack pattern for managing MCP client lifecycle."""
    
    @pytest.mark.asyncio
    async def test_exit_stack_enters_and_exits_context(self, mock_mcp_client):
        """Test that AsyncExitStack properly enters and exits context managers."""
        stack = AsyncExitStack()
        
        # Enter the context
        client = await stack.enter_async_context(mock_mcp_client)
        
        assert client.entered is True
        assert client.exited is False
        
        # Exit all contexts
        await stack.aclose()
        
        assert client.exited is True
    
    @pytest.mark.asyncio
    async def test_exit_stack_cleans_up_on_exception(self, mock_mcp_client):
        """Test that AsyncExitStack cleans up even when exceptions occur."""
        stack = AsyncExitStack()
        
        try:
            client = await stack.enter_async_context(mock_mcp_client)
            assert client.entered is True
            
            # Simulate an exception
            raise ValueError("Test exception")
        except ValueError:
            pass
        finally:
            # Cleanup should still happen
            await stack.aclose()
        
        assert mock_mcp_client.exited is True
    
    @pytest.mark.asyncio
    async def test_exit_stack_manages_multiple_clients(self):
        """Test that AsyncExitStack can manage multiple MCP clients."""
        
        class MockClient:
            def __init__(self, name):
                self.name = name
                self.entered = False
                self.exited = False
            
            async def __aenter__(self):
                self.entered = True
                return self
            
            async def __aexit__(self, *args):
                self.exited = True
        
        stack = AsyncExitStack()
        client1 = MockClient("client1")
        client2 = MockClient("client2")
        
        # Enter multiple contexts
        c1 = await stack.enter_async_context(client1)
        c2 = await stack.enter_async_context(client2)
        
        assert c1.entered and c2.entered
        assert not c1.exited and not c2.exited
        
        # Exit all at once
        await stack.aclose()
        
        assert c1.exited and c2.exited


class TestResourceTracking:
    """Test that resources are properly tracked and accessible."""
    
    @pytest.mark.asyncio
    async def test_can_access_mcp_client_after_registration(self, mock_mcp_client):
        """Test that registered MCP clients remain accessible."""
        stack = AsyncExitStack()
        client = await stack.enter_async_context(mock_mcp_client)
        
        # Should be able to use the client
        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "test_tool"
        
        await stack.aclose()
    
    @pytest.mark.asyncio
    async def test_resources_stay_alive_until_explicit_cleanup(self, mock_mcp_client):
        """Test that resources stay alive until we explicitly clean them up."""
        stack = AsyncExitStack()
        client = await stack.enter_async_context(mock_mcp_client)
        
        # Do some work
        await asyncio.sleep(0.01)
        
        # Client should still be alive
        assert client.entered is True
        assert client.exited is False
        
        # Only after cleanup should it exit
        await stack.aclose()
        assert client.exited is True


class TestExceptionSafety:
    """Test exception safety of async context manager lifecycle."""
    
    @pytest.mark.asyncio
    async def test_exception_in_setup_still_cleans_up_previous(self):
        """Test that if setup fails, previous resources are still cleaned up."""
        
        class FailingClient:
            def __init__(self, should_fail=False):
                self.should_fail = should_fail
                self.entered = False
                self.exited = False
            
            async def __aenter__(self):
                if self.should_fail:
                    raise RuntimeError("Setup failed")
                self.entered = True
                return self
            
            async def __aexit__(self, *args):
                self.exited = True
        
        stack = AsyncExitStack()
        client1 = FailingClient(should_fail=False)
        client2 = FailingClient(should_fail=True)
        
        # First client should succeed
        c1 = await stack.enter_async_context(client1)
        assert c1.entered is True
        
        # Second client should fail
        with pytest.raises(RuntimeError, match="Setup failed"):
            await stack.enter_async_context(client2)
        
        # Cleanup should still happen for client1
        await stack.aclose()
        assert client1.exited is True
    
    @pytest.mark.asyncio
    async def test_exception_during_use_cleans_up(self, mock_mcp_client):
        """Test that exceptions during resource use still trigger cleanup."""
        stack = AsyncExitStack()
        
        try:
            client = await stack.enter_async_context(mock_mcp_client)
            raise ValueError("Error during use")
        except ValueError:
            pass
        finally:
            await stack.aclose()
        
        assert mock_mcp_client.exited is True


class TestAsyncExitStackIntegration:
    """Test AsyncExitStack integration with agent-like patterns."""
    
    @pytest.mark.asyncio
    async def test_agent_can_manage_multiple_sessions(self, mock_mcp_client):
        """Test that an agent can manage multiple session resources."""
        
        class MockAgent:
            def __init__(self):
                self.exit_stack = AsyncExitStack()
                self.sessions = {}
            
            async def create_session(self, session_id, mcp_client):
                """Create a session with MCP client."""
                client = await self.exit_stack.enter_async_context(mcp_client)
                self.sessions[session_id] = client
                return session_id
            
            async def cleanup(self):
                """Cleanup all sessions."""
                await self.exit_stack.aclose()
        
        agent = MockAgent()
        
        # Create multiple sessions
        session1 = await agent.create_session("s1", mock_mcp_client)
        session2 = await agent.create_session("s2", mock_mcp_client)
        
        assert "s1" in agent.sessions
        assert "s2" in agent.sessions
        
        # Cleanup all
        await agent.cleanup()
        
        # All should be cleaned up
        assert mock_mcp_client.exited

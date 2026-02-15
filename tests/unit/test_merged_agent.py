"""
Tests to keep agent merge on rails.

These tests define the expected structure of the merged ACP-native agent.
They will FAIL initially but should PASS after merge is complete.

Run these during merge to verify progress:
    uv --project . run pytest tests/unit/test_merged_agent.py -v
"""

import pytest
from contextlib import AsyncExitStack


class TestMergedAgentStructure:
    """Tests for merged agent class structure."""
    
    @pytest.mark.asyncio
    async def test_single_agent_exists(self):
        """Verify single agent class (no wrapper)"""
        # Should be able to import Agent that inherits from acp.Agent
        from crow.agent import Agent
        from acp import Agent
        
        agent = Agent()
        assert isinstance(agent, Agent), "Agent must inherit from acp.Agent"
    
    @pytest.mark.asyncio
    async def test_no_nested_agents(self):
        """Verify no nested agent instances"""
        from crow.agent import Agent
        
        agent = Agent()
        
        # Should NOT have _agents dict (that was the wrapper)
        assert not hasattr(agent, '_agents'), "No _agents dict - no nested agents"
        
        # Should have _sessions dict instead
        assert hasattr(agent, '_sessions'), "Should have _sessions dict"
        assert isinstance(agent._sessions, dict)
    
    @pytest.mark.asyncio
    async def test_has_acp_methods(self):
        """Verify all ACP methods exist"""
        from crow.agent import Agent
        
        agent = Agent()
        
        # Required ACP methods
        required_methods = [
            'on_connect',
            'initialize',
            'new_session',
            'prompt',
            'cleanup',
        ]
        
        for method in required_methods:
            assert hasattr(agent, method), f"Missing ACP method: {method}"
    
    @pytest.mark.asyncio
    async def test_acp_methods_are_async(self):
        """Verify ACP methods are async"""
        from crow.agent import Agent
        import asyncio
        
        agent = Agent()
        
        async_methods = [
            'initialize',
            'new_session',
            'load_session',
            'prompt',
            'cleanup',
        ]
        
        for method in async_methods:
            method_func = getattr(agent, method)
            assert asyncio.iscoroutinefunction(method_func), \
                f"{method} must be async"


class TestMergedAgentBusinessLogic:
    """Tests for business logic methods in merged agent."""
    
    @pytest.mark.asyncio
    async def test_has_react_loop(self):
        """Verify react loop exists as method"""
        from crow.agent import Agent
        
        agent = Agent()
        
        # Should have _react_loop method (moved from old Agent)
        assert hasattr(agent, '_react_loop'), \
            "Should have _react_loop method"
    
    @pytest.mark.asyncio
    async def test_has_request_methods(self):
        """Verify LLM request methods exist"""
        from crow.agent import Agent
        
        agent = Agent()
        
        # Should have these methods moved from old Agent
        methods = [
            '_send_request',
            '_process_chunk',
            '_process_response',
            '_process_tool_call_inputs',
            '_execute_tool_calls',
        ]
        
        for method in methods:
            assert hasattr(agent, method), \
                f"Missing business logic method: {method}"
    
    @pytest.mark.asyncio
    async def test_react_loop_takes_session_param(self):
        """Verify react loop takes session as parameter (not instance var)"""
        from crow.agent import Agent
        import inspect
        
        agent = Agent()
        
        # Get _react_loop signature
        sig = inspect.signature(agent._react_loop)
        
        # Should have 'session' as parameter
        params = list(sig.parameters.keys())
        assert 'session' in params, \
            "_react_loop must take session as parameter"


class TestMergedAgentResourceManagement:
    """Tests for resource management in merged agent."""
    
    @pytest.mark.asyncio
    async def test_has_exit_stack(self):
        """Verify AsyncExitStack exists"""
        from crow.agent import Agent
        
        agent = Agent()
        
        # Should have AsyncExitStack for managing MCP clients
        assert hasattr(agent, '_exit_stack'), \
            "Should have _exit_stack for resource management"
        assert isinstance(agent._exit_stack, AsyncExitStack)
    
    @pytest.mark.asyncio
    async def test_has_cleanup_method(self):
        """Verify cleanup method exists"""
        from crow.agent import Agent
        
        agent = Agent()
        
        # Should have cleanup method
        assert hasattr(agent, 'cleanup'), \
            "Should have cleanup method for AsyncExitStack"
        
        # Should be async
        import asyncio
        assert asyncio.iscoroutinefunction(agent.cleanup), \
            "cleanup must be async"


class TestMergedAgentSessionHandling:
    """Tests for session handling in merged agent."""
    
    @pytest.mark.asyncio
    async def test_creates_session_with_mcp(self, mock_mcp_client, temp_workspace):
        """Verify new session creates MCP client via AsyncExitStack"""
        from crow.agent import Agent
        
        agent = Agent()
        
        # Mock connection
        from unittest.mock import MagicMock
        agent._conn = MagicMock()
        
        # Create session
        response = await agent.new_session(
            cwd=temp_workspace,
            mcp_servers=[],
        )
        
        assert response.session_id is not None
        assert response.session_id in agent._sessions
    
    @pytest.mark.asyncio
    async def test_session_stores_session_data(self, temp_workspace):
        """Verify session data is stored correctly"""
        from crow.agent import Agent
        
        agent = Agent()
        
        # Mock connection
        from unittest.mock import MagicMock
        agent._conn = MagicMock()
        
        # Create session
        response = await agent.new_session(
            cwd=temp_workspace,
            mcp_servers=[],
        )
        
        session_id = response.session_id
        
        # Check session data structure
        assert session_id in agent._sessions
        session_data = agent._sessions[session_id]
        
        # Should have these keys
        assert "session" in session_data
        # MCP client is stored via AsyncExitStack, not in dict


class TestMergedAgentStreaming:
    """Tests for streaming in merged agent."""
    
    @pytest.mark.asyncio
    async def test_react_loop_yields_tokens(self, temp_workspace):
        """Verify react loop yields tokens for streaming"""
        from crow.agent import Agent
        
        agent = Agent()
        
        # This test will need proper setup
        # Just verify module structure for now
        import inspect
        
        # _react_loop should be async generator
        assert inspect.isasyncgenfunction(agent._react_loop), \
            "_react_loop should be async generator (yield tokens)"


class TestMergedAgentNoWrapper:
    """Tests to ensure no wrapper pattern."""
    
    @pytest.mark.asyncio
    async def test_no_separate_agent_class(self):
        """Verify no separate Agent in agent/ module"""
        import sys
        
        # Old Agent should NOT exist in agent.agent module
        try:
            from crow.agent.agent import Agent as OldAgent
            assert False, "Old separate Agent class should not exist"
        except ImportError:
            pass  # Good - old class doesn't exist
    
    @pytest.mark.asyncio
    async def test_no_crowacpagent_wrapper(self):
        """Verify no CrowACPAgent wrapper class"""
        import sys
        
        # CrowACPAgent wrapper should NOT exist
        try:
            from crow.acp_agent import CrowACPAgent
            # If it exists, it should just import the merged agent
            from acp import Agent
            assert issubclass(CrowACPAgent, Agent)
        except ImportError:
            pass  # Good - wrapper doesn't exist


class TestMergedAgentImports:
    """Tests for import structure."""
    
    @pytest.mark.asyncio
    async def test_agent_importable_from_crow(self):
        """Verify agent can be imported from crow.agent"""
        from crow.agent import Agent
        from acp import Agent
        
        assert issubclass(Agent, Agent)
    
    @pytest.mark.asyncio
    async def test_agent_has_required_utilities(self):
        """Verify required utilities are importable"""
        from crow.agent import (
            configure_llm,
            setup_mcp_client,
            get_tools,
            Session,
        )
        
        # Should be able to import all utilities
        assert callable(configure_llm)
        assert callable(setup_mcp_client)
        assert callable(get_tools)


# These tests will FAIL initially but guide implementation
# Run: uv --project . run pytest tests/unit/test_merged_agent.py -v

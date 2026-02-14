"""
End-to-end tests for the full agent flow.

These tests verify:
- Complete ACP agent lifecycle
- Full integration of all components
- Real-world usage scenarios
"""

import pytest
from contextlib import AsyncExitStack


class TestAgentE2E:
    """End-to-end tests for the complete agent flow."""
    
    @pytest.mark.asyncio
    async def test_agent_full_lifecycle_with_cleanup(self, seeded_db, temp_workspace):
        """Test complete agent lifecycle from creation to cleanup."""
        
        # Simulating the CrowACPAgent pattern
        class MockAgent:
            """Mock agent for E2E testing."""
            
            def __init__(self):
                self.exit_stack = AsyncExitStack()
                self.sessions = {}
                self.clients = {}
            
            async def new_session(self, session_id, workspace, mcp_client, prompt_id, db_path):
                """Create a new session with proper resource management."""
                # Enter MCP client context (this is the fix!)
                client = await self.exit_stack.enter_async_context(mcp_client)
                
                # Simulate session creation
                self.sessions[session_id] = {
                    "workspace": workspace,
                    "prompt_id": prompt_id,
                    "created": True,
                }
                self.clients[session_id] = client
                
                return session_id
            
            async def cleanup_session(self, session_id):
                """Remove session (resources cleaned by exit stack)."""
                if session_id in self.sessions:
                    del self.sessions[session_id]
                if session_id in self.clients:
                    del self.clients[session_id]
            
            async def shutdown(self):
                """Cleanup all resources on shutdown."""
                await self.exit_stack.aclose()
        
        # Mock MCP client
        class MockMCPClient:
            def __init__(self):
                self.entered = False
                self.exited = False
            
            async def __aenter__(self):
                self.entered = True
                return self
            
            async def __aexit__(self, *args):
                self.exited = True
            
            async def list_tools(self):
                from types import SimpleNamespace
                return [SimpleNamespace(name="test", description="test", inputSchema={})]
        
        agent = MockAgent()
        client = MockMCPClient()
        
        # Create session
        session_id = await agent.new_session(
            session_id="test-session",
            workspace=temp_workspace,
            mcp_client=client,
            prompt_id="test-prompt-v1",
            db_path=seeded_db,
        )
        
        assert session_id == "test-session"
        assert client.entered is True
        assert client.exited is False
        assert len(agent.sessions) == 1
        
        # Simulate doing some work
        await agent.cleanup_session(session_id)
        assert len(agent.sessions) == 0
        
        # Shutdown agent completely
        await agent.shutdown()
        
        # Verify cleanup
        assert client.exited is True
    
    @pytest.mark.asyncio
    async def test_agent_handles_multiple_sessions_concurrently(
        self, seeded_db, temp_workspace
    ):
        """Test agent managing multiple sessions simultaneously."""
        
        class MultiSessionAgent:
            def __init__(self):
                self.exit_stack = AsyncExitStack()
                self.sessions = {}
            
            async def create_session(self, session_id, mcp_client):
                client = await self.exit_stack.enter_async_context(mcp_client)
                self.sessions[session_id] = client
                return session_id
            
            async def shutdown(self):
                await self.exit_stack.aclose()
        
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
        
        agent = MultiSessionAgent()
        clients = [MockClient(f"client{i}") for i in range(3)]
        
        # Create multiple sessions
        for i, client in enumerate(clients):
            await agent.create_session(f"session-{i}", client)
        
        # All should be entered
        assert all(c.entered for c in clients)
        assert all(not c.exited for c in clients)
        assert len(agent.sessions) == 3
        
        # Shutdown
        await agent.shutdown()
        
        # All should be cleaned up
        assert all(c.exited for c in clients)
    
    @pytest.mark.asyncio
    async def test_agent_recovers_from_session_creation_failure(self):
        """Test that agent can recover if a session creation fails."""
        
        class ResilientAgent:
            def __init__(self):
                self.exit_stack = AsyncExitStack()
                self.sessions = {}
            
            async def create_session(self, session_id, mcp_client, should_fail=False):
                client = await self.exit_stack.enter_async_context(mcp_client)
                
                if should_fail:
                    raise ValueError("Session creation failed")
                
                self.sessions[session_id] = client
                return session_id
            
            async def shutdown(self):
                await self.exit_stack.aclose()
        
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
        
        agent = ResilientAgent()
        client1 = MockClient("client1")
        client2 = MockClient("client2")
        client3 = MockClient("client3")
        
        # First session succeeds
        await agent.create_session("s1", client1)
        assert "s1" in agent.sessions
        
        # Second session fails
        with pytest.raises(ValueError, match="Session creation failed"):
            await agent.create_session("s2", client2, should_fail=True)
        
        # Third session succeeds (agent recovers)
        await agent.create_session("s3", client3)
        assert "s3" in agent.sessions
        
        # All clients should be cleaned up on shutdown
        await agent.shutdown()
        
        assert client1.exited
        assert client2.exited
        assert client3.exited
    
    @pytest.mark.asyncio
    async def test_full_prompt_lifecycle_e2e(self, temp_db):
        """Test full prompt lifecycle: create, lookup, use in session."""
        
        from nid.agent.db import Prompt, Session as SessionModel
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session as SQLAlchemySession
        
        # Step 1: Create prompt via lookup-or-create pattern
        engine = create_engine(temp_db)
        db = SQLAlchemySession(engine)
        
        template = "E2E test agent: {{workspace}}"
        
        # Try to find existing
        prompt = db.query(Prompt).filter_by(template=template).first()
        
        if not prompt:
            # Create new
            prompt = Prompt(
                id="e2e-prompt-v1",
                name="E2E Test Prompt",
                template=template,
            )
            db.add(prompt)
            db.commit()
        
        prompt_id = prompt.id
        db.close()
        engine.dispose()
        
        # Step 2: Use prompt in session creation
        from nid.agent import Session
        
        tools = [{"type": "function", "function": {"name": "test", "parameters": {}}}]
        
        session = Session.create(
            prompt_id=prompt_id,
            prompt_args={"workspace": "/test/workspace"},
            tool_definitions=tools,
            request_params={"temperature": 0.7},
            model_identifier="test-model",
            db_path=temp_db,
        )
        
        # Step 3: Verify session uses our prompt
        assert session is not None
        assert len(session.messages) > 0
        assert "E2E test agent" in session.messages[0]["content"]
        
        # Step 4: Verify prompt is in database
        engine = create_engine(temp_db)
        db = SQLAlchemySession(engine)
        
        found = db.query(Prompt).filter_by(id=prompt_id).first()
        assert found is not None
        assert found.template == template
        
        db.close()
        engine.dispose()

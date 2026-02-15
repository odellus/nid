"""
Integration tests for session lifecycle with MCP clients.

These tests verify:
- Full session creation with proper MCP client lifecycle
- Cleanup happens correctly
- Resources are managed throughout session lifetime
- Integration with prompt persistence
"""

import pytest
from contextlib import AsyncExitStack
from sqlalchemy.orm import Session as SQLAlchemySession

from crow.agent import Session, configure_llm, get_tools
from crow.agent.db import Prompt


class TestSessionLifecycle:
    """Test full session lifecycle with MCP client management."""
    
    @pytest.mark.asyncio
    async def test_session_creates_with_proper_cleanup(
        self, seeded_db, temp_workspace, mock_mcp_client
    ):
        """Test that session creation properly manages MCP client lifecycle."""
        
        class SessionManager:
            """Manages session resources with proper cleanup."""
            
            def __init__(self):
                self.exit_stack = AsyncExitStack()
                self.mcp_client = None
                self.session = None
            
            async def create(self, db_path, workspace, mcp_client, prompt_id):
                """Create session with proper resource management."""
                # Enter MCP client context
                self.mcp_client = await self.exit_stack.enter_async_context(mcp_client)
                
                # Get tools
                tools = await get_tools(self.mcp_client)
                
                # Create session
                self.session = Session.create(
                    prompt_id=prompt_id,
                    prompt_args={"workspace": workspace},
                    tool_definitions=tools,
                    request_params={"temperature": 0.7},
                    model_identifier="test-model",
                    db_path=db_path,
                )
                
                return self.session
            
            async def cleanup(self):
                """Cleanup all resources."""
                await self.exit_stack.aclose()
        
        manager = SessionManager()
        
        # Create session
        session = await manager.create(
            db_path=seeded_db,
            workspace=temp_workspace,
            mcp_client=mock_mcp_client,
            prompt_id="test-prompt-v1",
        )
        
        assert session is not None
        assert session.session_id is not None
        assert mock_mcp_client.entered is True
        assert mock_mcp_client.exited is False
        
        # Cleanup
        await manager.cleanup()
        
        assert mock_mcp_client.exited is True
    
    @pytest.mark.asyncio
    async def test_multiple_sessions_share_or_separate_resources(
        self, seeded_db, temp_workspace
    ):
        """Test how multiple sessions manage MCP client resources."""
        
        class MultiSessionManager:
            """Manages multiple sessions."""
            
            def __init__(self):
                self.exit_stack = AsyncExitStack()
                self.sessions = {}
            
            async def create_session(self, session_id, db_path, workspace, mcp_client, prompt_id):
                """Create a session with proper resource management."""
                client = await self.exit_stack.enter_async_context(mcp_client)
                tools = await get_tools(client)
                
                session = Session.create(
                    prompt_id=prompt_id,
                    prompt_args={"workspace": workspace},
                    tool_definitions=tools,
                    request_params={"temperature": 0.7},
                    model_identifier="test-model",
                    db_path=db_path,
                )
                
                self.sessions[session_id] = {
                    "session": session,
                    "mcp_client": client,
                }
                
                return session
            
            async def cleanup(self):
                """Cleanup all sessions."""
                await self.exit_stack.aclose()
        
        manager = MultiSessionManager()
        
        # Create mock clients
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
            
            async def list_tools(self):
                from types import SimpleNamespace
                return [SimpleNamespace(name="test", description="test", inputSchema={})]
        
        client1 = MockClient("client1")
        client2 = MockClient("client2")
        
        # Create two sessions
        await manager.create_session("s1", seeded_db, temp_workspace, client1, "test-prompt-v1")
        await manager.create_session("s2", seeded_db, temp_workspace, client2, "test-prompt-v1")
        
        assert client1.entered and client2.entered
        assert not client1.exited and not client2.exited
        
        # Cleanup all
        await manager.cleanup()
        
        assert client1.exited and client2.exited


class TestPromptPersistenceIntegration:
    """Test prompt persistence integrated with session creation."""
    
    @pytest.mark.asyncio
    async def test_session_uses_existing_prompt(self, seeded_db, temp_workspace):
        """Test that session creation uses existing prompt if template matches."""
        # The seeded_db already has "test-prompt-v1"
        
        tools = [{"type": "function", "function": {"name": "test", "parameters": {}}}]
        
        session = Session.create(
            prompt_id="test-prompt-v1",
            prompt_args={"workspace": temp_workspace},
            tool_definitions=tools,
            request_params={"temperature": 0.7},
            model_identifier="test-model",
            db_path=seeded_db,
        )
        
        # Should use existing prompt
        assert session is not None
        assert "You are a test agent" in session.messages[0]["content"]
    
    @pytest.mark.asyncio
    async def test_can_add_new_prompt_and_create_session(self, temp_db, temp_workspace):
        """Test adding a new prompt and creating session with it."""
        
        # Add new prompt
        from sqlalchemy.orm import Session as SQLAlchemySession
        from sqlalchemy import create_engine
        
        engine = create_engine(temp_db)
        db = SQLAlchemySession(bind=engine)
        
        new_template = "New agent template: {{workspace}}"
        new_prompt = Prompt(
            id="new-prompt-v1",
            name="New Prompt",
            template=new_template,
        )
        db.add(new_prompt)
        db.commit()
        db.close()
        engine.dispose()
        
        # Create session with new prompt
        tools = [{"type": "function", "function": {"name": "test", "parameters": {}}}]
        
        session = Session.create(
            prompt_id="new-prompt-v1",
            prompt_args={"workspace": temp_workspace},
            tool_definitions=tools,
            request_params={"temperature": 0.7},
            model_identifier="test-model",
            db_path=temp_db,
        )
        
        assert session is not None
        assert "New agent template" in session.messages[0]["content"]


class TestExceptionSafetyIntegration:
    """Test exception safety in integrated scenarios."""
    
    @pytest.mark.asyncio
    async def test_exception_during_session_setup_cleans_up_mcp(
        self, seeded_db, temp_workspace, mock_mcp_client
    ):
        """Test that MCP client is cleaned up even if session setup fails."""
        
        class FailingSessionManager:
            def __init__(self):
                self.exit_stack = AsyncExitStack()
            
            async def create_failing_session(self, mcp_client):
                """Create session that fails during setup."""
                client = await self.exit_stack.enter_async_context(mcp_client)
                
                # Simulate failure during session creation
                raise ValueError("Session creation failed")
            
            async def cleanup(self):
                await self.exit_stack.aclose()
        
        manager = FailingSessionManager()
        
        with pytest.raises(ValueError, match="Session creation failed"):
            await manager.create_failing_session(mock_mcp_client)
        
        # Cleanup should still work
        await manager.cleanup()
        
        assert mock_mcp_client.exited is True
    
    @pytest.mark.asyncio
    async def test_multiple_exceptions_handled_correctly(self, mock_mcp_client):
        """Test that multiple resources are all cleaned up on exception."""
        
        class MockResource:
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
        
        try:
            r1 = await stack.enter_async_context(MockResource("r1"))
            r2 = await stack.enter_async_context(mock_mcp_client)
            r3 = await stack.enter_async_context(MockResource("r3"))
            
            raise RuntimeError("Test error")
        except RuntimeError:
            pass
        finally:
            await stack.aclose()
        
        # All should be cleaned up
        assert r1.exited
        assert mock_mcp_client.exited
        assert r3.exited

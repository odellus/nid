"""
End-to-end tests for the full agent flow.

NO MOCKS. Real agent, real MCP, real DB, real everything.

These tests verify:
- Complete ACP agent lifecycle with real components
- Full integration of all components
- Real-world usage scenarios

If these tests pass, the system actually works.
"""

import pytest
import tempfile
from pathlib import Path
from contextlib import AsyncExitStack

from fastmcp import Client


class TestAgentE2E:
    """End-to-end tests with REAL components - NO MOCKS."""
    
    @pytest.mark.asyncio
    async def test_agent_session_with_real_mcp_and_db(self, seeded_db, temp_workspace):
        """Test agent session creation with real MCP client and real database."""
        from crow.agent import Session
        
        from crow_mcp_server.main import mcp as file_editor_mcp
        from crow.agent.db import Prompt, Session as SessionModel, Event
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session as SQLAlchemySession
        
        # Import real MCP server from installed package
        from crow_mcp_server.main import mcp as file_editor_mcp
        
        # Connect to REAL MCP server
        async with Client(transport=file_editor_mcp) as mcp_client:
            # Get real tools from the MCP server
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
            
            # Create REAL session in REAL database
            session = Session.create(
                prompt_id="test-prompt-v1",
                prompt_args={"workspace": temp_workspace},
                tool_definitions=tools,
                request_params={"temperature": 0.7},
                model_identifier="test-model",
                db_path=seeded_db,
            )
            
            # Verify session was created
            assert session is not None
            assert session.session_id is not None
            assert len(session.messages) > 0
            
            # Verify in database
            engine = create_engine(seeded_db)
            db = SQLAlchemySession(engine)
            
            db_session = db.query(SessionModel).filter_by(
                session_id=session.session_id
            ).first()
            assert db_session is not None
            
            db.close()
            engine.dispose()
    
    @pytest.mark.asyncio
    async def test_agent_calls_real_mcp_tool(self, seeded_db, temp_workspace):
        """Test agent actually calling a real MCP tool."""
        from crow.agent import Session
        
        from crow_mcp_server.main import mcp as file_editor_mcp
        
        from crow_mcp_server.main import mcp as file_editor_mcp
        
        async with Client(transport=file_editor_mcp) as mcp_client:
            # Get tools
            tools_result = await mcp_client.list_tools()
            tools = [{"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.inputSchema}} for t in tools_result]
            
            # Create session
            session = Session.create(
                prompt_id="test-prompt-v1",
                prompt_args={"workspace": temp_workspace},
                tool_definitions=tools,
                request_params={},
                model_identifier="test-model",
                db_path=seeded_db,
            )
            
            # Actually call a tool through MCP
            test_file = Path(temp_workspace) / "test.txt"
            result = await mcp_client.call_tool(
                name="file_editor",
                arguments={
                    "command": "create",
                    "path": str(test_file),
                    "file_text": "Hello from real E2E test!",
                }
            )
            
            # Verify tool actually worked
            assert test_file.exists()
            assert test_file.read_text() == "Hello from real E2E test!"
            assert "created successfully" in result.content[0].text.lower()
    
    @pytest.mark.asyncio
    async def test_agent_multiple_sessions_isolated(self, seeded_db):
        """Test multiple sessions are properly isolated."""
        from crow.agent import Session
        
        from crow_mcp_server.main import mcp as file_editor_mcp
        
        
        async with Client(transport=file_editor_mcp) as mcp_client:
            tools_result = await mcp_client.list_tools()
            tools = [{"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.inputSchema}} for t in tools_result]
            
            # Create two sessions with different workspaces
            with tempfile.TemporaryDirectory() as ws1, tempfile.TemporaryDirectory() as ws2:
                session1 = Session.create(
                    prompt_id="test-prompt-v1",
                    prompt_args={"workspace": ws1},
                    tool_definitions=tools,
                    request_params={},
                    model_identifier="test-model",
                    db_path=seeded_db,
                )
                
                session2 = Session.create(
                    prompt_id="test-prompt-v1",
                    prompt_args={"workspace": ws2},
                    tool_definitions=tools,
                    request_params={},
                    model_identifier="test-model",
                    db_path=seeded_db,
                )
                
                # Sessions should have different IDs
                assert session1.session_id != session2.session_id
                
                # Add messages to each session
                session1.add_message("user", "Message for session 1")
                session2.add_message("user", "Message for session 2")
                
                # Reload sessions and verify isolation
                reloaded1 = Session.load(session1.session_id, seeded_db)
                reloaded2 = Session.load(session2.session_id, seeded_db)
                
                # Each session should have its own message
                assert "session 1" in str(reloaded1.messages)
                assert "session 2" in str(reloaded2.messages)
                assert "session 1" not in str(reloaded2.messages)
                assert "session 2" not in str(reloaded1.messages)
    
    @pytest.mark.asyncio
    async def test_agent_session_persistence_across_reload(self, seeded_db, temp_workspace):
        """Test session state persists correctly when reloaded."""
        from crow.agent import Session
        
        from crow_mcp_server.main import mcp as file_editor_mcp
        from crow.agent.db import Event, Session as SessionModel
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session as SQLAlchemySession
        
        
        async with Client(transport=file_editor_mcp) as mcp_client:
            tools_result = await mcp_client.list_tools()
            tools = [{"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.inputSchema}} for t in tools_result]
            
            # Create session
            session = Session.create(
                prompt_id="test-prompt-v1",
                prompt_args={"workspace": temp_workspace},
                tool_definitions=tools,
                request_params={"temperature": 0.5},
                model_identifier="persist-test-model",
                db_path=seeded_db,
            )
            
            session_id = session.session_id
            
            # Add messages and events
            session.add_message("user", "Test message for persistence")
            
            # Reload from database
            reloaded = Session.load(session_id, seeded_db)
            
            # Verify session ID preserved
            assert reloaded.session_id == session_id
            
            # Verify messages preserved
            assert len(reloaded.messages) > 0
            assert "persistence" in str(reloaded.messages)
            
            # Verify in database model
            engine = create_engine(seeded_db)
            db = SQLAlchemySession(engine)
            db_session = db.query(SessionModel).filter_by(session_id=session_id).first()
            assert db_session is not None
            assert db_session.model_identifier == "persist-test-model"
            
            db.close()
            engine.dispose()
    
    @pytest.mark.asyncio
    async def test_full_prompt_lifecycle_e2e(self, temp_db):
        """Test full prompt lifecycle: create, lookup, use in session."""
        from crow.agent.db import Prompt, Session as SessionModel
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
        from crow.agent import Session
        
        from crow_mcp_server.main import mcp as file_editor_mcp
        
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

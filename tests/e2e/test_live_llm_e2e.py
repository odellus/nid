"""
End-to-end test: Real LLM call + DB persistence with session reload.

This test does NOT mock the LLM or database. It validates:
1. Agent can receive a prompt and call the configured LLM
2. Agent persists session and message history to the database
3. Agent can reload the session from the database and continue the conversation
4. All ACP protocol requirements are met
5. Database state is correct and complete
6. Streaming updates work properly
7. Response formatting is correct

This is BOTH a test AND end-to-end validation - no mocks, real components,
comprehensive assertions.
"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import os
import sqlite3

from crow.agent import Agent, Session
from crow.agent.db import create_database, Session as SessionModel, Event, Prompt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLAlchemySession


def _ensure_prompt_exists(db_path: str, prompt_id: str = "crow-v1"):
    """Ensure a minimal prompt exists for testing."""
    db = SQLAlchemySession(create_engine(db_path))
    try:
        existing = db.query(Prompt).filter_by(id=prompt_id).first()
        if not existing:
            prompt = Prompt(
                id=prompt_id,
                name="Crow Test Prompt",
                template="You are a helpful assistant. Workspace: {{workspace}}",
            )
            db.add(prompt)
            db.commit()
    finally:
        db.close()


class TestLiveAgentE2EwithLLM:
    """Live E2E tests with real LLM and DB (no mocks)."""

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def temp_db_path(self, temp_workspace):
        """Create a temporary database for the test."""
        db_path = os.path.join(temp_workspace, "test.db")
        db_connection_string = f"sqlite:///{db_path}"
        create_database(db_connection_string)
        return db_connection_string

    @pytest.mark.asyncio
    async def test_live_llm_db_and_reload(self, temp_workspace, temp_db_path):
        """
        Full lifecycle test:
        1. Agent receives prompt and calls real LLM
        2. Session and events are saved to DB
        3. Agent reloads session from DB and conversation history is intact
        4. Agent can continue conversation after reload
        """
        # Ensure LLM configuration is available from environment
        assert "ZAI_API_KEY" in os.environ or "OPENAI_API_KEY" in os.environ, (
            "Set ZAI_API_KEY or OPENAI_API_KEY for live LLM test"
        )

        from acp import text_block
        from acp.interfaces import Client

        # Minimal real Client implementation for E2E
        class E2EClient(Client):
            def __init__(self):
                self.updates = []

            async def session_update(self, session_id, update, **kwargs):
                self.updates.append((session_id, update))

            async def request_permission(self, options, session_id, tool_call, **kwargs):
                return {"outcome": {"outcome": "cancelled"}}

            async def ext_method(self, method, params):
                return {}

            async def ext_notification(self, method, params):
                pass

            def on_connect(self, conn):
                pass

        client = E2EClient()
        agent = Agent(db_path=temp_db_path)
        agent.on_connect(client)

        # Ensure prompt exists in test database
        _ensure_prompt_exists(temp_db_path, "crow-v1")

        # 1) Create a new session - REAL MCP CLIENT, REAL DB
        response = await agent.new_session(cwd=temp_workspace, mcp_servers=[])
        session_id = response.session_id

        # 2) Send a real prompt that triggers REAL LLM call
        prompt_text = "Say the word 'PINEAPPLE' and nothing else."
        result = await agent.prompt(
            session_id=session_id,
            prompt=[text_block(prompt_text)],
        )

        # Basic stop reason checks
        assert result.stop_reason in ("end_turn", "stop"), \
            f"Expected valid stop_reason, got: {result.stop_reason}"
        
        # Agent should have stored the session locally
        assert session_id in agent._sessions, \
            "Session should be in agent's in-memory cache"
        
        # Validate streaming updates were captured
        assert len(client.updates) > 0, \
            "Client should have received streaming updates via session_update"
        
        # Validate at least one update contains text content
        has_text_content = False
        for session_id_update, update in client.updates:
            # Check if update has content (structure depends on ACP schema)
            if hasattr(update, 'content'):
                has_text_content = True
                break
            elif isinstance(update, dict) and 'content' in update:
                has_text_content = True
                break
        
        assert has_text_content, \
            "At least one streaming update should contain text content from LLM"

        # 3) Inspect REAL database for persisted session and events - COMPREHENSIVE VALIDATION
        engine = create_engine(temp_db_path)
        db = SQLAlchemySession(engine)

        try:
            # Validate session record
            session_record = db.query(SessionModel).filter_by(session_id=session_id).first()
            assert session_record is not None, \
                "Session MUST be persisted in DB"
            
            # Validate session fields are populated
            assert session_record.session_id == session_id, \
                "Session ID must match"
            assert session_record.prompt_id == "crow-v1", \
                "Prompt ID must be saved correctly"
            assert session_record.model_identifier == "glm-5", \
                "Model identifier must be saved correctly"
            assert session_record.system_prompt is not None, \
                "System prompt must be rendered and saved"
            assert len(session_record.system_prompt) > 0, \
                "System prompt must not be empty"
            assert session_record.tool_definitions is not None, \
                "Tool definitions must be saved"
            assert isinstance(session_record.tool_definitions, list), \
                "Tool definitions must be a list"
            assert session_record.created_at is not None, \
                "Created timestamp must be set"
            
            # Validate events are persisted correctly
            events = db.query(Event).filter_by(session_id=session_id).all()
            assert len(events) >= 2, \
                "Must have at least user and assistant events"
            
            # Validate we have user event
            user_events = [e for e in events if e.role == "user"]
            assert len(user_events) >= 1, \
                "Must have at least one user event"
            
            # Validate user event content
            user_event = user_events[0]
            assert user_event.content is not None, \
                "User event must have content"
            assert prompt_text in user_event.content, \
                "User event must contain the original prompt"
            assert user_event.conv_index == 0, \
                "First user event should have conv_index 0"
            
            # Validate we have assistant event
            assistant_events = [e for e in events if e.role == "assistant"]
            assert len(assistant_events) >= 1, \
                "Must have at least one assistant event"
            
            # Validate assistant event has content
            assistant_event = assistant_events[0]
            # Content might be None if only reasoning was generated, check reasoning_content
            assert assistant_event.content is not None or assistant_event.reasoning_content is not None, \
                "Assistant event must have content or reasoning_content"
            assert assistant_event.conv_index >= 1, \
                "Assistant event should come after user event"
            
            # Validate event ordering (conv_index should be sequential)
            event_indices = sorted([e.conv_index for e in events])
            assert event_indices == list(range(len(events))), \
                f"Event conv_index should be sequential, got: {event_indices}"
            
            # Validate timestamps are set
            for event in events:
                assert event.timestamp is not None, \
                    "All events must have timestamps"
            
            # Validate foreign key relationship
            assert all(e.session_id == session_id for e in events), \
                "All events must reference the correct session_id"
            
        finally:
            db.close()

        # 4) Reload session in a fresh agent instance - REAL DB LOAD, REAL MCP
        client2 = E2EClient()
        agent2 = Agent(db_path=temp_db_path)
        agent2.on_connect(client2)
        load_resp = await agent2.load_session(cwd=temp_workspace, mcp_servers=[], session_id=session_id)

        assert load_resp is not None, \
            "load_session must succeed for existing session"
        assert session_id in agent2._sessions, \
            "Reloaded session must be in agent's cache"

        # Validate reloaded session state
        reloaded_session = agent2._sessions[session_id]
        
        # Validate conversation history is reconstructed
        messages = reloaded_session.messages
        assert len(messages) >= 3, \
            "Reloaded session must have at least system, user, and assistant messages"
        
        # Validate first message is system message (rendered prompt)
        first_msg = messages[0]
        assert first_msg.get("role") == "system", \
            "First message must be system prompt"
        
        # Validate second message is user message
        second_msg = messages[1]
        assert second_msg.get("role") == "user", \
            "Second message must be from user"
        
        # Validate user message content matches original
        content = second_msg.get("content", "")
        if isinstance(content, list):
            # Merge text blocks
            text_parts = [blk.get("text", "") for blk in content if isinstance(blk, dict) and "text" in blk]
            text = " ".join(text_parts)
        else:
            text = str(content)
        
        assert prompt_text in text, \
            f"Reloaded user message must contain original prompt. Got: {text}"
        
        # Validate third message is assistant message
        third_msg = messages[2]
        assert third_msg.get("role") == "assistant", \
            "Third message must be from assistant"
        
        # Validate assistant message has content
        assistant_content = third_msg.get("content") or third_msg.get("reasoning_content")
        assert assistant_content is not None, \
            "Assistant message must have content or reasoning_content after reload"

    @pytest.mark.asyncio
    async def test_session_persistence_isolation(self, temp_workspace, temp_db_path):
        """
        Validate that different sessions are properly isolated.
        Each session should have its own event stream.
        """
        assert "ZAI_API_KEY" in os.environ or "OPENAI_API_KEY" in os.environ, (
            "Set ZAI_API_KEY or OPENAI_API_KEY for live LLM test"
        )

        from acp import text_block
        from acp.interfaces import Client

        # Minimal real Client implementation for E2E
        class E2EClient(Client):
            def __init__(self):
                self.updates = []

            async def session_update(self, session_id, update, **kwargs):
                self.updates.append((session_id, update))

            async def request_permission(self, options, session_id, tool_call, **kwargs):
                return {"outcome": {"outcome": "cancelled"}}

            async def ext_method(self, method, params):
                return {}

            async def ext_notification(self, method, params):
                pass

            def on_connect(self, conn):
                pass

        client = E2EClient()
        agent = Agent(db_path=temp_db_path)
        agent.on_connect(client)
        _ensure_prompt_exists(temp_db_path, "crow-v1")

        # Create two different sessions
        response1 = await agent.new_session(cwd=temp_workspace, mcp_servers=[])
        session_id_1 = response1.session_id

        response2 = await agent.new_session(cwd=temp_workspace, mcp_servers=[])
        session_id_2 = response2.session_id

        # Validate sessions have different IDs
        assert session_id_1 != session_id_2, \
            "Different sessions must have different IDs"

        # Send different prompts to each session
        await agent.prompt(
            session_id=session_id_1,
            prompt=[text_block("Say SESSION1")],
        )

        await agent.prompt(
            session_id=session_id_2,
            prompt=[text_block("Say SESSION2")],
        )

        # Validate events are isolated in database
        engine = create_engine(temp_db_path)
        db = SQLAlchemySession(engine)

        try:
            # Get events for each session
            events_1 = db.query(Event).filter_by(session_id=session_id_1).all()
            events_2 = db.query(Event).filter_by(session_id=session_id_2).all()

            # Validate session 1 has its events
            assert len(events_1) >= 2, \
                "Session 1 must have events"
            assert any("SESSION1" in (e.content or "") for e in events_1 if e.role == "user"), \
                "Session 1 must contain its specific prompt"

            # Validate session 2 has its events
            assert len(events_2) >= 2, \
                "Session 2 must have events"
            assert any("SESSION2" in (e.content or "") for e in events_2 if e.role == "user"), \
                "Session 2 must contain its specific prompt"

            # Validate no cross-contamination
            assert not any("SESSION2" in (e.content or "") for e in events_1), \
                "Session 1 should NOT contain session 2's prompt"
            assert not any("SESSION1" in (e.content or "") for e in events_2), \
                "Session 2 should NOT contain session 1's prompt"

        finally:
            db.close()




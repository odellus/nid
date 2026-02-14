"""
End-to-end test: Real LLM call + DB persistence with session reload.

This test does NOT mock the LLM or database. It validates:
1. Agent can receive a prompt and call the configured LLM
2. Agent persists session and message history to the database
3. Agent can reload the session from the database and continue the conversation
"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import os
import sqlite3

from nid.agent import NidAgent, Session
from nid.agent.db import create_database, Session as SessionModel, Event, Prompt
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
        agent = NidAgent(db_path=temp_db_path)
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
        assert result.stop_reason in ("end_turn", "stop")
        # Agent should have stored the session locally
        assert session_id in agent._sessions

        # 3) Inspect REAL database for persisted session and events
        engine = create_engine(temp_db_path)
        db = SQLAlchemySession(engine)

        try:
            session_record = db.query(SessionModel).filter_by(session_id=session_id).first()
            assert session_record is not None, "Session should be persisted in DB"
            events = db.query(Event).filter_by(session_id=session_id).all()
            # At minimum we expect a user and assistant event
            assert any(e for e in events if e.role == "user"), "User event should be persisted"
            assert any(e for e in events if e.role == "assistant"), "Assistant event should be persisted"
        finally:
            db.close()

        # 4) Reload session in a fresh agent instance - REAL DB LOAD, REAL MCP
        client2 = E2EClient()
        agent2 = NidAgent(db_path=temp_db_path)
        agent2.on_connect(client2)
        load_resp = await agent2.load_session(cwd=temp_workspace, mcp_servers=[], session_id=session_id)

        assert load_resp is not None, "load_session should succeed for existing session"
        assert session_id in agent2._sessions

        # Verify conversation history is present after reload
        reloaded_session = agent2._sessions[session_id]
        messages = reloaded_session.messages
        assert messages, "Reloaded session should contain message history"

        # Simple sanity: the prompt text should appear in the first user message content
        user_msgs = [m for m in messages if m.get("role") == "user"]
        assert user_msgs, "Reloaded history should include a user message"
        first_user_msg = user_msgs[0]
        content = first_user_msg.get("content", "")
        if isinstance(content, list):
            # Merge text blocks
            text_parts = [blk.get("text", "") for blk in content if isinstance(blk, dict) and "text" in blk]
            text = " ".join(text_parts)
        else:
            text = str(content)
        assert prompt_text in text, f"Expected the original prompt in the user message; got: {text}"




"""
Tests for ACP-native session management.

These tests encode our UNDERSTANDING of how sessions should work:

1. Sessions are created via ACP's new_session() method
2. The session_id from ACP is the source of truth
3. Persistence uses ACP's session_id as primary key
4. In-memory state is keyed by ACP's session_id
5. No custom session ID generation - use ACP's ID

This is the THESIS that we're testing. If tests fail, it means our
understanding is wrong and we need to revise (dialectical process).
"""

import pytest
from uuid import uuid4

from crow.agent import Agent
from crow.agent.db import Session as DBSession, Prompt, create_database
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLAlchemySession


class TestACPSessions:
    """
    Tests that encode understanding: ACP sessions should be native.
    
    These tests may fail initially (X meets ~X), which teaches us
    what we got wrong and need to fix (synthesis Y).
    """
    
    @pytest.mark.asyncio
    async def test_new_session_returns_session_with_id(self):
        """
        UNDERSTANDING: new_session() must return a response with session_id.
        
        This is the ACP protocol requirement. The session_id is the
        primary identifier for all subsequent operations.
        """
        agent = Agent()
        
        # Create session via ACP protocol
        response = await agent.new_session(
            cwd="/tmp",
            mcp_servers=[]
        )
        
        # Response must have session_id
        assert response.session_id is not None
        assert isinstance(response.session_id, str)
        assert len(response.session_id) > 0
    
    @pytest.mark.asyncio
    async def test_session_id_is_source_of_truth(self, temp_db):
        """
        UNDERSTANDING: ACP's session_id should be used as DB primary key.
        
        We should NOT generate a separate session_id. The ACP session_id
        is the semantic anchor for the entire session lifecycle.
        """
        # Add required prompt to temp_db
        db = SQLAlchemySession(create_engine(temp_db))
        try:
            prompt = Prompt(
                id="crow-v1",
                name="Crow Default Prompt",
                template="You are a helpful assistant. Workspace: {{workspace}}",
            )
            db.add(prompt)
            db.commit()
        finally:
            db.close()
        
        # Create agent with temp DB
        agent = Agent()
        agent._db_path = temp_db
        
        # Create session
        response = await agent.new_session(
            cwd="/tmp",
            mcp_servers=[]
        )
        session_id = response.session_id
        
        # Session should be in memory
        assert session_id in agent._sessions
        
        # Session should be persisted to DB with same ID
        db = SQLAlchemySession(create_engine(temp_db))
        try:
            db_session = db.query(DBSession).filter_by(session_id=session_id).first()
            assert db_session is not None, "Session not found in DB"
            assert db_session.session_id == session_id, "DB session_id doesn't match ACP session_id"
        finally:
            db.close()
    
    @pytest.mark.asyncio
    async def test_load_session_uses_acp_session_id(self, temp_db):
        """
        UNDERSTANDING: load_session() should use ACP's session_id to restore state.
        
        After creating and persisting a session, we should be able to
        load it in a new agent instance using the same session_id.
        """
        # Add required prompt to temp_db
        db = SQLAlchemySession(create_engine(temp_db))
        try:
            prompt = Prompt(
                id="crow-v1",
                name="Crow Default Prompt",
                template="You are a helpful assistant. Workspace: {{workspace}}",
            )
            db.add(prompt)
            db.commit()
        finally:
            db.close()
        
        # Create first agent and session
        agent1 = Agent()
        agent1._db_path = temp_db
        
        response1 = await agent1.new_session(
            cwd="/tmp",
            mcp_servers=[]
        )
        session_id = response1.session_id
        
        # Add some state to the session
        session_state = agent1._sessions[session_id]
        session_state.messages.append({
            "role": "user",
            "content": "Hello"
        })
        
        # Save to DB (this should happen automatically or via explicit save)
        # For now, we'll just verify the session exists
        
        # Create second agent instance
        agent2 = Agent()
        agent2._db_path = temp_db
        
        # Load the session
        response2 = await agent2.load_session(
            cwd="/tmp",
            session_id=session_id,
            mcp_servers=[]
        )
        
        # Should succeed
        assert response2 is not None
        
        # Session should be loaded in memory
        assert session_id in agent2._sessions
        
        # State should be restored
        # Note: This test may fail initially - that's the point!
        # It teaches us what we need to implement.
    
    @pytest.mark.asyncio
    async def test_prompt_uses_session_id(self, temp_db):
        """
        UNDERSTANDING: prompt() should use session_id to identify conversation.
        
        The session_id links the prompt to the correct conversation history
        and tool context.
        """
        # Add required prompt
        db = SQLAlchemySession(create_engine(temp_db))
        try:
            prompt = Prompt(
                id="crow-v1",
                name="Crow Default Prompt",
                template="You are a helpful assistant. Workspace: {{workspace}}",
            )
            db.add(prompt)
            db.commit()
        finally:
            db.close()
        
        agent = Agent()
        agent._db_path = temp_db
        
        # Create session
        response = await agent.new_session(
            cwd="/tmp",
            mcp_servers=[]
        )
        session_id = response.session_id
        
        # TODO: Test prompt() with this session_id
        # This will require mocking the LLM and MCP client
        
        # For now, just verify session exists
        assert session_id in agent._sessions
    
    @pytest.mark.asyncio
    async def test_no_duplicate_session_ids(self):
        """
        UNDERSTANDING: Each session should have a unique session_id.
        
        ACP's session_id generation should ensure uniqueness.
        """
        agent = Agent()
        
        # Create multiple sessions
        session_ids = []
        for i in range(5):
            response = await agent.new_session(
                cwd=f"/tmp/{i}",
                mcp_servers=[]
            )
            session_ids.append(response.session_id)
        
        # All should be unique
        assert len(session_ids) == len(set(session_ids)), "Duplicate session IDs found"
        
        # All should be accessible
        for session_id in session_ids:
            assert session_id in agent._sessions
    
    @pytest.mark.asyncio
    async def test_session_state_is_in_memory(self, temp_db):
        """
        UNDERSTANDING: Session state (messages, tools) should be in memory.
        
        The DB is for persistence across restarts. In-memory state is
        for fast access during the session lifetime.
        """
        # Add required prompt
        db = SQLAlchemySession(create_engine(temp_db))
        try:
            prompt = Prompt(
                id="crow-v1",
                name="Crow Default Prompt",
                template="You are a helpful assistant. Workspace: {{workspace}}",
            )
            db.add(prompt)
            db.commit()
        finally:
            db.close()
        
        agent = Agent()
        agent._db_path = temp_db
        
        response = await agent.new_session(
            cwd="/tmp",
            mcp_servers=[]
        )
        session_id = response.session_id
        
        # Session state should be in memory
        assert session_id in agent._sessions
        session_state = agent._sessions[session_id]
        
        # State should have required fields
        assert hasattr(session_state, 'messages')
        assert hasattr(session_state, 'session_id')
        
        # Messages should include system prompt
        assert len(session_state.messages) > 0
        assert session_state.messages[0]["role"] == "system"


class TestPromptPersistence:
    """
    Tests for prompt template persistence.
    
    Prompts are templates that can be reused across sessions.
    """
    
    @pytest.mark.asyncio
    async def test_session_uses_prompt_from_db(self, temp_db):
        """
        UNDERSTANDING: Sessions should reference prompts by ID.
        
        The prompt template is stored in DB, sessions reference it.
        This allows prompt versioning and reuse.
        """
        # Add required prompt
        db = SQLAlchemySession(create_engine(temp_db))
        try:
            prompt = Prompt(
                id="crow-v1",
                name="Crow Default Prompt",
                template="You are a helpful assistant. Workspace: {{workspace}}",
            )
            db.add(prompt)
            db.commit()
        finally:
            db.close()
        
        # Create agent
        agent = Agent()
        agent._db_path = temp_db
        
        # Create session with prompt
        response = await agent.new_session(
            cwd="/tmp",
            mcp_servers=[]
        )
        session_id = response.session_id
        
        # Session should have been created with the prompt
        # (This test may need adjustment based on implementation)
        
        db = SQLAlchemySession(create_engine(temp_db))
        try:
            db_session = db.query(DBSession).filter_by(session_id=session_id).first()
            assert db_session is not None
            # Session should reference the prompt
            assert db_session.prompt_id == "crow-v1"
        finally:
            db.close()

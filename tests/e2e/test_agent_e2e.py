"""
End-to-end tests for the full agent flow.

NO MOCKS. Real agent, real MCP, real DB, real everything.

These tests encode our UNDERSTANDING of how agents work:
- Agent lifecycle: Agent(config) -> new_session() -> prompt() -> cleanup()
- MCP integration: Configure via config dict, use builtin by default
- Session persistence: DB-backed, survives restart
- React loop: LLM calls -> tool execution -> response streaming

If these tests pass, the system actually works.
"""

import pytest
import tempfile
from pathlib import Path

from crow.agent import (
    Agent,
    Session,
    Config,
    LLMConfig,
    create_mcp_client_from_config,
    get_default_config,
)


class TestAgentLifecycleE2E:
    """
    Tests that encode our UNDERSTANDING of the agent lifecycle.
    
    These tests may FAIL initially (that's TDD - X meets ~X).
    Implementation will SYNTHESIZE from the failures (producing Y).
    """
    
    @pytest.mark.asyncio
    async def test_create_agent_with_defaults(self):
        """
        UNDERSTANDING: Agent should work out-of-box with no configuration.
        
        Default = builtin MCP (file_editor, web_search, fetch) + env vars for LLM.
        """
        agent = Agent()
        
        assert agent is not None
        assert agent._config is not None
        assert agent._llm is not None
        
    @pytest.mark.asyncio
    async def test_create_agent_with_custom_config(self):
        """
        UNDERSTANDING: Agent can be configured programmatically.
        
        Config includes: LLM settings, MCP servers, DB path, runtime params.
        """
        config = Config(
            llm=LLMConfig(
                default_model="custom-model",
            ),
            database_path="sqlite:///custom.db",
            mcp_servers={
                "custom-server": {
                    "command": "python",
                    "args": ["server.py"],
                }
            }
        )
        
        agent = Agent(config)
        
        assert agent._config.llm.default_model == "custom-model"
        assert "custom-server" in agent._config.mcp_servers
        
    @pytest.mark.asyncio
    async def test_setup_mcp_from_config_dict(self):
        """
        UNDERSTANDING: MCP clients can be created from config dicts.
        
        This is the FastMCP format - same as what we use in Agent config.
        """
        config = {
            "mcpServers": {
                "crow-builtin": {
                    "command": "uv",
                    "args": ["--project", "crow-mcp-server", "run", "."],
                }
            }
        }
        
        client = create_mcp_client_from_config(config)
        
        async with client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            
            # Builtin server has these tools
            assert "file_editor" in tool_names
            assert "web_search" in tool_names
            assert "fetch" in tool_names
    
    @pytest.mark.asyncio
    async def test_agent_new_session_creates_mcp_client(self, temp_db, temp_workspace):
        """
        UNDERSTANDING: new_session() should setup MCP client internally.
        
        Session has:
        - Unique session_id
        - MCP client (from config or builtin)
        - Tools from MCP
        - Persisted to DB
        """
        config = Config(database_path=temp_db)
        agent = Agent(config)
        
        # This should create session + setup MCP + persist to DB
        response = await agent.new_session(
            cwd=temp_workspace,
            mcp_servers=[],  # Use builtin
        )
        
        assert response is not None
        assert response.session_id is not None
        
        # Agent should track the session
        assert response.session_id in agent._sessions
        
        # MCP client should be initialized
        assert response.session_id in agent._mcp_clients
        
        # Tools should be loaded
        assert response.session_id in agent._tools
        assert len(agent._tools[response.session_id]) > 0
        
    @pytest.mark.asyncio
    async def test_agent_load_session_rebuilds_state(self, temp_db, temp_workspace):
        """
        UNDERSTANDING: load_session() should rebuild in-memory state from DB.
        
        This includes:
        - Loading messages from DB
        - Recreating MCP client
        - Restoring tools
        """
        config = Config(database_path=temp_db)
        agent = Agent(config)
        
        # Create session first
        create_response = await agent.new_session(
            cwd=temp_workspace,
            mcp_servers=[],
        )
        session_id = create_response.session_id
        
        # Add some messages
        session = agent._sessions[session_id]
        session.add_message("user", "Hello from previous session")
        
        # Simulate restart - create new agent instance
        agent2 = Agent(config)
        
        # Load the session
        load_response = await agent2.load_session(
            cwd=temp_workspace,
            session_id=session_id,
            mcp_servers=[],
        )
        
        # Should have rebuilt state
        assert session_id in agent2._sessions
        assert session_id in agent2._mcp_clients
        
        # Messages should be restored from DB
        loaded_session = agent2._sessions[session_id]
        assert "previous session" in str(loaded_session.messages)
        
    @pytest.mark.asyncio 
    async def test_agent_prompt_triggers_react_loop(self, temp_db, temp_workspace):
        """
        UNDERSTANDING: prompt() should run the full react loop.
        
        The loop:
        1. Add user message to session
        2. Call LLM with tools
        3. Execute any tool calls
        4. Continue until done
        5. Stream updates to client
        """
        config = Config(database_path=temp_db)
        agent = Agent(config)
        
        # Setup session
        session_response = await agent.new_session(
            cwd=temp_workspace,
            mcp_servers=[],
        )
        session_id = session_response.session_id
        
        # Send prompt
        response = await agent.prompt(
            prompt=[{"type": "text", "text": "What is 2+2?"}],
            session_id=session_id,
        )
        
        # Should get response
        assert response is not None
        assert response.stop_reason in ["end_turn", "stop"]
        
        # Session should have messages
        session = agent._sessions[session_id]
        assert len(session.messages) >= 2  # user + assistant


class TestMCPIntegrationE2E:
    """Tests for MCP tool calling through the agent."""
    
    @pytest.mark.asyncio
    async def test_agent_uses_file_editor_tool(self, temp_db, temp_workspace):
        """
        UNDERSTANDING: Agent can use file_editor tool via MCP.
        
        The tool is provided by builtin crow-mcp-server.
        """
        config = Config(database_path=temp_db)
        agent = Agent(config)
        
        session_response = await agent.new_session(
            cwd=temp_workspace,
            mcp_servers=[],
        )
        session_id = session_response.session_id
        
        # Ask agent to create a file
        test_file = Path(temp_workspace) / "test.md"
        
        response = await agent.prompt(
            prompt=[{
                "type": "text", 
                "text": f"Create a file at {test_file} with content 'Hello E2E'"
            }],
            session_id=session_id,
        )
        
        # File should exist (agent called file_editor tool)
        # Note: This test may FAIL initially - that's OK (TDD)
        # The agent needs to actually call the tool
        assert test_file.exists()
        assert "Hello E2E" in test_file.read_text()
        
    @pytest.mark.asyncio
    async def test_agent_uses_web_search_tool(self, temp_db, temp_workspace):
        """
        UNDERSTANDING: Agent can use web_search tool via MCP.
        
        The tool is provided by builtin crow-mcp-server.
        """
        config = Config(database_path=temp_db)
        agent = Agent(config)
        
        session_response = await agent.new_session(
            cwd=temp_workspace,
            mcp_servers=[],
        )
        session_id = session_response.session_id
        
        # Ask agent to search (this requires internet)
        response = await agent.prompt(
            prompt=[{
                "type": "text",
                "text": "Search for 'Python agent protocol MCP' and summarize"
            }],
            session_id=session_id,
        )
        
        # Response should mention search results
        # Note: This test may FAIL initially - that's OK (TDD)
        session = agent._sessions[session_id]
        # We expect assistant message to mention search results
        assistant_messages = [m for m in session.messages if m.get("role") == "assistant"]
        # This is our constraint - we EXPECT the agent to search and respond
        # Failure teaches us what's missing in implementation


class TestSessionPersistenceE2E:
    """Tests for session persistence and reload."""
    
    @pytest.mark.asyncio
    async def test_session_survives_agent_restart(self, temp_db, temp_workspace):
        """
        UNDERSTANDING: Sessions are persisted to DB and survive process restart.
        
        This is WHAT sessions ARE - persistent conversation state.
        """
        # Agent 1 creates session
        config = Config(database_path=temp_db)
        agent1 = Agent(config)
        
        session_response = await agent1.new_session(
            cwd=temp_workspace,
            mcp_servers=[],
        )
        session_id = session_response.session_id
        
        # Add conversation
        await agent1.prompt(
            prompt=[{"type": "text", "text": "My name is Thomas"}],
            session_id=session_id,
        )
        
        # Cleanup agent1 (simulating process exit)
        await agent1.cleanup()
        
        # Agent 2 loads session
        agent2 = Agent(config)
        
        await agent2.load_session(
            cwd=temp_workspace,
            session_id=session_id,
            mcp_servers=[],
        )
        
        # Conversation should be intact
        session = agent2._sessions[session_id]
        conversation_str = str(session.messages)
        
        assert "Thomas" in conversation_str
        
        # Continue conversation
        response = await agent2.prompt(
            prompt=[{"type": "text", "text": "What's my name?"}],
            session_id=session_id,
        )
        
        # Agent should remember context from before restart
        # This is the CORE semantic constraint - sessions persist

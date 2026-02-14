"""
ACP Agent wrapper for NID Agent.

This wraps our clean Agent/Session implementation with ACP protocol handling.
"""

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any

from acp import (
    PROTOCOL_VERSION,
    Agent,
    AuthenticateResponse,
    InitializeResponse,
    LoadSessionResponse,
    NewSessionResponse,
    PromptResponse,
    SetSessionModeResponse,
    run_agent,
    text_block,
    update_agent_message,
)
from acp.interfaces import Client
from acp.schema import (
    AgentCapabilities,
    AgentMessageChunk,
    AudioContentBlock,
    ClientCapabilities,
    EmbeddedResourceContentBlock,
    HttpMcpServer,
    ImageContentBlock,
    Implementation,
    McpServerStdio,
    ResourceContentBlock,
    SseMcpServer,
    TextContentBlock,
    ToolCallProgress,
    ToolCallStart,
)

from nid.agent import Agent as NidAgent
from nid.agent import Session, configure_llm, get_tools, setup_mcp_client

logger = logging.getLogger(__name__)


class CrowACPAgent(Agent):
    """
    ACP protocol wrapper for NID Agent.
    
    Handles:
    - ACP protocol methods (initialize, new_session, prompt, etc.)
    - Session management (maps ACP session IDs to NID Sessions)
    - Streaming updates (converts NID generator to ACP notifications)
    - Resource lifecycle (MCP clients are properly cleaned up)
    
    Uses AsyncExitStack to manage MCP client lifecycle ensuring:
    - Resources are always cleaned up, even on exceptions
    - Multiple sessions can be managed independently
    - No resource leaks occur
    """
    
    _conn: Client
    _sessions: dict[str, Session]
    _agents: dict[str, NidAgent]
    _exit_stack: AsyncExitStack
    
    def __init__(self) -> None:
        self._sessions = {}
        self._agents = {}
        self._exit_stack = AsyncExitStack()
        self._llm = configure_llm(debug=False)
    
    def on_connect(self, conn: Client) -> None:
        """Store connection for sending updates"""
        self._conn = conn
    
    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: ClientCapabilities | None = None,
        client_info: Implementation | None = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        """Handle ACP initialization"""
        logger.info("Initializing Crow ACP Agent")
        return InitializeResponse(
            protocol_version=PROTOCOL_VERSION,
            agent_capabilities=AgentCapabilities(
                load_session=True,  # We support session loading
            ),
            agent_info=Implementation(
                name="crow",
                title="Crow Agent",
                version="0.1.0",
            ),
        )
    
    async def authenticate(self, method_id: str, **kwargs: Any) -> AuthenticateResponse | None:
        """Handle authentication (no-op for now)"""
        logger.info("Authentication request: %s", method_id)
        return AuthenticateResponse()
    
    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio],
        **kwargs: Any,
    ) -> NewSessionResponse:
        """Create a new session with NID Agent using AsyncExitStack for lifecycle management."""
        logger.info("Creating new session in cwd: %s", cwd)
        
        # Setup MCP client (for now, use default search.py)
        # TODO: Use mcp_servers from ACP client
        mcp_client = setup_mcp_client("src/nid/mcp/search.py")
        
        # Enter MCP client context using AsyncExitStack (proper lifecycle management!)
        # This ensures cleanup happens even if exceptions occur
        mcp_client = await self._exit_stack.enter_async_context(mcp_client)
        
        # Get tools
        tools = await get_tools(mcp_client)
        
        # Create NID session
        session = Session.create(
            prompt_id="crow-v1",
            prompt_args={"workspace": cwd},
            tool_definitions=tools,
            request_params={"temperature": 0.7},
            model_identifier="glm-5",
        )
        
        # Create NID agent
        agent = NidAgent(
            session=session,
            llm=self._llm,
            mcp_client=mcp_client,
            tools=tools,
            model="glm-5",
        )
        
        # Store session and agent
        self._sessions[session.session_id] = session
        self._agents[session.session_id] = agent
        
        logger.info("Created session: %s", session.session_id)
        return NewSessionResponse(session_id=session.session_id, modes=None)
    
    async def load_session(
        self,
        cwd: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio],
        session_id: str,
        **kwargs: Any,
    ) -> LoadSessionResponse | None:
        """Load an existing session using AsyncExitStack for lifecycle management."""
        logger.info("Loading session: %s", session_id)
        
        try:
            # Load session from database
            session = Session.load(session_id)
            
            # Setup MCP client
            mcp_client = setup_mcp_client("src/nid/mcp/search.py")
            
            # Enter MCP client context using AsyncExitStack (proper lifecycle management!)
            mcp_client = await self._exit_stack.enter_async_context(mcp_client)
            
            # Get tools
            tools = await get_tools(mcp_client)
            
            # Create agent with loaded session
            agent = NidAgent(
                session=session,
                llm=self._llm,
                mcp_client=mcp_client,
                tools=tools,
                model="glm-5",
            )
            
            # Store session and agent
            self._sessions[session_id] = session
            self._agents[session_id] = agent
            
            # Replay conversation history to client
            # TODO: Send session/update notifications for each message
            
            return LoadSessionResponse()
        except Exception as e:
            logger.error("Failed to load session %s: %s", session_id, e)
            return None
    
    async def set_session_mode(self, mode_id: str, session_id: str, **kwargs: Any) -> SetSessionModeResponse | None:
        """Handle session mode changes (not implemented yet)"""
        logger.info("Set session mode: %s -> %s", session_id, mode_id)
        return SetSessionModeResponse()
    
    async def prompt(
        self,
        prompt: list[
            TextContentBlock
            | ImageContentBlock
            | AudioContentBlock
            | ResourceContentBlock
            | EmbeddedResourceContentBlock
        ],
        session_id: str,
        **kwargs: Any,
    ) -> PromptResponse:
        """
        Handle prompt request - main entry point for user messages.
        
        This is where we run the NID Agent react loop and stream updates back.
        """
        logger.info("Prompt request for session: %s", session_id)
        
        # Get session and agent
        session = self._sessions.get(session_id)
        agent = self._agents.get(session_id)
        
        if not session or not agent:
            logger.error("Session not found: %s", session_id)
            return PromptResponse(stop_reason="error")
        
        # Extract text from prompt blocks
        user_text = []
        for block in prompt:
            if isinstance(block, dict):
                text = block.get("text", "")
            else:
                text = getattr(block, "text", "")
            if text:
                user_text.append(text)
        
        # Add user message to session
        session.add_message("user", " ".join(user_text))
        
        # Run agent loop and stream updates
        try:
            async for chunk in agent.react_loop():
                chunk_type = chunk.get("type")
                
                if chunk_type == "content":
                    # Send agent message chunk
                    await self._conn.session_update(
                        session_id,
                        update_agent_message(text_block(chunk["token"])),
                    )
                
                elif chunk_type == "thinking":
                    # Send agent thought chunk (if client supports it)
                    # TODO: Use update_agent_thought() when available
                    pass
                
                elif chunk_type == "tool_call":
                    # Send tool call start
                    name, first_arg = chunk["token"]
                    # TODO: Send ToolCallStart notification
                    logger.debug("Tool call: %s(%s", name, first_arg)
                
                elif chunk_type == "tool_args":
                    # Send tool call progress
                    # TODO: Send ToolCallProgress notification
                    logger.debug("Tool args: %s", chunk["token"])
                
                elif chunk_type == "final_history":
                    # Done
                    break
            
            return PromptResponse(stop_reason="end_turn")
        
        except Exception as e:
            logger.error("Error in prompt handling: %s", e, exc_info=True)
            return PromptResponse(stop_reason="error")
    
    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        """Handle cancellation"""
        logger.info("Cancel request for session: %s", session_id)
        # TODO: Implement cancellation
    
    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Handle extension methods"""
        logger.info("Extension method: %s", method)
        return {}
    
    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Handle extension notifications"""
        logger.info("Extension notification: %s", method)
    
    async def cleanup(self) -> None:
        """
        Cleanup all resources managed by this agent.
        
        This method should be called when the agent is shutting down to ensure
        all MCP clients and other resources are properly closed.
        
        The AsyncExitStack ensures all resources are cleaned up in reverse order
        of their creation, even if exceptions occur during cleanup.
        """
        logger.info("Cleaning up Crow ACP Agent resources")
        await self._exit_stack.aclose()
        logger.info("Cleanup complete")



async def main() -> None:
    """Start the ACP agent"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Starting NID ACP Agent (merged)")
    # Use the new merged NidAgent
    from nid.agent import NidAgent
    await run_agent(NidAgent())


if __name__ == "__main__":
    asyncio.run(main())

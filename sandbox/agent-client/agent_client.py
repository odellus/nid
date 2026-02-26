"""
AgentClient - Bidirectional ACP router.

An ACP agent that can also act as an ACP client, routing requests to other agents.
This is the programmable way to build multi-agent pipelines with ACP.

Usage:
    uv --project /home/thomas/src/nid/sandbox/agent-client run python agent_client.py

The router pattern:
- Client → AgentClient (session ID: abc-123)
- AgentClient → Backend Agent 1 (session ID: abc-123)
- AgentClient → Backend Agent 2 (session ID: xyz-789)

This allows building multi-agent pipelines in pure Python.
"""

import asyncio
import logging
import sys
import uuid
from typing import Any

from acp import run_agent, text_block
from acp.interfaces import Agent
from acp.schema import (
    AgentCapabilities,
    ClientCapabilities,
    Implementation,
    McpServerStdio,
    PromptCapabilities,
    SessionConfigOption,
)
from rich.console import Console

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


class RouterAgent(Agent):
    """
    An ACP agent that routes to backend agents.

    This is the "router" in the agent-client-router pattern.
    Clients connect to this, and it forwards to backend agents.
    """

    _console: Console

    def __init__(self, console: Console | None = None):
        self._console = console or Console()

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: ClientCapabilities,
        client_info: Implementation,
    ) -> dict:
        """Initialize as an ACP agent."""
        logger.info(f"Client connected: {client_info.name} v{client_info.version}")
        return {
            "protocol_version": protocol_version,
            "agent_info": {
                "name": "agent-client-router",
                "title": "Agent Client Router",
                "version": "0.1.0",
            },
            "agent_capabilities": {
                "prompt": {
                    "prompt_capabilities": {
                        "text": True,
                    }
                },
                "session": {
                    "config": {},
                    "mode": {},
                },
            },
        }

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[McpServerStdio] | None = None,
        **kwargs,
    ) -> dict:
        """Create a new session, routing to backend agent."""
        session_id = self._generate_session_id()

        self._console.print(f"[dim]Creating session: {session_id}[/dim]")

        return {"session_id": session_id}

    async def load_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[McpServerStdio] | None = None,
        **kwargs,
    ) -> dict:
        """Load an existing session."""
        self._console.print(f"[dim]Loading session: {session_id}[/dim]")
        return {"session_id": session_id}

    async def prompt(self, session_id: str, prompt: list[dict]) -> dict:
        """Route prompt to backend agent."""
        self._console.print(
            f"[dim]Routing prompt to backend session: {session_id}[/dim]"
        )

        # In a real router, you'd forward to the backend agent
        # For demo, we'll just return a simple response
        return {
            "stop_reason": "end_turn",
            "content": [
                {
                    "type": "text",
                    "text": "Hello! This is the router agent. I can route to other agents!",
                }
            ],
        }

    async def cancel(self, session_id: str, **kwargs) -> None:
        """Cancel a session."""
        logger.info(f"Cancelling session: {session_id}")

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return f"router-{uuid.uuid4()}"


async def agent_run():
    """Run the agent."""
    agent = RouterAgent()
    await run_agent(agent)


def main():
    asyncio.run(agent_run())


if __name__ == "__main__":
    main()

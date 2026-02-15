#!/usr/bin/env python
"""
Test script to verify the ACP agent works.

Usage:
    # Terminal 1: Run the agent
    uv run python src/crow/acp_agent.py
    
    # Terminal 2: Run the client
    uv run python src/crow/scripts/test_acp_client.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from acp import (
    PROTOCOL_VERSION,
    Client,
    RequestError,
    connect_to_agent,
    text_block,
)
from acp.schema import (
    AgentMessageChunk,
    ClientCapabilities,
    Implementation,
    TextContentBlock,
)
import asyncio.subprocess as aio_subprocess
import contextlib


class TestClient(Client):
    """Minimal test client"""
    
    async def session_update(self, session_id: str, update: Any, **kwargs) -> None:
        """Handle session updates from agent"""
        if isinstance(update, AgentMessageChunk):
            content = update.content
            if isinstance(content, TextContentBlock):
                print(f"Agent: {content.text}")
    
    async def request_permission(self, *args, **kwargs):
        raise RequestError.method_not_found("session/request_permission")
    
    async def write_text_file(self, *args, **kwargs):
        raise RequestError.method_not_found("fs/write_text_file")
    
    async def read_text_file(self, *args, **kwargs):
        raise RequestError.method_not_found("fs/read_text_file")
    
    async def create_terminal(self, *args, **kwargs):
        raise RequestError.method_not_found("terminal/create")
    
    async def terminal_output(self, *args, **kwargs):
        raise RequestError.method_not_found("terminal/output")
    
    async def release_terminal(self, *args, **kwargs):
        raise RequestError.method_not_found("terminal/release")
    
    async def wait_for_terminal_exit(self, *args, **kwargs):
        raise RequestError.method_not_found("terminal/wait_for_exit")
    
    async def kill_terminal(self, *args, **kwargs):
        raise RequestError.method_not_found("terminal/kill")
    
    async def ext_method(self, method: str, params: dict) -> dict:
        raise RequestError.method_not_found(method)
    
    async def ext_notification(self, method: str, params: dict) -> None:
        pass


async def main():
    """Test the ACP agent"""
    print("Starting test client...")
    
    # Spawn agent process
    agent_path = Path(__file__).parent.parent / "acp_agent.py"
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(agent_path),
        stdin=aio_subprocess.PIPE,
        stdout=aio_subprocess.PIPE,
    )
    
    if not proc.stdin or not proc.stdout:
        print("Failed to spawn agent process")
        return 1
    
    print("Agent process started, connecting...")
    
    # Connect to agent
    client = TestClient()
    conn = connect_to_agent(client, proc.stdin, proc.stdout)
    
    # Initialize
    await conn.initialize(
        protocol_version=PROTOCOL_VERSION,
        client_capabilities=ClientCapabilities(),
        client_info=Implementation(
            name="test-client",
            title="Test Client",
            version="0.1.0",
        ),
    )
    print("Connected to agent!")
    
    # Create session
    session = await conn.new_session(
        mcp_servers=[],
        cwd=str(Path.cwd()),
    )
    print(f"Created session: {session.session_id}")
    
    # Send a prompt
    print("\nSending prompt: 'Search for machine learning papers'")
    await conn.prompt(
        session_id=session.session_id,
        prompt=[text_block("Search for machine learning papers with your search tool")],
    )
    
    print("\nPrompt completed!")
    
    # Cleanup
    if proc.returncode is None:
        proc.terminate()
        with contextlib.suppress(ProcessLookupError):
            await proc.wait()
    
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

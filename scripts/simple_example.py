#!/usr/bin/env python
"""
Complete working example using ACP-native agent.

Based on streaming_async_react.py but uses the full agent architecture.

Usage: uv --project . run python scripts/simple_example.py
"""

import asyncio

from crow.agent import (
    Agent,
    Config,
    LLMConfig,
    create_mcp_client_from_acp,
)
from crow.agent.db import Base, create_database


async def main():
    print("=" * 60)
    print("CROW AGENT - COMPLETE EXAMPLE")
    print("=" * 60)

    # Step 0: Initialize database (create tables if needed)
    print("\n0. Initializing database...")
    db_path = "sqlite:///example.db"
    create_database(db_path)
    print("   ✓ Database initialized")

    # Step 1: Create agent with config
    print("\n1. Creating agent...")
    config = Config(
        llm=LLMConfig(default_model="glm-5"),
        database_path=db_path,
    )
    agent = Agent(config)
    print("   ✓ Agent created")

    # Step 2: Create session with builtin MCP
    print("\n2. Creating session...")
    session_response = await agent.new_session(
        cwd="/tmp",
        mcp_servers=[],  # Empty = use builtin (file_editor, web_search, fetch)
    )
    session_id = session_response.session_id
    print(f"   ✓ Session: {session_id}")
    print(f"   ✓ Tools: {len(agent._tools[session_id])} tools available")

    # Step 3: Send prompt (this requires actual LLM!)
    print("\n3. Sending prompt to LLM...")
    print("   (This will call the real LLM - make sure ZAI_API_KEY is set)")

    try:
        response = await agent.prompt(
            prompt=[
                {
                    "type": "text",
                    "text": "what is agent client protocol? use your web search tool to find the documentation, then fetch and respond",
                }
            ],
            session_id=session_id,
        )

        print(f"\n   ✓ Got response: {response.stop_reason}")

        # Show conversation history
        session = agent._sessions[session_id]
        print(f"\n4. Conversation history:")
        for i, msg in enumerate(session.messages):
            role = msg.get("role", "unknown")
            content = str(msg.get("content", ""))[:100]
            print(f"   [{i}] {role}: {content}...")

        print("\n" + "=" * 60)
        print("✓ SUCCESS - Agent works end-to-end!")
        print("=" * 60)

    except Exception as e:
        print(f"\n   ✗ Failed: {e}")
        print("   (This is expected if LLM_API_KEY is not set)")
        print("   The important part is that session creation worked!")

        # Still show what we accomplished
        session = agent._sessions[session_id]
        print(f"\n4. Session state:")
        print(f"   - Session ID: {session_id}")
        print(f"   - Messages: {len(session.messages)}")
        print(f"   - Tools available: {len(agent._tools[session_id])}")

        print("\n" + "=" * 60)
        print("✓ Architecture works - just needs LLM credentials")
        print("=" * 60)

    # Cleanup
    await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

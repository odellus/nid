#!/usr/bin/env python
"""
Example usage of the new clean Agent and Session API.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from crow.agent import (
    Agent,
    Session,
    create_database,
    configure_llm,
    setup_mcp_client,
    get_tools,
)


async def main():
    """Main example function"""
    
    # Initialize database
    create_database()
    
    # Setup LLM and MCP
    llm = configure_llm(debug=False)
    mcp_client = setup_mcp_client("src/crow/mcp/search.py")
    
    async with mcp_client:
        # Get tools
        tools = await get_tools(mcp_client)
        
        # Create session with prompt template
        session = Session.create(
            prompt_id="crow-v1",
            prompt_args={"workspace": "/home/user/project"},
            tool_definitions=tools,
            request_params={"temperature": 0.7},
            model_identifier="glm-4.7",
        )
        
        print(f"Session ID: {session.session_id}")
        
        # Add user message
        session.add_message("user", "Search for machine learning papers")
        
        # Create agent
        agent = Agent(
            session=session,
            llm=llm,
            mcp_client=mcp_client,
            tools=tools,
            model="glm-4.7",
        )
        
        # Run react loop
        async for chunk in agent.react_loop():
            if chunk["type"] == "content":
                print(chunk["token"], end="", flush=True)
            elif chunk["type"] == "thinking":
                print(f"\n[Thinking]: {chunk['token']}", end="", flush=True)
            elif chunk["type"] == "tool_call":
                name, first_arg = chunk["token"]
                print(f"\n[Tool Call]: {name}({first_arg}", end="", flush=True)
            elif chunk["type"] == "tool_args":
                print(chunk["token"], end="", flush=True)
            elif chunk["type"] == "final_history":
                print("\n\n=== Final History ===")
                for msg in chunk["messages"]:
                    print(f"{msg['role']}: {msg.get('content', msg)[:100]}...")


if __name__ == "__main__":
    asyncio.run(main())

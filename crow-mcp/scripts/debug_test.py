#!/usr/bin/env python3
"""Quick debug test to see PS1 output with logging."""

import asyncio
import os
from fastmcp import Client

CROW_MCP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

config = {
    "mcpServers": {
        "crow_mcp": {
            "transport": "stdio",
            "command": "uv",
            "args": ["--project", CROW_MCP_DIR, "run", "crow-mcp"],
            "cwd": CROW_MCP_DIR,
        }
    }
}

async def test():
    client = Client(config)
    
    print("=" * 60)
    print("DEBUG TEST - Check logs after running")
    print("=" * 60)
    print("Log files will be in: ~/.cache/crow-mcp/logs/")
    print()
    
    async with client:
        # Simple command with SHORT timeout (5s instead of 30s)
        print("Test 1: Simple echo (5s timeout)...")
        result = await client.call_tool("terminal", {
            "command": "echo test",
            "timeout": 5.0
        })
        print(result.content[0].text)
        print()
        
        # Another command
        print("Test 2: pwd...")
        result = await client.call_tool("terminal", {
            "command": "pwd",
            "timeout": 5.0
        })
        print(result.content[0].text)
        
    print("\n" + "=" * 60)
    print("Check logs:")
    print("  python scripts/view_logs.py")
    print("  cat ~/.cache/crow-mcp/logs/terminal_*.log | tail -100")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test())

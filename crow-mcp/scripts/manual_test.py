#!/usr/bin/env python3
"""Simple manual test of terminal tool."""

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
    
    print("Connecting to MCP server...")
    async with client:
        print("✅ Connected\n")
        
        # Test 1: Basic command
        print("=" * 60)
        print("TEST 1: Basic command")
        print("=" * 60)
        result = await client.call_tool("terminal", {"command": "echo 'Hello terminal!'"})
        print(result.content[0].text)
        
        # Test 2: Directory persistence
        print("\n" + "=" * 60)
        print("TEST 2: CD persistence")
        print("=" * 60)
        result1 = await client.call_tool("terminal", {"command": "pwd"})
        print(f"Before: {result1.content[0].text}")
        
        result2 = await client.call_tool("terminal", {"command": "cd /tmp"})
        print(f"CD: {result2.content[0].text}")
        
        result3 = await client.call_tool("terminal", {"command": "pwd"})
        print(f"After: {result3.content[0].text}")
        
        # Test 3: Env var persistence
        print("\n" + "=" * 60)
        print("TEST 3: Environment variable persistence")
        print("=" * 60)
        await client.call_tool("terminal", {"command": "export MY_TEST_VAR=persistence_works"})
        result = await client.call_tool("terminal", {"command": "echo $MY_TEST_VAR"})
        print(result.content[0].text)
        
        # Test 4: Venv persistence
        print("\n" + "=" * 60)
        print("TEST 4: Virtual environment persistence")
        print("=" * 60)
        
        # First deactivate any existing venv
        await client.call_tool("terminal", {"command": "deactivate 2>/dev/null || true"})
        
        # Check starting python (should be system python)
        result1 = await client.call_tool("terminal", {"command": "which python"})
        print(f"Before venv (system python):\n{result1.content[0].text}\n")
        
        # CD back to project dir and activate venv
        venv_path = os.path.join(CROW_MCP_DIR, ".venv", "bin", "activate")
        
        if os.path.exists(venv_path):
            result_cd = await client.call_tool("terminal", {"command": f"cd {CROW_MCP_DIR}"})
            print(f"CD to project dir:\n{result_cd.content[0].text}\n")
            
            # Activate venv
            result2 = await client.call_tool("terminal", {"command": "source .venv/bin/activate"})
            print(f"Activate venv:\n{result2.content[0].text}\n")
            
            # Check python again (should now be venv python)
            result3 = await client.call_tool("terminal", {"command": "which python"})
            print(f"After venv (venv python):\n{result3.content[0].text}\n")
            
            # Verify persistence with another command
            result4 = await client.call_tool("terminal", {"command": "python --version"})
            print(f"Python version from venv:\n{result4.content[0].text}\n")
        else:
            print("No .venv found, skipping venv test\n")
        
        print("\n" + "=" * 60)
        print("✅ ALL MANUAL TESTS PASSED!")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test())

#!/usr/bin/env python3
"""Test terminal persistence MCP tool."""

import asyncio
import os
from fastmcp import Client

# Get the crow-mcp directory (parent of scripts/)
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

client = Client(config)


async def test_basic_command():
    """Test basic command execution."""
    print("=" * 60)
    print("TEST 1: Basic Command")
    print("=" * 60)
    
    async with client:
        result = await client.call_tool("terminal", {"command": "echo 'Hello from terminal!'"})
        print(f"Result:\n{result.content[0].text}\n")


async def test_pwd_persistence():
    """Test that cd persists across calls."""
    print("=" * 60)
    print("TEST 2: Working Directory Persistence")
    print("=" * 60)
    
    async with client:
        # Get current directory
        result1 = await client.call_tool("terminal", {"command": "pwd"})
        print(f"Before cd:\n{result1.content[0].text}\n")
        
        # Change directory
        result2 = await client.call_tool("terminal", {"command": "cd /tmp"})
        print(f"cd /tmp:\n{result2.content[0].text}\n")
        
        # Check current directory again
        result3 = await client.call_tool("terminal", {"command": "pwd"})
        print(f"After cd:\n{result3.content[0].text}\n")
        
        # Verify it changed
        assert "/tmp" in result3.content[0].text, "pwd should show /tmp after cd"


async def test_env_persistence():
    """Test that environment variables persist."""
    print("=" * 60)
    print("TEST 3: Environment Variable Persistence")
    print("=" * 60)
    
    async with client:
        # Set environment variable
        result1 = await client.call_tool("terminal", {"command": "export TEST_VAR='hello persistence!'"})
        print(f"Set env var:\n{result1.content[0].text}\n")
        
        # Read it back
        result2 = await client.call_tool("terminal", {"command": "echo $TEST_VAR"})
        print(f"Read env var:\n{result2.content[0].text}\n")
        
        # Verify it persists
        assert "hello persistence!" in result2.content[0].text, "env var should persist"


async def test_venv_persistence():
    """Test that virtual environment activation persists."""
    print("=" * 60)
    print("TEST 4: Virtual Environment Persistence")
    print("=" * 60)
    
    async with client:
        # Check starting python
        result1 = await client.call_tool("terminal", {"command": "which python"})
        print(f"Before venv:\n{result1.content[0].text}\n")
        
        # Activate venv (if it exists)
        venv_path = os.path.join(CROW_MCP_DIR, ".venv", "bin", "activate")
        
        if os.path.exists(venv_path):
            result2 = await client.call_tool("terminal", {"command": "source .venv/bin/activate"})
            print(f"Activate venv:\n{result2.content[0].text}\n")
            
            # Check python again
            result3 = await client.call_tool("terminal", {"command": "which python"})
            print(f"After venv:\n{result3.content[0].text}\n")
            
            # Verify it changed
            assert ".venv/bin/python" in result3.content[0].text, "python should be in venv after activation"
        else:
            print("No .venv found, skipping venv test\n")


async def test_reset():
    """Test terminal reset."""
    print("=" * 60)
    print("TEST 5: Terminal Reset")
    print("=" * 60)
    
    async with client:
        # Set environment variable
        result1 = await client.call_tool("terminal", {"command": "export RESET_TEST='should disappear'"})
        print(f"Set env var:\n{result1.content[0].text}\n")
        
        # Reset terminal
        result2 = await client.call_tool("terminal", {"command": "", "reset": True})
        print(f"Reset:\n{result2.content[0].text}\n")
        
        # Check if env var is gone
        result3 = await client.call_tool("terminal", {"command": "echo $RESET_TEST"})
        print(f"After reset:\n{result3.content[0].text}\n")
        
        # Verify it's gone (empty or doesn't contain the value)
        assert "should disappear" not in result3.content[0].text, "env var should be gone after reset"


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("CROW TERMINAL MCP TOOL - PERSISTENCE TESTS")
    print("=" * 60 + "\n")
    
    try:
        await test_basic_command()
        await test_pwd_persistence()
        await test_env_persistence()
        await test_venv_persistence()
        await test_reset()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        raise


if __name__ == "__main__":
    asyncio.run(main())

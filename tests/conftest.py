"""
Shared pytest fixtures and configuration for all tests.

This file provides:
- Async test support via pytest-asyncio
- Database fixtures for isolated testing
- Mock MCP client fixtures
- Cleanup verification helpers
"""

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLAlchemySession

from nid.agent import create_database
from nid.agent.db import Base, Prompt, Session as SessionModel


# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f"sqlite:///{f.name}"
    
    # Create tables
    engine = create_engine(db_path)
    Base.metadata.create_all(engine)
    
    yield db_path
    
    # Cleanup
    engine.dispose()
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
async def db_session(temp_db) -> AsyncGenerator[SQLAlchemySession, None]:
    """Provide a database session for testing."""
    engine = create_engine(temp_db)
    session = SQLAlchemySession(engine)
    
    yield session
    
    session.close()
    engine.dispose()


@pytest.fixture
async def seeded_db(temp_db) -> AsyncGenerator[str, None]:
    """Provide a database with test prompts seeded."""
    engine = create_engine(temp_db)
    session = SQLAlchemySession(engine)
    
    # Add test prompts
    test_prompt = Prompt(
        id="test-prompt-v1",
        name="Test Prompt",
        template="You are a test agent. Workspace: {{workspace}}",
    )
    session.add(test_prompt)
    session.commit()
    
    session.close()
    engine.dispose()
    
    yield temp_db


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP client with proper async context manager protocol."""
    
    class MockMCPClient:
        def __init__(self):
            self.entered = False
            self.exited = False
            self.tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "test_tool",
                        "description": "A test tool",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ]
        
        async def __aenter__(self):
            self.entered = True
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            self.exited = True
            return False  # Don't suppress exceptions
        
        async def list_tools(self):
            """Mock list_tools returning test tools."""
            from types import SimpleNamespace
            return [
                SimpleNamespace(
                    name="test_tool",
                    description="A test tool",
                    inputSchema={"type": "object", "properties": {}},
                )
            ]
        
        async def call_tool(self, name, args):
            """Mock call_tool returning test result."""
            from types import SimpleNamespace
            from mcp.types import TextContent
            return SimpleNamespace(
                content=[TextContent(type="text", text="Tool executed successfully")]
            )
    
    return MockMCPClient()


@pytest.fixture
def cleanup_tracker():
    """Track cleanup calls for verification in tests."""
    
    class CleanupTracker:
        def __init__(self):
            self.cleanup_called = False
            self.cleanup_exception = None
        
        async def cleanup(self, exc_type=None, exc_val=None, exc_tb=None):
            """Mark cleanup as called."""
            self.cleanup_called = True
            self.cleanup_exception = exc_val
    
    return CleanupTracker()


@pytest.fixture
async def temp_workspace():
    """Create a temporary workspace directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

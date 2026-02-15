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

from crow.agent import create_database
from crow.agent.db import Base, Prompt, Session as SessionModel


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
def mock_async_context():
    """
    Simple async context manager for UNIT tests of lifecycle patterns.
    
    Used by test_mcp_lifecycle.py and test_session_lifecycle.py to test
    AsyncExitStack behavior without needing a real MCP server.
    
    NOT for E2E tests - E2E tests use real FastMCP Client.
    """
    
    class MockAsyncContextManager:
        def __init__(self):
            self.entered = False
            self.exited = False
        
        async def __aenter__(self):
            self.entered = True
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            self.exited = True
            return False  # Don't suppress exceptions
        
        async def list_tools(self):
            """Minimal interface for tests that check tool access."""
            from types import SimpleNamespace
            return [SimpleNamespace(name="test_tool", description="test", inputSchema={})]
        
        async def call_tool(self, name, args):
            """Minimal interface for tests that check tool calling."""
            from types import SimpleNamespace
            from mcp.types import TextContent
            return SimpleNamespace(
                content=[TextContent(type="text", text="Mock result")]
            )
    
    return MockAsyncContextManager()


@pytest.fixture
def mock_mcp_client(mock_async_context):
    """Alias for backward compatibility with existing tests."""
    return mock_async_context


@pytest.fixture
async def temp_workspace():
    """Create a temporary workspace directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

"""
Crow Agent - Clean agent implementation with session management.
"""

# Import the merged ACP-native agent
from .acp_native import Agent

# Also import from current module for backward compatibility
from .agent import Agent
from .session import Session, lookup_or_create_prompt
from .db import Base, Session as SessionModel, Event, Prompt, create_database
from .prompt import render_template
from .llm import configure_llm
from .mcp_client import setup_mcp_client, get_tools

__all__ = [
    "Agent",  # Export merged agent
    "Agent",  # Deprecated - will be removed
    "Session",
    "lookup_or_create_prompt",
    "Base",
    "SessionModel",
    "Event",
    "Prompt",
    "create_database",
    "render_template",
    "configure_llm",
    "setup_mcp_client",
    "get_tools",
]

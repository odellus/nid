"""
Crow Agent - Clean agent implementation with session management.
"""

# Import the merged ACP-native agent (the only agent we export)
from .acp_native import Agent

from .session import Session, lookup_or_create_prompt
from .db import Base, Session as SessionModel, Event, Prompt, create_database
from .prompt import render_template
from .llm import configure_llm
from .mcp_client import (
    setup_mcp_client,
    get_tools,
    create_mcp_client_from_acp,
    create_mcp_client_from_config,
)
from .config import Config, LLMConfig, get_default_config, get_config_dir

__all__ = [
    "Agent",
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
    "create_mcp_client_from_acp",
    "create_mcp_client_from_config",
    "Config",
    "LLMConfig",
    "get_default_config",
    "get_config_dir",
]

"""
Configuration settings for Crow Agent.

Simple configuration with sensible defaults:
- LLM config (api key, base url, model)
- MCP servers (default: builtin file_editor, web_search, fetch)
- Persistence (database path: ~/.crow/crow.db)
- Runtime (max steps, retries)
"""

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr

load_dotenv()


def get_config_dir() -> Path:
    """Get the configuration directory path (~/.crow)."""
    config_dir = Path.home() / ".crow"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_default_mcp_config() -> dict[str, Any]:
    """The default location of the crow-mcp-server is in the current working directory where"""
    config_dir = get_config_dir()
    with open(config_dir / "mcp.json", "r") as f:
        return json.load(f)


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    api_key: SecretStr | None = Field(
        default=None, description="API key for LLM provider"
    )
    base_url: str | None = Field(default=None, description="Base URL for LLM API")
    default_model: str = Field(default="glm-5", description="Default model to use")


class Config(BaseModel):
    """Configuration for Crow Agent."""

    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM configuration")
    database_path: str = Field(
        default="sqlite:///~/.crow/crow.db", description="Database connection string"
    )
    max_steps_per_turn: int = Field(
        default=100, ge=1, description="Max agent steps per turn"
    )
    max_retries_per_step: int = Field(
        default=3, ge=1, description="Max retries per step"
    )

    # Default MCP servers for coding agent
    mcp_servers: dict[str, Any] = Field(
        default_factory=dict,
        description="MCP servers config (default: builtin server with file_editor, web_search, fetch)",
    )

    def get_builtin_mcp_config(self) -> dict[str, Any]:
        """Get the default MCP server configuration."""
        # If mcp_servers is empty, load from file
        if not self.mcp_servers:
            return get_default_mcp_config()
        return self.mcp_servers


def get_default_config() -> Config:
    """Get default configuration from environment variables."""
    # Ensure ~/.crow directory exists
    db_path = f"sqlite:///{get_config_dir() / 'crow.db'}"

    return Config(
        llm=LLMConfig(
            api_key=os.getenv("ZAI_API_KEY"),
            base_url=os.getenv("ZAI_BASE_URL"),
            default_model=os.getenv("DEFAULT_MODEL", "glm-5"),
        ),
        database_path=os.getenv("DATABASE_PATH", db_path),
        # MCP servers passed via ACP at runtime, or use empty dict for builtin
        mcp_servers=get_default_mcp_config(),
    )

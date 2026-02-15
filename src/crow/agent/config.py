"""
Configuration settings for Crow Agent.

Simple configuration - MCP servers are passed by the ACP client at runtime.
Config is for LLM keys, database path, and agent settings.
"""

import os
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr
from dotenv import load_dotenv

load_dotenv()


def get_config_dir() -> Path:
    """Get the configuration directory path (~/.crow)."""
    config_dir = Path.home() / ".crow"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


class LLMConfig(BaseModel):
    """LLM provider configuration."""
    
    api_key: SecretStr | None = Field(default=None, description="API key for LLM provider")
    base_url: str | None = Field(default=None, description="Base URL for LLM API")
    default_model: str = Field(default="glm-5", description="Default model to use")


class Config(BaseModel):
    """Configuration for Crow Agent."""
    
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM configuration")
    database_path: str = Field(
        default="sqlite:///mcp_testing.db",
        description="Database connection string"
    )
    max_steps_per_turn: int = Field(default=100, ge=1, description="Max agent steps per turn")
    max_retries_per_step: int = Field(default=3, ge=1, description="Max retries per step")


def get_default_config() -> Config:
    """Get default configuration from environment variables."""
    return Config(
        llm=LLMConfig(
            api_key=os.getenv("ZAI_API_KEY"),
            base_url=os.getenv("ZAI_BASE_URL"),
            default_model=os.getenv("DEFAULT_MODEL", "glm-5"),
        ),
        database_path=os.getenv("DATABASE_PATH", "sqlite:///mcp_testing.db"),
    )

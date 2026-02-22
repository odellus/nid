import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def get_config_dir() -> Path:
    """Get the configuration directory path (~/.crow)."""
    config_dir = Path.home() / ".crow"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_default_mcp_config(use_local: bool = True) -> dict[str, Any]:
    """Load default MCP server config, falling back to empty dict if missing."""
    config_dir = get_config_dir()
    mcp_file = config_dir / "mcp.json"

    if not mcp_file.exists():
        return {}

    with open(mcp_file, "r") as f:
        mcp_config = json.load(f)

    # Added safety check using .get() to prevent KeyErrors
    if use_local and "crow-mcp" in mcp_config.get("mcpServers", {}):
        path = Path(os.path.abspath(__file__))
        local_path = path.parent.parent.parent.parent / "crow-mcp"
        mcp_config["mcpServers"]["crow-mcp"]["args"][1] = str(local_path)

    return mcp_config


@dataclass
class LLMProvider:
    """LLM provider configuration."""

    # repr=False hides the key from logs, acting like Pydantic's SecretStr
    api_key: str | None = field(default=None, repr=False)
    base_url: str | None = None
    default_model: str = "glm-5"


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    providers: list[LLMProvider] = field(default_factory=list)


@dataclass
class Config:
    """Configuration for Crow Agent."""

    # Instance variables
    config_dir: Path = field(default_factory=get_config_dir)
    llm: LLMConfig = field(default_factory=LLMConfig)

    database_path: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_PATH", f"sqlite:///{get_config_dir() / 'crow.db'}"
        )
    )

    max_steps_per_turn: int = 100
    max_retries_per_step: int = 3
    mcp_servers: dict[str, Any] = field(default_factory=get_default_mcp_config)

    # Constants (Class variables)
    TERMINAL_TOOL: str = field(default="crow-mcp_terminal", init=False)
    WRITE_TOOL: str = field(default="crow-mcp_write", init=False)
    READ_TOOL: str = field(default="crow-mcp_read", init=False)
    EDIT_TOOL: str = field(default="crow-mcp_edit", init=False)
    SEARCH_TOOL: str = field(default="crow-mcp_web_search", init=False)
    FETCH_TOOL: str = field(default="crow-mcp_web_fetch", init=False)

    def get_builtin_mcp_config(self) -> dict[str, Any]:
        """Get the default MCP server configuration."""
        if not self.mcp_servers:
            return get_default_mcp_config()
        return self.mcp_servers


def get_default_config() -> Config:
    """Get default configuration from environment variables."""
    return Config(
        llm=LLMConfig(
            providers=[
                LLMProvider(
                    api_key=os.getenv("ZAI_API_KEY"), base_url=os.getenv("ZAI_BASE_URL")
                )
            ],
        )
    )


settings = get_default_config()

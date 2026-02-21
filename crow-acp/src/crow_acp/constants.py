import os
from pathlib import Path

HOME = Path(os.getenv("HOME", "~"))
LOG_DIR = HOME / ".crow"
LOG_PATH = LOG_DIR / "crow-acp.log"

TERMINAL_TOOL = "crow-mcp_terminal"
WRITE_TOOL = "crow-mcp_write"
READ_TOOL = "crow-mcp_read"
EDIT_TOOL = "crow-mcp_edit"
SEARCH_TOOL = "crow-mcp_web_search"
FETCH_TOOL = "crow-mcp_web_fetch"

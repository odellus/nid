from contextvars import ContextVar
from typing import Any

from acp.helpers import (
    start_edit_tool_call,
    start_read_tool_call,
    text_block,
    tool_content,
    update_tool_call,
)
from acp.interfaces import Client

from crow_acp.logger import logger


def get_tool_kind(tool_name: str) -> str:
    """Map tool names to ACP ToolKind."""
    # Common MCP tool patterns
    if tool_name in ("read_file", "read", "view", "list_directory", "list"):
        return "read"
    elif tool_name in ("write_file", "write", "edit", "create", "str_replace"):
        return "edit"
    elif tool_name in ("delete", "remove"):
        return "delete"
    elif tool_name in ("move", "rename"):
        return "move"
    elif tool_name in ("search", "grep", "find"):
        return "search"
    elif tool_name in ("terminal", "bash", "shell", "execute"):
        return "execute"
    else:
        return "other"


async def execute_acp_read(
    conn: Client,
    session_id: str,
    tool_call_id: str,
    args: dict[str, Any],
    _current_turn_id: ContextVar[str | None],
) -> str:
    """
    Read file via ACP client filesystem.

    Args:
        session_id: ACP session ID
        tool_call_id: LLM tool call ID
        args: Tool arguments from LLM (file_path, offset, limit)

    Returns:
        File contents with line numbers
    """
    path = args.get("file_path", "")
    offset = args.get("offset")  # 1-indexed
    limit = args.get("limit", 2000)

    # Build ACP tool call ID from turn_id + llm tool call id
    turn_id = _current_turn_id.get()
    acp_tool_call_id = f"{turn_id}/{tool_call_id}" if turn_id else tool_call_id

    try:
        # 1. Send tool call start
        title = f"read: {path}"
        await conn.session_update(
            session_id=session_id,
            update=start_read_tool_call(
                tool_call_id=acp_tool_call_id,
                title=title,
                path=path,
            ),
        )

        # 2. Send in_progress update
        await conn.session_update(
            session_id=session_id,
            update=update_tool_call(acp_tool_call_id, status="in_progress"),
        )

        # 3. Read file via ACP client
        logger.info(f"Reading file via ACP: {path}")
        response = await conn.read_text_file(
            session_id=session_id,
            path=path,
            line=offset,
            limit=limit,
        )
        content = response.content or ""

        # 4. Send completion update with file content
        await conn.session_update(
            session_id=session_id,
            update=update_tool_call(
                acp_tool_call_id,
                status="completed",
                content=[tool_content(text_block(content))],
            ),
        )
        return content
    except Exception as e:
        logger.error(f"Error reading file via ACP: {e}", exc_info=True)
        # Send failed status
        await self._conn.session_update(
            session_id=session_id,
            update=update_tool_call(acp_tool_call_id, status="failed"),
        )
        return f"Error reading file: {str(e)}"

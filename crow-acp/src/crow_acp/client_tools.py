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
from acp.schema import (
    AgentCapabilities,
    AgentMessageChunk,
    AudioContentBlock,
    ClientCapabilities,
    EmbeddedResourceContentBlock,
    HttpMcpServer,
    ImageContentBlock,
    Implementation,
    McpServerStdio,
    ResourceContentBlock,
    SseMcpServer,
    TerminalToolCallContent,
    TextContentBlock,
    ToolCallProgress,
    ToolCallStart,
)
from fastmcp import Client as McpClient

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


async def execute_acp_tool(
    conn: Client,
    current_turn_id: ContextVar[str | None],
    session_id: str,
    tool_call_id: str,
    tool_name: str,
    mcp_clients: dict[str, McpClient],
    args: dict[str, Any],
    kind: str = "other",
) -> str:
    """
    Execute a generic tool via MCP and report with content.

    Used for tools like search, fetch, etc. that return text content
    to display to the user.

    Args:
        session_id: ACP session ID
        tool_call_id: LLM tool call ID
        tool_name: Name of the MCP tool to call
        args: Tool arguments from LLM
        kind: Tool kind for display (search, fetch, other)

    Returns:
        Result string from the tool
    """
    # Build ACP tool call ID from turn_id + llm tool call id
    turn_id = current_turn_id.get()
    acp_tool_call_id = f"{turn_id}/{tool_call_id}" if turn_id else tool_call_id

    try:
        # 1. Send tool call start
        title = f"{tool_name}"
        await conn.session_update(
            session_id=session_id,
            update=ToolCallStart(
                session_update="tool_call",
                tool_call_id=acp_tool_call_id,
                title=title,
                kind=kind,
                status="pending",
            ),
        )

        # 2. Send in_progress update
        await conn.session_update(
            session_id=session_id,
            update=update_tool_call(acp_tool_call_id, status="in_progress"),
        )

        # 3. Execute tool via MCP
        logger.info(f"Executing tool via MCP: {tool_name}")
        mcp_client = mcp_clients.get(session_id)
        if not mcp_client:
            raise RuntimeError(f"No MCP client for session {session_id}")
        result = await mcp_client.call_tool(tool_name, args)
        result_content = result.content[0].text

        # 4. Send completion update with content
        status = "completed" if "Error" not in result_content else "failed"
        await conn.session_update(
            session_id=session_id,
            update=update_tool_call(
                acp_tool_call_id,
                status=status,
                content=[tool_content(text_block(result_content))],
            ),
        )

        return result_content

    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
        await self._conn.session_update(
            session_id=session_id,
            update=update_tool_call(acp_tool_call_id, status="failed"),
        )
        return f"Error: {str(e)}"

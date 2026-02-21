"""Read file tool - reads file contents with line numbering."""

from pathlib import Path

from crow_mcp.server.main import mcp

DEFAULT_LINE_LIMIT = 2000
MAX_LINE_LENGTH = 2000
BINARY_CHECK_SIZE = 8192
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _is_binary_file(path: Path) -> bool:
    """Check if a file appears to be binary."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(BINARY_CHECK_SIZE)
            if not chunk:
                return False
            if b"\x00" in chunk:
                return True
            try:
                text = chunk.decode("utf-8")
                if "\ufffd" in text:
                    return True
                control_chars = sum(1 for c in text if ord(c) < 9 or (13 < ord(c) < 32))
                return control_chars / len(text) > 0.3 if text else False
            except UnicodeDecodeError:
                return True
    except OSError:
        return False


def _format_with_line_numbers(
    content: str, offset: int = 0, limit: int = DEFAULT_LINE_LIMIT
) -> str:
    """Format content with line numbers."""
    lines = content.split("\n")
    total_lines = len(lines)

    start_line = min(offset, len(lines))
    end_line = min(start_line + limit, len(lines))
    selected_lines = lines[start_line:end_line]

    formatted = []
    max_line_num = start_line + len(selected_lines)
    padding = len(str(max_line_num))
    lines_truncated = False

    for idx, line in enumerate(selected_lines):
        line_number = start_line + idx + 1
        if len(line) > MAX_LINE_LENGTH:
            line = line[:MAX_LINE_LENGTH] + "... [line truncated]"
            lines_truncated = True
        formatted.append(f"{line_number:>{padding}}\u2192{line}")

    result = "\n".join(formatted)

    notices = []
    if end_line < total_lines and limit == DEFAULT_LINE_LIMIT:
        notices.append(
            f"\n\n[File truncated: showing lines {start_line + 1}-{end_line} of {total_lines} total. "
            "Use offset and limit parameters to read other sections.]"
        )
    if lines_truncated:
        notices.append(
            f"\n\n[Some lines exceeded {MAX_LINE_LENGTH} characters and were truncated.]"
        )

    return result + "".join(notices)


@mcp.tool
async def read(
    file_path: str,
    offset: int | None = 1,
    limit: int | None = 2000,
) -> str:
    """Reads a file from the local filesystem with line numbers.

    Args:
        file_path: The absolute path to the file to read
        offset: Line number to start reading from (1-indexed, optional)
        limit: Maximum number of lines to read (optional, default 2000)

    Returns:
        File contents with line numbers, or an error message

    Notes:
        - when limit is not specified, it defaults to 2000 lines
        - when offset is not specified, it defaults to 1
        - you should probably check file length with `wc -l /path/to/file` before reading, but if you just give the file path with no args you won't overflow
        - BUT you really do want to use limit and offset pretty much always
        - reading the file twice in a row with the same arguments will return the exact same result
        - do not do with many tool calls what can be accomplished with fewer

    Examples:
        # EACH EXAMPLE IS SELF-CONTAINED.
        # Read in lines 400-427 from file_path
        {
          "tool": "crow-mcp_read",
          "file_path": "/path/to/file",
          "offset": 400,
          "limit": 26
        }

        # EXAMPLE
        # Read in the first 2000 lines of the file path
        {
          "tool": "crow-mcp_read",
          "file_path": "/path/to/file"
        }

        # EXAMPLE
        # Read in the first 2000 lines of the file path
        {
          "tool": "crow-mcp_read",
          "file_path": "/path/to/file"
          "limit": 2000
        }

        # EXAMPLE
        # Read in the first 2000 lines of the file path
        {
            "tool": "crow-mcp_read",
            "file_path": "/path/to/file"
            "limit": 2000,
            "offset": 1
        }

        # EXAMPLE
        # Read in lines 55-1056 lines of the file path
        {
          "tool": "crow-mcp_read",
          "file_path": "/path/to/file",
          "offset": 55,
          "limit": 1001
        }
    """
    path = Path(file_path)

    if offset is None:
        offset = 0
    else:
        offset = max(0, offset - 1)

    if limit is None:
        limit = DEFAULT_LINE_LIMIT

    if not path.exists():
        return f"Error: File does not exist: {path}"

    if not path.is_file():
        return f"Error: Path is a directory, not a file: {path}"

    try:
        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            return f"Error: File too large: {size} bytes (max {MAX_FILE_SIZE} bytes)"
    except OSError as e:
        return f"Error: Cannot stat file: {e}"

    if _is_binary_file(path):
        return f"Error: Cannot read binary file: {path}"

    try:
        content = path.read_text(encoding="utf-8")
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except OSError as e:
        return f"Error: Failed to read file: {e}"

    if not content.strip():
        return f"<system-reminder>\nThe file {path} exists but has empty contents.\n</system-reminder>"

    return _format_with_line_numbers(content, offset, limit)

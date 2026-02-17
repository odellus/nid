"""
Crow Builtin MCP Server

Combines all builtin tools into one MCP server:
- file_editor: View, create, edit files
- web_search: Search the web via SearXNG
- fetch: Fetch and parse web pages

This is the default MCP server for crow agents.
"""

import base64
import hashlib
import json
import logging
import mimetypes
import os
import re
import tempfile
from pathlib import Path
from typing import Literal

import charset_normalizer
from binaryornot.check import is_binary
from cachetools import LRUCache
from pydantic import BaseModel, Field
from crow_mcp.server.main import mcp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Create the combined MCP server
# mcp = FastMCP(name="crow-builtin")


# Constants
MAX_FILE_SIZE_MB = 10
SNIPPET_CONTEXT_LINES = 4
HISTORY_PER_FILE = 10
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

Command = Literal["view", "create", "str_replace", "insert", "undo_edit"]


class EditorError(Exception):
    """Base error for file editor operations."""

    pass


class EncodingManager:
    """Manages file encoding detection and caching."""

    def __init__(self, cache_size: int = 1000):
        self.cache: LRUCache[str, tuple[str, float]] = LRUCache(maxsize=cache_size)
        self.confidence_threshold = 0.9

    def detect(self, path: Path) -> str:
        """Detect file encoding with caching."""
        if not path.exists():
            return "utf-8"

        path_str = str(path)
        current_mtime = os.path.getmtime(path)

        if path_str in self.cache:
            cached_encoding, cached_mtime = self.cache[path_str]
            if cached_mtime == current_mtime:
                return cached_encoding

        sample_size = min(os.path.getsize(path), 1024 * 1024)
        with open(path, "rb") as f:
            raw_data = f.read(sample_size)

        results = charset_normalizer.detect(raw_data)

        if (
            results
            and results.get("confidence", 0) > self.confidence_threshold
            and results.get("encoding")
        ):
            encoding = results["encoding"]
            if encoding.lower() == "ascii":
                encoding = "utf-8"
        else:
            encoding = "utf-8"

        self.cache[path_str] = (encoding, current_mtime)
        return encoding


class HistoryManager:
    """Manages file edit history for undo."""

    def __init__(self, max_per_file: int = HISTORY_PER_FILE):
        self.max_per_file = max_per_file
        self.history_dir = Path(tempfile.mkdtemp(prefix="file_editor_history_"))
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _hash_path(self, path: Path) -> str:
        return hashlib.sha256(str(path).encode()).hexdigest()

    def _metadata_path(self, path_hash: str) -> Path:
        return self.history_dir / f"{path_hash}_metadata.json"

    def _content_path(self, path_hash: str, counter: int) -> Path:
        return self.history_dir / f"{path_hash}_{counter}.txt"

    def add(self, path: Path, content: str) -> None:
        path_hash = self._hash_path(path)
        metadata_file = self._metadata_path(path_hash)

        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
        else:
            metadata = {"entries": [], "counter": 0}

        content_file = self._content_path(path_hash, metadata["counter"])
        with open(content_file, "w", encoding="utf-8") as f:
            f.write(content)

        metadata["entries"].append(metadata["counter"])
        metadata["counter"] += 1

        while len(metadata["entries"]) > self.max_per_file:
            old_counter = metadata["entries"].pop(0)
            old_file = self._content_path(path_hash, old_counter)
            if old_file.exists():
                old_file.unlink()

        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

    def pop(self, path: Path) -> str | None:
        path_hash = self._hash_path(path)
        metadata_file = self._metadata_path(path_hash)

        if not metadata_file.exists():
            return None

        with open(metadata_file) as f:
            metadata = json.load(f)

        if not metadata["entries"]:
            return None

        last_counter = metadata["entries"].pop()
        content_file = self._content_path(path_hash, last_counter)

        if not content_file.exists():
            return None

        with open(content_file, encoding="utf-8") as f:
            content = f.read()

        content_file.unlink()
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

        return content


class FileEditor:
    """Core file editor logic."""

    def __init__(self, workspace_root: str | None = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.encoding_manager = EncodingManager()
        self.history_manager = HistoryManager()
        self.max_file_size = MAX_FILE_SIZE_MB * 1024 * 1024

    def validate_path(self, command: Command, path: Path) -> None:
        if not path.is_absolute():
            suggestion = f"The path should be absolute, starting with `/`."
            suggested = self.workspace_root / path
            if suggested.exists():
                suggestion += f" Maybe you meant {suggested}?"
            raise EditorError(suggestion)

        if command == "create" and path.exists():
            raise EditorError(f"File already exists at: {path}.")

        if command != "create" and not path.exists():
            raise EditorError(f"The path {path} does not exist.")

        if command != "view" and path.is_dir():
            raise EditorError(
                f"The path {path} is a directory. Only `view` works on directories."
            )

    def validate_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            return

        file_size = os.path.getsize(path)
        if file_size > self.max_file_size:
            raise EditorError(
                f"File is too large ({file_size / 1024 / 1024:.1f}MB). Maximum is {MAX_FILE_SIZE_MB}MB."
            )

        file_ext = path.suffix.lower()
        if is_binary(str(path)) and file_ext not in IMAGE_EXTENSIONS:
            raise EditorError("File appears to be binary and cannot be edited.")

    def read_file(
        self, path: Path, start_line: int | None = None, end_line: int | None = None
    ) -> str:
        self.validate_file(path)
        encoding = self.encoding_manager.detect(path)

        if start_line is not None and end_line is not None:
            lines = []
            with open(path, encoding=encoding) as f:
                for i, line in enumerate(f, 1):
                    if i > end_line:
                        break
                    if i >= start_line:
                        lines.append(line)
            return "".join(lines)
        else:
            with open(path, encoding=encoding) as f:
                return f.read()

    def write_file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoding = self.encoding_manager.detect(path)
        with open(path, "w", encoding=encoding) as f:
            f.write(content)

    def format_output(self, content: str, path: str, start_line: int = 1) -> str:
        lines = content.split("\n")
        formatted = [f"{path}:"]
        for i, line in enumerate(lines, start_line):
            formatted.append(f"{i:6}\t{line}")
        return "\n".join(formatted) + "\n"

    def view_directory(self, path: Path) -> str:
        items = []
        for item in sorted(
            path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())
        ):
            if item.is_dir():
                items.append(f"{item.name}/")
            else:
                size = item.stat().st_size
                items.append(f"{item.name} ({size} bytes)")
        return "\n".join(items) + "\n"

    def view_image(self, path: Path) -> str:
        mime_type, _ = mimetypes.guess_type(str(path))
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "application/octet-stream"
        with open(path, "rb") as f:
            image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode("utf-8")
        image_url = f"data:{mime_type};base64,{image_base64}"
        return f"Image file {path}:\n{image_url}\n"

    def view(self, path: Path, view_range: list[int] | None = None) -> str:
        self.validate_path("view", path)

        if path.is_dir():
            return self.view_directory(path)

        if path.suffix.lower() in IMAGE_EXTENSIONS:
            return self.view_image(path)

        self.validate_file(path)
        encoding = self.encoding_manager.detect(path)
        with open(path, encoding=encoding) as f:
            num_lines = sum(1 for _ in f)

        if not view_range:
            content = self.read_file(path)
            return self.format_output(content, str(path))

        if len(view_range) != 2:
            raise EditorError("view_range must be [start, end]")

        start, end = view_range
        if start < 1 or start > num_lines:
            raise EditorError(f"start_line {start} must be in range [1, {num_lines}]")

        if end == -1:
            end = num_lines
        elif end > num_lines:
            end = num_lines

        if end < start:
            raise EditorError(f"end_line {end} must be >= start_line {start}")

        content = self.read_file(path, start, end)
        return self.format_output(content, str(path), start)

    def create(self, path: Path, content: str) -> str:
        if path.exists():
            raise EditorError(f"File already exists: {path}")

        self.write_file(path, content)
        self.history_manager.add(path, content)
        return f"File created successfully at: {path}\n"

    def str_replace(self, path: Path, old_str: str, new_str: str) -> str:
        if old_str == new_str:
            raise EditorError("old_str and new_str must be different")

        content = self.read_file(path)
        pattern = re.escape(old_str)
        matches = list(re.finditer(pattern, content))

        if not matches:
            old_str = old_str.strip()
            new_str = new_str.strip()
            pattern = re.escape(old_str)
            matches = list(re.finditer(pattern, content))
            if not matches:
                raise EditorError(f"String not found: `{old_str[:50]}...`")

        if len(matches) > 1:
            line_numbers = [content.count("\n", 0, m.start()) + 1 for m in matches]
            raise EditorError(
                f"Multiple matches found at lines {sorted(set(line_numbers))}. "
                "Include more context to make it unique."
            )

        match = matches[0]
        new_content = content[: match.start()] + new_str + content[match.end() :]

        self.history_manager.add(path, content)
        self.write_file(path, new_content)

        replacement_line = content.count("\n", 0, match.start()) + 1
        start = max(0, replacement_line - SNIPPET_CONTEXT_LINES)
        end = replacement_line + SNIPPET_CONTEXT_LINES + new_str.count("\n")

        snippet = self.read_file(path, start + 1, end)
        snippet_output = self.format_output(snippet, f"{path} snippet", start + 1)

        return (
            f"The file {path} has been edited.\n{snippet_output}\nReview the changes.\n"
        )

    def insert(self, path: Path, insert_line: int, new_str: str) -> str:
        content = self.read_file(path)
        lines = content.split("\n")
        num_lines = len(lines)

        if insert_line < 0 or insert_line > num_lines:
            raise EditorError(f"insert_line must be in range [0, {num_lines}]")

        self.history_manager.add(path, content)

        new_lines = new_str.split("\n")
        lines[insert_line:insert_line] = new_lines
        new_content = "\n".join(lines)

        self.write_file(path, new_content)

        start = max(0, insert_line - SNIPPET_CONTEXT_LINES)
        end = min(len(lines), insert_line + len(new_lines) + SNIPPET_CONTEXT_LINES)
        snippet = "\n".join(lines[start:end])
        snippet_output = self.format_output(snippet, f"{path} snippet", start + 1)

        return (
            f"The file {path} has been edited.\n{snippet_output}\nReview the changes.\n"
        )

    def undo_edit(self, path: Path) -> str:
        current = self.read_file(path)
        old = self.history_manager.pop(path)

        if old is None:
            raise EditorError(f"No edit history found for {path}")

        self.write_file(path, old)
        snippet_output = self.format_output(old, str(path))
        return f"Last edit undone for {path}.\n{snippet_output}"


# Global editor instance
_editor: FileEditor | None = None


def get_editor() -> FileEditor:
    global _editor
    if _editor is None:
        _editor = FileEditor()
    return _editor



@mcp.tool
async def file_editor(
    command: Command,
    path: str,
    file_text: str | None = None,
    view_range: list[int] | None = None,
    old_str: str | None = None,
    new_str: str | None = None,
    insert_line: int | None = None,
) -> str:
    """File editor for viewing, creating, and editing files.

    Commands:
    - view: View file or directory (cat -n style)
    - create: Create new file (fails if exists)
    - str_replace: Replace exact string match
    - insert: Insert text after line number
    - undo_edit: Undo last edit

    Args:
        command: str - The command to run (required)
        path: str -  Absolute path to file or directory (required)
        file_text: str - Content for create command
        view_range: list[int] | None - Range of lines to view
        old_str: str - String to replace for str_replace
        new_str: str - New string for str_replace or insert
        insert_line: int - Line number to insert after (0 = beginning)

    Returns:
        Result message with context
    """
    try:
        editor = get_editor()
        file_path = Path(path)
        editor.validate_path(command, file_path)

        if command == "view":
            return editor.view(file_path, view_range)
        elif command == "create":
            if file_text is None:
                raise EditorError("file_text required for create")
            return editor.create(file_path, file_text)
        elif command == "str_replace":
            if old_str is None or new_str is None:
                raise EditorError("old_str and new_str required for str_replace")
            return editor.str_replace(file_path, old_str, new_str)
        elif command == "insert":
            if insert_line is None or new_str is None:
                raise EditorError("insert_line and new_str required for insert")
            return editor.insert(file_path, insert_line, new_str)
        elif command == "undo_edit":
            return editor.undo_edit(file_path)
        else:
            raise EditorError(f"Unknown command: {command}")

    except EditorError as e:
        return f"Error: {e}\n"
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return f"Unexpected error: {e}\n"

"""
File Editor MCP Server

A semantic file manipulation tool for LLMs via MCP protocol.
Implementing from understanding, not copying.

Key concepts:
- Exact string matching (forces precision)
- Encoding preservation (charset_normalizer)
- History for undo (tempfile-based)
- Rich error messages (guides correction)
"""

import base64
import hashlib
import json
import logging
import mimetypes
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Literal

import charset_normalizer
from binaryornot.check import is_binary
from cachetools import LRUCache
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
MAX_FILE_SIZE_MB = 10
MAX_RESPONSE_LEN = 16000
SNIPPET_CONTEXT_LINES = 4
HISTORY_PER_FILE = 10
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

# FastMCP server
mcp = FastMCP(name="file_editor")

# Command type
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

        # Check cache
        if path_str in self.cache:
            cached_encoding, cached_mtime = self.cache[path_str]
            if cached_mtime == current_mtime:
                return cached_encoding

        # Detect encoding
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
            # Always use utf-8 instead of ascii
            if encoding.lower() == "ascii":
                encoding = "utf-8"
        else:
            encoding = "utf-8"

        # Cache result
        self.cache[path_str] = (encoding, current_mtime)
        return encoding


class HistoryManager:
    """Manages file edit history for undo operations."""

    def __init__(self, max_per_file: int = HISTORY_PER_FILE):
        self.max_per_file = max_per_file
        self.history_dir = Path(tempfile.mkdtemp(prefix="file_editor_history_"))
        self.history_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"History directory: {self.history_dir}")

    def _hash_path(self, path: Path) -> str:
        """Create hash key for path."""
        return hashlib.sha256(str(path).encode()).hexdigest()

    def _metadata_path(self, path_hash: str) -> Path:
        """Get metadata file path."""
        return self.history_dir / f"{path_hash}_metadata.json"

    def _content_path(self, path_hash: str, counter: int) -> Path:
        """Get content file path."""
        return self.history_dir / f"{path_hash}_{counter}.txt"

    def add(self, path: Path, content: str) -> None:
        """Add content to history."""
        path_hash = self._hash_path(path)
        metadata_file = self._metadata_path(path_hash)

        # Load or create metadata
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
        else:
            metadata = {"entries": [], "counter": 0}

        # Save content
        content_file = self._content_path(path_hash, metadata["counter"])
        with open(content_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Update metadata
        metadata["entries"].append(metadata["counter"])
        metadata["counter"] += 1

        # Evict old entries if needed
        while len(metadata["entries"]) > self.max_per_file:
            old_counter = metadata["entries"].pop(0)
            old_file = self._content_path(path_hash, old_counter)
            if old_file.exists():
                old_file.unlink()

        # Save metadata
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

    def pop(self, path: Path) -> str | None:
        """Pop last history entry."""
        path_hash = self._hash_path(path)
        metadata_file = self._metadata_path(path_hash)

        if not metadata_file.exists():
            return None

        with open(metadata_file) as f:
            metadata = json.load(f)

        if not metadata["entries"]:
            return None

        # Get last entry
        last_counter = metadata["entries"].pop()
        content_file = self._content_path(path_hash, last_counter)

        if not content_file.exists():
            return None

        # Read content
        with open(content_file, encoding="utf-8") as f:
            content = f.read()

        # Delete content file
        content_file.unlink()

        # Update metadata
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
        logger.info(f"FileEditor initialized with workspace: {self.workspace_root}")

    def validate_path(self, command: Command, path: Path) -> None:
        """Validate path for command."""
        if not path.is_absolute():
            suggestion = f"The path should be absolute, starting with `/`."
            suggested = self.workspace_root / path
            if suggested.exists():
                suggestion += f" Maybe you meant {suggested}?"
            raise EditorError(suggestion)

        if command == "create" and path.exists():
            raise EditorError(
                f"File already exists at: {path}. Cannot overwrite using `create`."
            )

        if command != "create" and not path.exists():
            raise EditorError(f"The path {path} does not exist.")

        if command != "view" and path.is_dir():
            raise EditorError(
                f"The path {path} is a directory. Only `view` works on directories."
            )

    def validate_file(self, path: Path) -> None:
        """Validate file for operations."""
        if not path.exists() or not path.is_file():
            return

        # Check size
        file_size = os.path.getsize(path)
        if file_size > self.max_file_size:
            raise EditorError(
                f"File is too large ({file_size / 1024 / 1024:.1f}MB). "
                f"Maximum allowed is {MAX_FILE_SIZE_MB}MB."
            )

        # Check binary
        file_ext = path.suffix.lower()
        if is_binary(str(path)) and file_ext not in IMAGE_EXTENSIONS:
            raise EditorError("File appears to be binary and cannot be edited.")

    def read_file(
        self, path: Path, start_line: int | None = None, end_line: int | None = None
    ) -> str:
        """Read file with optional line range."""
        self.validate_file(path)
        encoding = self.encoding_manager.detect(path)

        try:
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
        except Exception as e:
            raise EditorError(f"Error reading {path}: {e}")

    def write_file(self, path: Path, content: str) -> None:
        """Write content to file."""
        self.validate_file(path)
        encoding = self.encoding_manager.detect(path) if path.exists() else "utf-8"

        try:
            with open(path, "w", encoding=encoding) as f:
                f.write(content)
        except Exception as e:
            raise EditorError(f"Error writing {path}: {e}")

    def format_output(self, content: str, description: str, start_line: int = 1) -> str:
        """Format output with line numbers."""
        if len(content) > MAX_RESPONSE_LEN:
            content = content[:MAX_RESPONSE_LEN]
            content += f"\n\n<response clipped - file too large, use grep to find specific content>"

        lines = content.split("\n")
        numbered = "\n".join(
            f"{i + start_line:6}\t{line}" for i, line in enumerate(lines)
        )

        return f"Here's the result of running `cat -n` on {description}:\n{numbered}\n"

    def view_directory(self, path: Path) -> str:
        """View directory structure."""
        # Get files up to 2 levels deep
        result = []
        for item in sorted(path.rglob("*")):
            rel = item.relative_to(path)
            if len(rel.parts) > 2:  # Max 2 levels
                continue
            if any(part.startswith(".") for part in rel.parts):  # Skip hidden
                continue

            if item.is_dir():
                result.append(f"{rel}/")
            else:
                result.append(str(rel))

        output = "\n".join(result[:100])  # Limit output
        if len(result) > 100:
            output += f"\n\n... and {len(result) - 100} more items"

        return f"Here's the files and directories up to 2 levels deep in {path}:\n{output}\n"

    def view_image(self, path: Path) -> str:
        """View image as base64."""
        try:
            with open(path, "rb") as f:
                image_bytes = f.read()

            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            mime_type, _ = mimetypes.guess_type(str(path))
            if not mime_type or not mime_type.startswith("image/"):
                mime_type = "image/png"

            image_url = f"data:{mime_type};base64,{image_base64}"
            return f"Image file {path}:\n{image_url}\n"
        except Exception as e:
            raise EditorError(f"Failed to read image {path}: {e}")

    def view(self, path: Path, view_range: list[int] | None = None) -> str:
        """View file or directory."""
        # Validate path first (ensures consistent error messages)
        self.validate_path("view", path)

        if path.is_dir():
            if view_range:
                raise EditorError("view_range not allowed for directories")
            return self.view_directory(path)

        # Check for image
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            return self.view_image(path)

        # Validate and read file
        self.validate_file(path)

        # Count lines
        encoding = self.encoding_manager.detect(path)
        with open(path, encoding=encoding) as f:
            num_lines = sum(1 for _ in f)

        # View full file or range
        if not view_range:
            content = self.read_file(path)
            return self.format_output(content, str(path))

        # Validate view_range
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
        """Create new file."""
        if path.exists():
            raise EditorError(f"File already exists: {path}")

        self.write_file(path, content)
        self.history_manager.add(path, content)

        return f"File created successfully at: {path}\n"

    def str_replace(self, path: Path, old_str: str, new_str: str) -> str:
        """Replace exact string match."""
        if old_str == new_str:
            raise EditorError("old_str and new_str must be different")

        content = self.read_file(path)

        # Find matches
        pattern = re.escape(old_str)
        matches = list(re.finditer(pattern, content))

        if not matches:
            # Try stripping whitespace
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

        # Perform replacement
        match = matches[0]
        new_content = content[: match.start()] + new_str + content[match.end() :]

        # Save to history and write
        self.history_manager.add(path, content)
        self.write_file(path, new_content)

        # Show snippet
        replacement_line = content.count("\n", 0, match.start()) + 1
        start = max(0, replacement_line - SNIPPET_CONTEXT_LINES)
        end = replacement_line + SNIPPET_CONTEXT_LINES + new_str.count("\n")

        snippet = self.read_file(path, start + 1, end)
        snippet_output = self.format_output(snippet, f"{path} snippet", start + 1)

        return f"The file {path} has been edited.\n{snippet_output}\nReview the changes and make sure they are as expected.\n"

    def insert(self, path: Path, insert_line: int, new_str: str) -> str:
        """Insert text after line number."""
        content = self.read_file(path)
        lines = content.split("\n")
        num_lines = len(lines)

        if insert_line < 0 or insert_line > num_lines:
            raise EditorError(f"insert_line must be in range [0, {num_lines}]")

        # Save history
        self.history_manager.add(path, content)

        # Insert
        new_lines = new_str.split("\n")
        lines[insert_line:insert_line] = new_lines
        new_content = "\n".join(lines)

        self.write_file(path, new_content)

        # Show snippet
        start = max(0, insert_line - SNIPPET_CONTEXT_LINES)
        end = min(len(lines), insert_line + len(new_lines) + SNIPPET_CONTEXT_LINES)
        snippet = "\n".join(lines[start:end])
        snippet_output = self.format_output(snippet, f"{path} snippet", start + 1)

        return f"The file {path} has been edited.\n{snippet_output}\nReview the changes and make sure they are as expected.\n"

    def undo_edit(self, path: Path) -> str:
        """Undo last edit."""
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
    """Get or create editor instance."""
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
        command: The command to run
        path: Absolute path to file or directory
        file_text: Content for create command
        view_range: [start, end] line range for view (optional)
        old_str: String to replace for str_replace
        new_str: New string for str_replace or insert
        insert_line: Line number to insert after (0 = beginning)

    Returns:
        Result message with context
    """
    try:
        editor = get_editor()
        file_path = Path(path)

        # Validate path
        editor.validate_path(command, file_path)

        # Execute command
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


if __name__ == "__main__":
    mcp.run(transport="stdio")

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
import shutil
import tempfile
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse, urlunparse

import charset_normalizer
import markdownify
import readabilipy.simple_json
from binaryornot.check import is_binary
from cachetools import LRUCache
from fastmcp import FastMCP
from httpx import AsyncClient
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the combined MCP server
mcp = FastMCP(name="crow-builtin")

# =============================================================================
# FILE EDITOR TOOL
# =============================================================================

# Import the file editor implementation
# We'll inline the core logic here for a self-contained server


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


class SearchResult(BaseModel):
    url: str
    title: str
    content: str


class InfoboxUrl(BaseModel):
    title: str
    url: str


class Infobox(BaseModel):
    infobox: str
    id: str
    content: str
    urls: list[InfoboxUrl]


class SearchResponse(BaseModel):
    query: str
    number_of_results: int
    results: list[SearchResult]
    infoboxes: list[Infobox]


@mcp.tool
async def web_search(query: str, limit: int = 5) -> str:
    """## Search Tool Instructions
    **Search the internet. USE THIS LIBERALLY.**
    If you are:
    - Uncertain about the user's query
    - About to make something up
    - Suspecting the USER is making something up
    - Working with a library/API you haven't seen recently
    - Debugging an error message you don't recognize
    Then SEARCH. Search in parallel (4-5 max). Search before you hallucinate.
    SEARCH INTERNET AS MUCH AS FILESYSTEM! I PITY THE FOOL WHO DON'T USE WEB SEARCH!
    This is not a fallback tool. This is a primary tool. Good developers search the internet constantly. So should you.
    **Tips for better results:**
    - To search a specific website, add the site name to your query (e.g., "python async stackoverflow" or "react hooks site:reactjs.org")
    - To find recent results, add timeframes to your query (e.g., "rust 2024", "next.js news this week")
    - If a snippet looks promising but is cut off, use the fetch tool to pull down the full page
    **Arguments:**
    - `query: str` - Your search query for the search engine
    - `limit: int = 5` - Optional, control the number of results
    **Example use:**
    result: str = search(query="How to make key lime pie")
    """
    searxng_url = os.getenv("SEARXNG_URL", "http://localhost:8082")
    client = AsyncClient(base_url=searxng_url)

    params = {"q": query, "format": "json"}
    response = await client.get("/search", params=params)
    response.raise_for_status()

    data = SearchResponse.model_validate_json(response.text)

    text = []

    for infobox in data.infoboxes:
        text.append(f"Infobox: {infobox.infobox}\n")
        text.append(f"ID: {infobox.id}\n")
        text.append(f"Content: {infobox.content}\n\n")

    if not data.results:
        text.append("No results found\n")

    for i, result in enumerate(data.results):
        text.append(f"Title: {result.title}\n")
        text.append(f"URL: {result.url}\n")
        text.append(f"Content: {result.content}\n\n")
        if i == limit - 1:
            break

    return "".join(text)


DEFAULT_USER_AGENT = "CrowAgent/1.0"


async def fetch_url(url: str, user_agent: str = DEFAULT_USER_AGENT) -> tuple[str, str]:
    """Fetch URL and return (content, prefix)."""
    async with AsyncClient() as client:
        response = await client.get(
            url,
            follow_redirects=True,
            headers={"User-Agent": user_agent},
            timeout=30,
        )
        response.raise_for_status()
        page_raw = response.text

    content_type = response.headers.get("content-type", "")
    is_html = (
        "<html" in page_raw[:100] or "text/html" in content_type or not content_type
    )

    if is_html:
        ret = readabilipy.simple_json.simple_json_from_html_string(
            page_raw, use_readability=True
        )
        if ret.get("content"):
            content = markdownify.markdownify(
                ret["content"], heading_style=markdownify.ATX
            )
            return content, ""
        return "<error>Failed to parse HTML</error>", ""
    else:
        return page_raw, f"Content type: {content_type}\n"


@mcp.tool
async def fetch(
    url: str,
    max_length: int = 5000,
    start_index: int = 0,
    raw: bool = False,
) -> str:
    """Fetch a URL and extract content as markdown.

    Args:
        url: URL to fetch
        max_length: Max characters to return (default 5000)
        start_index: Start at this character (for pagination)
        raw: Get raw HTML instead of markdown

    Returns:
        Page content as markdown (or raw HTML if raw=True)
    """
    try:
        content, prefix = await fetch_url(url)

        if raw:
            # Return raw HTML
            total_len = len(content)
            truncated = content[start_index : start_index + max_length]
            if start_index >= total_len:
                return "<error>No more content available.</error>"
            result = f"{prefix}Raw HTML from {url}:\n{truncated}"
            if len(truncated) == max_length and start_index + max_length < total_len:
                result += f"\n\n<error>Content truncated. Call fetch with start_index={start_index + max_length}</error>"
            return result

        total_len = len(content)
        if start_index >= total_len:
            return "<error>No more content available.</error>"

        truncated = content[start_index : start_index + max_length]
        result = f"{prefix}Contents of {url}:\n{truncated}"

        if len(truncated) == max_length and start_index + max_length < total_len:
            result += f"\n\n<error>Content truncated. Call fetch with start_index={start_index + max_length}</error>"

        return result

    except Exception as e:
        return f"Error fetching {url}: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")

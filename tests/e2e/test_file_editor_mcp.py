"""
E2E tests for file_editor MCP server.

Tests real MCP protocol communication using FastMCP Client.
This validates:
1. The MCP server starts and responds correctly
2. Tool schemas are correct
3. Tool execution works end-to-end

NO MOCKS - real file operations, real MCP protocol.
"""

import tempfile
from pathlib import Path

import pytest
from fastmcp import Client

# Import the MCP server instance directly from the installed package
from crow_mcp_server.main import mcp


class TestFileEditorMCPServer:
    """E2E tests for file_editor MCP server."""
    
    async def test_server_lists_file_editor_tool(self):
        """The server should expose a file_editor tool."""
        async with Client(transport=mcp) as client:
            tools = await client.list_tools()
            tool_names = [t.name for t in tools]
            
            assert "file_editor" in tool_names, f"Available tools: {tool_names}"
    
    async def test_tool_has_correct_schema(self):
        """The file_editor tool should have the expected schema."""
        async with Client(transport=mcp) as client:
            tools = await client.list_tools()
            file_editor = next(t for t in tools if t.name == "file_editor")
            
            # Check required parameters exist
            schema = file_editor.inputSchema
            required = schema.get("required", [])
            properties = schema.get("properties", {})
            
            assert "command" in required, f"Required: {required}"
            assert "path" in required, f"Required: {required}"
            
            # Check command has expected enum values
            command_prop = properties.get("command", {})
            command_enum = command_prop.get("enum", [])
            expected_commands = ["view", "create", "str_replace", "insert", "undo_edit"]
            
            for cmd in expected_commands:
                assert cmd in command_enum, f"Command enum: {command_enum}"
    
    async def test_view_command_reads_file(self):
        """view command should read file content with line numbers."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Line 1\nLine 2\nLine 3\n")
            test_file = Path(f.name)
        
        try:
            async with Client(transport=mcp) as client:
                result = await client.call_tool(
                    name="file_editor",
                    arguments={
                        "command": "view",
                        "path": str(test_file),
                    }
                )
                
                # Result is a list of content blocks
                text = result.content[0].text
                
                assert "Line 1" in text
                assert "Line 2" in text
                assert "Line 3" in text
                # Should have line numbers (cat -n style)
                assert "1\t" in text or "     1\t" in text
        finally:
            test_file.unlink()
    
    async def test_view_command_with_range(self):
        """view command with view_range should read only specified lines."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")
            test_file = Path(f.name)
        
        try:
            async with Client(transport=mcp) as client:
                result = await client.call_tool(
                    name="file_editor",
                    arguments={
                        "command": "view",
                        "path": str(test_file),
                        "view_range": [2, 3],
                    }
                )
                
                text = result.content[0].text
                
                assert "Line 1" not in text
                assert "Line 2" in text
                assert "Line 3" in text
                assert "Line 4" not in text
                assert "Line 5" not in text
        finally:
            test_file.unlink()
    
    async def test_view_directory_lists_contents(self):
        """view on directory should list files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "file1.txt").write_text("content1")
            (tmpdir_path / "file2.txt").write_text("content2")
            (tmpdir_path / "subdir").mkdir()
            
            async with Client(transport=mcp) as client:
                result = await client.call_tool(
                    name="file_editor",
                    arguments={
                        "command": "view",
                        "path": str(tmpdir_path),
                    }
                )
                
                text = result.content[0].text
                
                assert "file1.txt" in text
                assert "file2.txt" in text
                assert "subdir" in text
    
    async def test_create_command_creates_file(self):
        """create command should create new file with content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_file = Path(tmpdir) / "new_file.txt"
            content = "Hello\nWorld\n"
            
            async with Client(transport=mcp) as client:
                result = await client.call_tool(
                    name="file_editor",
                    arguments={
                        "command": "create",
                        "path": str(new_file),
                        "file_text": content,
                    }
                )
                
                text = result.content[0].text
                
                assert new_file.exists()
                assert new_file.read_text() == content
                assert "created successfully" in text.lower()
    
    async def test_create_existing_file_fails(self):
        """create on existing file should fail with error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("existing content")
            test_file = Path(f.name)
        
        try:
            async with Client(transport=mcp) as client:
                result = await client.call_tool(
                    name="file_editor",
                    arguments={
                        "command": "create",
                        "path": str(test_file),
                        "file_text": "new content",
                    }
                )
                
                text = result.content[0].text
                
                assert "error" in text.lower()
                assert "already exists" in text.lower()
        finally:
            test_file.unlink()
    
    async def test_str_replace_unique_match(self):
        """str_replace should replace unique exact match."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Line 1\nLine 2\nLine 3\n")
            test_file = Path(f.name)
        
        try:
            async with Client(transport=mcp) as client:
                result = await client.call_tool(
                    name="file_editor",
                    arguments={
                        "command": "str_replace",
                        "path": str(test_file),
                        "old_str": "Line 2",
                        "new_str": "Modified Line 2",
                    }
                )
                
                text = result.content[0].text
                content = test_file.read_text()
                
                # Check the file was modified correctly
                assert "Modified Line 2" in content
                # The exact old string should no longer exist as a standalone line
                # But "Line 2" is a substring of "Modified Line 2" so we check differently
                assert content == "Line 1\nModified Line 2\nLine 3\n"
                assert "edited" in text.lower()
        finally:
            test_file.unlink()
    
    async def test_str_replace_no_match_fails(self):
        """str_replace with no match should fail with error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Line 1\nLine 2\nLine 3\n")
            test_file = Path(f.name)
        
        try:
            async with Client(transport=mcp) as client:
                result = await client.call_tool(
                    name="file_editor",
                    arguments={
                        "command": "str_replace",
                        "path": str(test_file),
                        "old_str": "NonexistentLine",
                        "new_str": "replacement",
                    }
                )
                
                text = result.content[0].text
                
                assert "error" in text.lower()
                assert "not found" in text.lower()
        finally:
            test_file.unlink()
    
    async def test_str_replace_multiple_matches_fails(self):
        """str_replace with multiple matches should fail with line numbers."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("duplicate\nunique\nduplicate\n")
            test_file = Path(f.name)
        
        try:
            async with Client(transport=mcp) as client:
                result = await client.call_tool(
                    name="file_editor",
                    arguments={
                        "command": "str_replace",
                        "path": str(test_file),
                        "old_str": "duplicate",
                        "new_str": "replacement",
                    }
                )
                
                text = result.content[0].text
                
                assert "error" in text.lower()
                assert "multiple" in text.lower()
                # Should mention line numbers to help agent be more specific
                assert "1" in text or "3" in text  # Lines where duplicate appears
        finally:
            test_file.unlink()
    
    async def test_insert_command(self):
        """insert command should insert text at line."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Line 1\nLine 2\nLine 3\n")
            test_file = Path(f.name)
        
        try:
            async with Client(transport=mcp) as client:
                result = await client.call_tool(
                    name="file_editor",
                    arguments={
                        "command": "insert",
                        "path": str(test_file),
                        "insert_line": 1,
                        "new_str": "Inserted Line",
                    }
                )
                
                text = result.content[0].text
                content = test_file.read_text()
                
                assert "Inserted Line" in content
                assert "edited" in text.lower()
        finally:
            test_file.unlink()
    
    async def test_undo_edit_restores_previous(self):
        """undo_edit should restore previous version."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Original content\n")
            test_file = Path(f.name)
        
        try:
            async with Client(transport=mcp) as client:
                # First make an edit
                await client.call_tool(
                    name="file_editor",
                    arguments={
                        "command": "str_replace",
                        "path": str(test_file),
                        "old_str": "Original content",
                        "new_str": "Modified content",
                    }
                )
                
                assert "Modified content" in test_file.read_text()
                
                # Now undo
                result = await client.call_tool(
                    name="file_editor",
                    arguments={
                        "command": "undo_edit",
                        "path": str(test_file),
                    }
                )
                
                text = result.content[0].text
                content = test_file.read_text()
                
                assert content == "Original content\n"
                assert "undone" in text.lower()
        finally:
            test_file.unlink()
    
    async def test_relative_path_fails(self):
        """Relative path should fail with helpful error."""
        async with Client(transport=mcp) as client:
            result = await client.call_tool(
                name="file_editor",
                arguments={
                    "command": "view",
                    "path": "relative/path.txt",
                }
            )
            
            text = result.content[0].text
            
            assert "error" in text.lower()
            assert "absolute" in text.lower()
    
    async def test_nonexistent_path_fails(self):
        """Nonexistent path should fail with helpful error."""
        async with Client(transport=mcp) as client:
            result = await client.call_tool(
                name="file_editor",
                arguments={
                    "command": "view",
                    "path": "/nonexistent/path/that/does/not/exist.txt",
                }
            )
            
            text = result.content[0].text
            
            assert "error" in text.lower()
            assert "not exist" in text.lower() or "does not exist" in text.lower()
    
    async def test_encoding_preservation(self):
        """The editor should preserve UTF-8 encoding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "utf8.txt"
            # Write UTF-8 content with non-ASCII characters
            test_file.write_text("Привет мир\nHello world\n", encoding='utf-8')
            
            async with Client(transport=mcp) as client:
                # Modify via editor
                result = await client.call_tool(
                    name="file_editor",
                    arguments={
                        "command": "str_replace",
                        "path": str(test_file),
                        "old_str": "Hello world",
                        "new_str": "Bonjour le monde",
                    }
                )
                
                text = result.content[0].text
                
                # Should still be valid UTF-8 with original non-ASCII preserved
                content = test_file.read_text(encoding='utf-8')
                assert "Привет мир" in content
                assert "Bonjour le monde" in content

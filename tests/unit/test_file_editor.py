"""
Unit tests for file_editor MCP server.

Following TDD: These tests define expected behavior.
They should FAIL initially, then we make them pass.
"""

import tempfile
from pathlib import Path

import pytest

# Import the module we're testing
import sys
sys.path.insert(0, "mcp-servers/file_editor")
from server import FileEditor, EditorError


class TestFileEditor:
    """Unit tests for FileEditor core logic."""
    
    @pytest.fixture
    def editor(self):
        """Create editor with temp workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield FileEditor(workspace_root=tmpdir)
    
    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Line 1\nLine 2\nLine 3\n")
            path = Path(f.name)
        yield path
        if path.exists():
            path.unlink()
    
    # === VIEW COMMAND TESTS ===
    
    def test_view_file_reads_content(self, editor, temp_file):
        """View should read file content with line numbers."""
        result = editor.view(temp_file)
        
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result
        assert "1\t" in result  # Line numbers
    
    def test_view_directory_lists_files(self, editor):
        """View on directory should list contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "file1.txt").write_text("content")
            (tmpdir_path / "subdir").mkdir()
            
            result = editor.view(tmpdir_path)
            
            assert "file1.txt" in result
            assert "subdir/" in result
    
    def test_view_with_range_reads_subset(self, editor, temp_file):
        """View with range should read only specified lines."""
        result = editor.view(temp_file, view_range=[2, 3])
        
        assert "Line 1" not in result
        assert "Line 2" in result
        assert "Line 3" in result
    
    def test_view_nonexistent_file_raises(self, editor):
        """Viewing nonexistent file should raise error."""
        with pytest.raises(EditorError, match="does not exist"):
            editor.view(Path("/nonexistent/file.txt"))
    
    # === CREATE COMMAND TESTS ===
    
    def test_create_new_file(self, editor):
        """Create should make new file with content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "new_file.txt"
            content = "Hello\nWorld\n"
            
            result = editor.create(file_path, content)
            
            assert file_path.exists()
            assert file_path.read_text() == content
            assert "created successfully" in result
    
    def test_create_existing_file_raises(self, editor, temp_file):
        """Create on existing file should raise error."""
        with pytest.raises(EditorError, match="already exists"):
            editor.create(temp_file, "new content")
    
    def test_create_adds_to_history(self, editor):
        """Create should add initial content to history."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "new_file.txt"
            content = "Initial content"
            
            editor.create(file_path, content)
            
            # Should be able to undo (means history exists)
            assert editor.history_manager.pop(file_path) == content
    
    # === STR_REPLACE COMMAND TESTS ===
    
    def test_str_replace_unique_match(self, editor, temp_file):
        """str_replace should replace unique exact match."""
        result = editor.str_replace(temp_file, "Line 2", "Modified Line 2")
        
        content = temp_file.read_text()
        assert "Modified Line 2" in content
        # Check full content instead of substring check (Line 2 != Modified Line 2)
        assert content == "Line 1\nModified Line 2\nLine 3\n"
        assert "edited" in result.lower()
    
    def test_str_replace_no_match_raises(self, editor, temp_file):
        """str_replace with no match should raise error."""
        with pytest.raises(EditorError, match="not found"):
            editor.str_replace(temp_file, "NonexistentLine", "replacement")
    
    def test_str_replace_multiple_matches_raises(self, editor, temp_file):
        """str_replace with multiple matches should raise error."""
        # Add duplicate line
        content = temp_file.read_text() + "Line 2\n"
        temp_file.write_text(content)
        
        with pytest.raises(EditorError, match="Multiple matches"):
            editor.str_replace(temp_file, "Line 2", "replacement")
    
    def test_str_replace_same_strings_raises(self, editor, temp_file):
        """str_replace with same old and new should raise error."""
        with pytest.raises(EditorError, match="must be different"):
            editor.str_replace(temp_file, "Line 2", "Line 2")
    
    def test_str_replace_preserves_encoding(self, editor):
        """str_replace should preserve file encoding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "utf8_file.txt"
            # Write UTF-8 content
            file_path.write_text("Привет\nМир\n", encoding='utf-8')
            
            editor.str_replace(file_path, "Мир", "World")
            
            # Should still be valid UTF-8
            content = file_path.read_text(encoding='utf-8')
            assert "World" in content
            assert "Привет" in content
    
    def test_str_replace_adds_to_history(self, editor, temp_file):
        """str_replace should save old content to history."""
        original = temp_file.read_text()
        
        editor.str_replace(temp_file, "Line 2", "Modified")
        
        # Should be able to undo
        old = editor.history_manager.pop(temp_file)
        assert old == original
    
    # === INSERT COMMAND TESTS ===
    
    def test_insert_at_beginning(self, editor, temp_file):
        """Insert at line 0 should insert at beginning."""
        result = editor.insert(temp_file, 0, "New First Line")
        
        content = temp_file.read_text()
        lines = content.split("\n")
        assert lines[0] == "New First Line"
    
    def test_insert_at_end(self, editor, temp_file):
        """Insert at end should append."""
        num_lines = len(temp_file.read_text().split("\n"))
        
        editor.insert(temp_file, num_lines, "New Last Line")
        
        content = temp_file.read_text()
        assert "New Last Line" in content
    
    def test_insert_in_middle(self, editor, temp_file):
        """Insert in middle should insert after specified line."""
        editor.insert(temp_file, 1, "Inserted Line")
        
        content = temp_file.read_text()
        lines = content.split("\n")
        # After line 1 (Line 1), before old line 2
        assert "Inserted Line" in lines
    
    def test_insert_invalid_line_raises(self, editor, temp_file):
        """Insert with invalid line number should raise error."""
        num_lines = len(temp_file.read_text().split("\n"))
        
        with pytest.raises(EditorError, match="must be in range"):
            editor.insert(temp_file, num_lines + 10, "new line")
    
    # === UNDO_EDIT COMMAND TESTS ===
    
    def test_undo_edit_restores_previous(self, editor, temp_file):
        """undo_edit should restore previous version."""
        original = temp_file.read_text()
        
        # Make an edit
        editor.str_replace(temp_file, "Line 2", "Modified")
        assert "Modified" in temp_file.read_text()
        
        # Undo
        result = editor.undo_edit(temp_file)
        
        # Should be back to original
        assert temp_file.read_text() == original
        assert "undone" in result.lower()
    
    def test_undo_edit_no_history_raises(self, editor, temp_file):
        """undo_edit with no history should raise error."""
        with pytest.raises(EditorError, match="No edit history"):
            editor.undo_edit(temp_file)
    
    # === VALIDATION TESTS ===
    
    def test_validate_path_rejects_relative(self, editor):
        """Should reject relative paths."""
        # Error message: "The path should be absolute, starting with `/`."
        with pytest.raises(EditorError, match="absolute"):
            editor.validate_path("view", Path("relative/path.txt"))
    
    def test_validate_file_size_limit(self, editor):
        """Should reject files over size limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            big_file = Path(tmpdir) / "big.txt"
            # Write 11MB of data (over 10MB limit)
            big_file.write_bytes(b"x" * (11 * 1024 * 1024))
            
            with pytest.raises(EditorError, match="too large"):
                editor.validate_file(big_file)
    
    def test_validate_binary_file_rejection(self, editor):
        """Should reject binary files (except images)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            binary_file = Path(tmpdir) / "binary.bin"
            binary_file.write_bytes(b"\x00\x01\x02\x03\x04\x05")
            
            with pytest.raises(EditorError, match="binary"):
                editor.validate_file(binary_file)
    
    # === ENCODING TESTS ===
    
    def test_encoding_detection_utf8(self, editor):
        """Should detect UTF-8 encoding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            utf8_file = Path(tmpdir) / "utf8.txt"
            utf8_file.write_text("Hello 世界", encoding='utf-8')
            
            encoding = editor.encoding_manager.detect(utf8_file)
            assert encoding.lower() in ['utf-8', 'ascii']  # ASCII is subset
    
    def test_encoding_preservation_on_write(self, editor):
        """Should preserve encoding when writing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            # Write UTF-8
            file_path.write_text("Тест", encoding='utf-8')
            
            # Modify via editor
            editor.str_replace(file_path, "Тест", "Test")
            
            # Should still be valid UTF-8
            content = file_path.read_text(encoding='utf-8')
            assert content == "Test"


class TestHistoryManager:
    """Unit tests for history management."""
    
    def test_add_and_pop_history(self):
        """Should add and retrieve history."""
        from server import HistoryManager
        
        hm = HistoryManager(max_per_file=5)
        test_path = Path("/test/file.txt")
        
        hm.add(test_path, "content v1")
        hm.add(test_path, "content v2")
        
        assert hm.pop(test_path) == "content v2"
        assert hm.pop(test_path) == "content v1"
    
    def test_history_eviction(self):
        """Should evict old entries when over limit."""
        from server import HistoryManager
        
        hm = HistoryManager(max_per_file=3)
        test_path = Path("/test/file.txt")
        
        hm.add(test_path, "v1")
        hm.add(test_path, "v2")
        hm.add(test_path, "v3")
        hm.add(test_path, "v4")
        
        # Should only have last 3
        assert hm.pop(test_path) == "v4"
        assert hm.pop(test_path) == "v3"
        assert hm.pop(test_path) == "v2"
        assert hm.pop(test_path) is None  # v1 was evicted


class TestEncodingManager:
    """Unit tests for encoding detection."""
    
    def test_detect_utf8(self):
        """Should detect UTF-8."""
        from server import EncodingManager
        
        em = EncodingManager()
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as f:
            f.write("Hello 世界")
            path = Path(f.name)
        
        encoding = em.detect(path)
        assert encoding.lower() in ['utf-8', 'ascii']
        path.unlink()
    
    def test_encoding_cache(self):
        """Should cache encoding by mtime."""
        from server import EncodingManager
        
        em = EncodingManager()
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as f:
            f.write("Test content")
            path = Path(f.name)
        
        # First call detects
        enc1 = em.detect(path)
        # Second call uses cache (same mtime)
        enc2 = em.detect(path)
        
        assert enc1 == enc2
        path.unlink()

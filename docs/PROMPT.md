# TDD Implementation Pattern for Crow MCP Tools

## 🚨 FIRST THING - READ THESE DOCS

**In this order:**
1. **AGENTS.md** - Critical rules (no git commits, use `uv --project .`), current state, patterns
2. **IMPLEMENTATION_PLAN.md** - Current goals, what's done, what's next
3. **This file** (PROMPT.md) - The workflow pattern

Then proceed with the workflow below.

---

## The Sacred Workflow

### 1. UNDERSTAND (Don't Copy)
- **Read code deeply** - not to copy, but to understand *why*
- **Ask**: What problem does this solve? Why this design?
- **Research** - Use internet, specs, llms.txt, documentation
- **NO CARGO-CULTING** - If you copy without understanding, you've failed

### 2. DOCUMENT Understanding
- **Write essay** in `docs/essays/[topic-name].md` (descriptive names, not dates)
- Explain architecture, design decisions, trade-offs
- Blog-post quality - teach the concepts
- Include: "Here's how X works and what makes it great"

### 3. RESEARCH Gaps
- **Use the internet** - search liberally (searxng_web_search tool)
- Read specs (MCP, ACP, FastMCP, Skills)
- Study real implementations
- When stuck: RESEARCH, don't guess

### 4. WRITE TESTS (The TDD Part)
**Tests come from understanding, NOT implementation**

```python
# ✅ GOOD: Test from spec understanding
def test_str_replace_rejects_duplicate_matches():
    """If old_str appears multiple times, fail with line numbers.
    Forces agent to include more context for uniqueness."""
    with pytest.raises(EditorError, match="Multiple matches"):
        editor.str_replace(path, "duplicate", "new")

# ❌ BAD: Test from implementation
def test_str_replace_uses_regex():
    """Tests HOW it works, not WHAT it should do."""
    assert editor._uses_regex == True  # brittle!
```

**Test Structure**:
- Unit tests: Fast, isolated, test semantics not implementation
- Integration tests: Components working together
- E2E tests: **REAL TESTS, NO MOCKS, LIVE EVERYTHING**

### 5. E2E TESTS ARE SACRED
**E2E tests validate your ASSUMPTIONS - NO MOCKS ALLOWED**

```python
# ✅ GOOD: E2E with real MCP
from fastmcp import Client
from server import mcp

async def test_file_editor_creates_file():
    async with Client(transport=mcp) as client:
        result = await client.call_tool("file_editor", {
            "command": "create",
            "path": str(test_file),
            "file_text": "Hello"
        })
        assert test_file.exists()  # Actually proved it works!

# ❌ FRAUD: E2E with mock - proves NOTHING
class MockAgent:
    async def create_file(self):
        return "success"
agent = MockAgent()
assert await agent.create_file() == "success"  # You hard-coded it, derp
```

**Why NO MOCKS in E2E**:
- Mocks test your assumptions, not the system
- "The test passes" ≠ "The code works"
- Real components expose real bugs
- Slow is smooth, smooth is fast

**When E2E fails**:
1. It revealed a wrong assumption ✅
2. Research the actual behavior
3. Update understanding
4. Fix test OR fix implementation
5. Document what you learned

### 6. IMPLEMENT (Make Tests Green)
Now write code to make tests pass:
- Minimal implementation
- Clean, focused code
- No speculative features
- Keep it simple

### 7. REFACTOR (Keep Tests Green)
- Clean up while tests still pass
- Remove duplication
- Improve names
- Simplify

## The Mantra

```
UNDERSTAND → DOCUMENT → RESEARCH → TEST → IMPLEMENT → REFACTOR
     ↑                                                      ↓
     ←←←←←←←←←←← RED IS GOOD, RESEARCH MORE ←←←←←←←←←←←←←←←←
```

**Red tests are teachers** - they show where understanding is wrong.

---

## 🎯 Current Task: Terminal MCP Server

### Context
We have `mcp-servers/terminal/` with openhands terminal implementation from software-agent-sdk. It has:
- `definition.py` - TerminalAction, TerminalObservation schemas
- `impl.py` - TerminalExecutor with sessions
- `terminal/` - tmux/subprocess backends
- BUT: Depends on `openhands.sdk.*` imports (coupled to their SDK)
- `main.py` is just `print("Hello from terminal!")` - NOT a FastMCP server

### Task: Create Terminal MCP Server (like file_editor)

**Step 1: UNDERSTAND**
Read the existing terminal code:
```bash
cat mcp-servers/terminal/definition.py
cat mcp-servers/terminal/impl.py
cat mcp-servers/terminal/terminal/subprocess_terminal.py
```
Understand:
- What commands does it execute?
- How do sessions work?
- What about timeouts?
- What about interrupting running commands?

**Step 2: DOCUMENT**
Write `docs/essays/terminal-tool-semantics.md` covering:
- Terminal tool purpose (shell execution for agents)
- Core operations: execute, interrupt, reset
- Session persistence (or not?)
- Output handling (truncation? streaming?)
- Security considerations (what commands to allow?)

**Step 3: RESEARCH**
- Check how FastMCP handles streaming/long-running operations
- Study kimi-cli terminal implementation if helpful
- Look at software-agent-sdk terminal for patterns

**Step 4: WRITE TESTS FIRST**
Create `tests/e2e/test_terminal_mcp.py` with REAL shell commands:
```python
async def test_execute_echo_command():
    """Execute simple echo command."""
    async with Client(transport=terminal_mcp) as client:
        result = await client.call_tool("terminal", {
            "command": "echo 'Hello World'"
        })
        assert "Hello World" in result.content[0].text

async def test_execute_ls_command():
    """Execute ls and verify output."""
    async with Client(transport=terminal_mcp) as client:
        result = await client.call_tool("terminal", {
            "command": "ls /tmp"
        })
        assert result.content[0].text  # Non-empty output

async def test_command_exit_code():
    """Non-zero exit code should be in response."""
    async with Client(transport=terminal_mcp) as client:
        result = await client.call_tool("terminal", {
            "command": "exit 1"
        })
        # Should indicate failure somehow
```

**Step 5: IMPLEMENT**
Create `mcp-servers/terminal/server.py`:
```python
from fastmcp import FastMCP

mcp = FastMCP(name="terminal")

@mcp.tool
async def terminal(command: str, timeout: float | None = None) -> str:
    """Execute a shell command.
    
    Args:
        command: Shell command to execute
        timeout: Optional timeout in seconds
    
    Returns:
        Command output (stdout + stderr)
    """
    # Use subprocess to execute
    # Return output
    # Handle errors gracefully
    pass

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

**Step 6: MAKE TESTS GREEN**
Run tests, fix issues, repeat until all pass.

**Step 7: REFACTOR**
Clean up, remove duplication, simplify.

---

## ✅ Done (Reference)

### file_editor MCP Server
- 28 unit tests + 15 E2E tests passing
- `mcp-servers/file_editor/server.py` - Clean implementation
- `tests/e2e/test_file_editor_mcp.py` - Pattern for MCP E2E tests
- Essay: `docs/essays/file-editor-semantics-and-fastmcp.md`

### E2E Pattern (NO MOCKS!)
```python
from fastmcp import Client
import sys
sys.path.insert(0, "mcp-servers/file_editor")
from server import mcp

async with Client(transport=mcp) as client:
    result = await client.call_tool("tool_name", {"arg": "value"})
    assert expected_behavior
```

---

## Virtual Env
```bash
# All commands use:
uv --project . run pytest tests/
uv --project . run python src/crow/acp_agent.py
```

## Remember

> "What you're generating isn't code, it's UNDERSTANDING."

The tests encode understanding. Implementation is just making them pass.

When in doubt: **RESEARCH** 🔍
When stuck: **WRITE A TEST** ❤️  
When red: **LEARN** 📚
When E2E: **NO MOCKS** 🚫

---

**Good luck! Follow the workflow. Start with UNDERSTANDING the terminal code, then DOCUMENT, then TEST, then IMPLEMENT.** 

🫡

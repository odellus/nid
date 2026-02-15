# ACP Agent Implementation Plan

This document outlines the plan to properly implement our agent as an ACP-native agent, fixing the architectural anti-pattern of having multiple agent classes.

---

## ✅ Goal 1: Merge Agents into Single ACP-Native Agent

### Current Status: COMPLETE ✅

**Implementation:**
- Created `src/crow/agent/acp_native.py` with merged `Agent(acp.Agent)` class
- Moved ALL business logic from old Agent into the new agent
- Proper resource management with AsyncExitStack
- Added `db_path` parameter for testability

**Tests:**
- ✅ 41 tests passing (up from 30 baseline - NO REGRESSIONS)
- ✅ Live E2E test passing with REAL LLM + DB + MCP (no mocks!)
- ✅ Comprehensive validation: DB state, streaming, session reload, ACP protocol
- ✅ Session creation, persistence, and reload working
- ✅ Conversation history preserved across reloads (system, user, assistant)
- ✅ Multi-session isolation working (UUID-based session IDs)
- 6 rail-guard tests failing (expected - TDD markers for cleanup phase)
- 8 compaction tests failing (expected - TDD markers for next feature)

**Known Issues:**
- Old `agent.py` and `acp_agent.py` still exist (Phase 6 cleanup)
- Minor parameter naming (`session_id` vs `session`) - acceptable

```
src/crow/
├── acp_agent.py           # CrowACPAgent - ACP wrapper
└── agent/
    └── agent.py           # Agent - business logic
    
This creates: CrowACPAgent wraps Agent
```

**Why this is wrong:**
- Unnecessary indirection
- Violates ACP pattern (Agent IS the implementation)
- Confusion about which is "the agent"
- Extra abstraction without benefit

### Target Architecture (Correct Pattern)

```
src/crow/
└── agent.py               # Single Agent(acp.Agent) class
    
This creates: Agent inherits from acp.Agent directly
```

**Why this is right:**
- Follows ACP SDK pattern exactly
- Business logic goes IN the Agent class
- No wrapper, no confusion
- Single source of truth

### What This Looks Like

```python
# src/crow/agent.py
from acp import Agent, PromptResponse

class Agent(Agent):
    """ACP-native agent - single agent class"""
    
    def __init__(self):
        self._exit_stack = AsyncExitStack()  # Resource management
        self._mcp_clients = {}  # session_id -> mcp_client (only thing not in DB)
        self._token_counts = {}  # session_id -> {"input": 0, "output": 0}
        self._llm = configure_llm()
        self._conn = None  # ACP connection
    
    def on_connect(self, conn: Client):
        self._conn = conn
    
    async def new_session(self, cwd, mcp_servers, **kwargs):
        # Setup MCP client (AsyncExitStack manages lifecycle)
        mcp_client = setup_mcp_client("src/crow/mcp/search.py")
        mcp_client = await self._exit_stack.enter_async_context(mcp_client)
        
        # Get tools
        tools = await get_tools(mcp_client)
        
        # Create Session (persisted to DB)
        session = Session.create(
            prompt_id="crow-v1",
            prompt_args={"workspace": cwd},
            tool_definitions=tools,
            request_params={"temperature": 0.7},
            model_identifier="glm-5",
        )
        
        # Store ONLY MCP client (session is in DB)
        self._mcp_clients[session.session_id] = mcp_client
        self._token_counts[session.session_id] = {"input": 0, "output": 0, "threshold": 100000}
        
        return NewSessionResponse(session_id=session.session_id)
    
    async def prompt(self, prompt, session_id, **kwargs):
        # Load session from database
        session = Session.load(session_id)
        
        # Get MCP client
        mcp_client = self._mcp_clients[session_id]
        tools = await get_tools(mcp_client)
        
        # Add user message
        session.add_message("user", extract_text(prompt))
        
        # Run react loop (business logic from old Agent)
        async for chunk in self._react_loop(session, mcp_client, tools):
            await self._conn.session_update(
                session_id,
                update_agent_message(text_block(chunk))
            )
        
        # Check for compaction (post-request hook)
        await self._after_request(session_id, usage)
        
        return PromptResponse(stop_reason="end_turn")
    
    async def cleanup(self):
        await self._exit_stack.aclose()
```

### Implementation Steps

1. **Research ACP SDK patterns**
   - Read `deps/python-sdk/schema/schema.json`
   - Study `deps/python-sdk/examples/echo_agent.py`
   - Study `deps/python-sdk/examples/agent.py`
   - Study `deps/kimi-cli/` for real-world implementation

2. **Extract business logic from old Agent**
   - `react_loop()` method
   - `send_request()` method
   - `process_response()` method
   - `execute_tool_calls()` method

3. **Create new single Agent class**
   - Inherit from `acp.Agent`
   - Move business logic methods into agent
   - Implement ACP methods: `new_session()`, `prompt()`, etc.
   - Use AsyncExitStack for resource management

4. **Update imports and entry point**
   - Update `src/crow/acp_agent.py` to use new agent
   - Or rename to `src/crow/agent.py` and delete old agent module
   - Update `__init__.py` exports

5. **Update tests**
   - Tests should still work (they test behavior, not structure)
   - Update any imports if needed

---

## 🎯 Goal 2: Implement MCP Tools for Shell and File Editing

### ✅ Status: File Editor COMPLETE (needs tests)

**Implementation Date**: February 14, 2026

**What Was Done**:
1. ✅ Deep architectural study documented in `docs/essays/14Feb2026.md`
   - Part 1: file_editor semantics (pattern matching tool for LLMs)
   - Part 2: FastMCP protocol understanding
2. ✅ Clean implementation in `mcp-servers/file_editor/server.py`
   - **NO openhands SDK dependencies**
   - Standard library + minimal deps (charset_normalizer, binaryornot, cachetools)
   - ~580 lines of focused code
   - Preserves all critical semantics (exact matching, encoding, history, rich errors)

**What's Left**:
- Unit tests (started in `tests/unit/test_file_editor.py`)
- E2E test with live MCP server
- Terminal MCP server (same approach)

**Key Insight**: file_editor is NOT a text editor - it's a semantic string manipulation tool designed for how LLMs think about text (patterns, not cursors).

### Requirements

**Shell Tool:**
- Study kimi-cli shell implementation
- Test if ACP client exposes shell capability
- If client has shell, use client's shell instead of our own
- Otherwise, implement MCP shell tool similar to kimi-cli

**File Editor Tool:**
- **DO NOT copy kimi-cli's file editor** (user reports it's broken, agents fall back to sed/awk)
- **DO study openhands file_editor tool** (deps/software-agent-sdk/openhands-tools/)
- Implement proper file editing with:
  - View files
  - Create files
  - Edit files (str_replace pattern like we use)
  - Delete files
  - Proper error handling

### Implementation Approach

```bash
# Research openhands file editor
cat deps/software-agent-sdk/openhands-tools/openhands/tools/file_editor/

# Research kimi-cli shell
cat deps/kimi-cli/src/kimi_cli/tools/shell.py

# Check ACP client capabilities for shell
# TODO: Determine how to query client for shell support
```

### File Structure

```
src/crow/mcp/
├── search.py          # Existing search MCP
├── shell.py           # Shell execution MCP (new)
└── file_editor.py     # File editing MCP (new)
```

---

## 🎯 Goal 3: Enhanced E2E Testing Framework


```
warning: adding embedded git repository: deps/kimi-cli
warning: adding embedded git repository: deps/software-agent-sdk
```

### Solution

```bash
# Remove wrongly added directories
git rm --cached deps/kimi-cli
git rm --cached deps/software-agent-sdk

# Remove the directories themselves
rm -rf deps/kimi-cli
rm -rf deps/software-agent-sdk

# Add as proper submodules
git submodule add git@github.com:MoonshotAI/kimi-cli.git deps/kimi-cli
git submodule add <software-agent-sdk-url> deps/software-agent-sdk

# Initialize submodules
git submodule update --init --recursive
```

---

## 🎯 Goal 3: ACP Protocol Compliance

### Study Required

1. **Read ACP Specification**
   ```bash
   cat deps/python-sdk/schema/schema.json
   ```
   - Understand all required methods
   - Understand message flow
   - Understand capabilities negotiation

2. **Read ACP Examples**
   ```bash
   cat deps/python-sdk/examples/echo_agent.py    # Simplest
   cat deps/python-sdk/examples/agent.py         # Full featured
   cat deps/python-sdk/examples/gemini.py        # Real integration
   ```

3. **Study kimi-cli Implementation**
   ```bash
   ls deps/kimi-cli/
   # Find their ACP agent implementation
   # See how they structure sessions, tools, etc.
   ```

### Implement Missing ACP Methods

Current `CrowACPAgent` implements:
- ✅ `initialize()`
- ✅ `authenticate()`
- ✅ `new_session()`
- ✅ `load_session()`
- ✅ `set_session_mode()`
- ✅ `prompt()`
- ✅ `cancel()`
- ✅ `ext_method()`
- ✅ `ext_notification()`

Verify all are correctly implemented according to spec.

---

## 🎯 Goal 4: Test Coverage for Merged Agent

### Tests to Write/Update

1. **Unit tests for merged agent**
   - Test agent creation
   - Test session management
   - Test react loop integration
   - Test resource cleanup

2. **Integration tests with ACP client**
   - Test full session lifecycle
   - Test streaming updates
   - Test tool execution
   - Test error handling

3. **E2E tests with real ACP client**
   - Test with `deps/python-sdk/examples/client.py`
   - Verify streaming works
   - Verify tool calls work
   - Verify cleanup happens

---

## 🎯 Goal 5: Documentation Updates

### Update AGENTS.md

- Remove references to multiple agent classes
- Update architecture diagram
- Document merged agent pattern
- Add learnings from ACP implementation

### Update Project README

- Explain ACP-native architecture
- Explain why single agent class matters
- Link to ACP specification

---

## 🎯 Implementation Order

### Phase 1: Research (CRITICAL - DO NOT SKIP)
1. Read ACP spec (schema.json)
2. Read all ACP SDK examples
3. Study kimi-cli implementation
4. Document patterns and requirements

### Phase 2: Prepare Workspace
1. Fix git submodules
2. Run all tests to ensure green baseline
3. Document current agent structure

### Phase 3: Merge Agents
1. Create new merged Agent class
2. Move business logic methods
3. Update imports and entry points
4. Run tests, fix breaking changes

### Phase 4: Validate
1. Test with ACP client
2. Verify all functionality works
3. Test resource cleanup (AsyncExitStack)
4. Run full test suite

### Phase 5: Clean Up
1. Remove old agent files if needed
2. Update documentation
3. Ensure imports are clean

---

## 🚨 Critical Success Factors

1. **Research FIRST** - Do not implement until ACP spec is understood
2. **Keep tests green** - Run tests after every change
3. **Follow ACP patterns** - Use SDK examples as guide
4. **Single agent class** - No wrappers, no multiple agents
5. **AsyncExitStack** - Proper resource management always
6. **No git commits** - Human commits, agent writes code

---

## 📐 Architecture Principles

### Single Source of Truth
- ONE agent class (`Agent(acp.Agent)`)
- Business logic lives IN the agent
- No wrappers, no delegation, no confusion

### ACP-Native
- Follow ACP SDK patterns exactly
- Agent IS the implementation
- No abstraction layers between agent and ACP

### Resource Safety  
- AsyncExitStack for all async context managers
- Cleanup guaranteed even on exceptions
- Test resource cleanup explicitly

### Test-Driven
- Tests verify behavior, not structure
- Refactor structure while keeping tests green
- Add new tests for merged agent behavior

---

## 🔗 Resources

- ACP Specification: `deps/python-sdk/schema/schema.json`
- ACP Examples: `deps/python-sdk/examples/`
- Kimi-cli Reference: `deps/kimi-cli/`
- Current Agent: `src/crow/acp_agent.py` (CrowACPAgent)
- Old Agent Logic: `src/crow/agent/agent.py` (Agent)
- Session Management: `src/crow/agent/session.py`
- Test Suite: `tests/`

---

## ✅ Definition of Done

A merged ACP agent is complete when:

1. ✅ Single `Agent(acp.Agent)` class exists
2. ✅ All business logic incorporated
3. ✅ All ACP methods implemented correctly
4. ✅ Resource cleanup verified (AsyncExitStack)
5. ✅ All 28 tests still pass
6. ✅ Works with ACP client
7. ✅ No git commits made by agent
8. ✅ Documentation updated
9. ✅ No code duplication
10. ✅ Follows ACP SDK patterns exactly

---

**Remember: This is a fundamental architectural change. Take time to research ACP spec deeply before implementing. The goal is not just to make it work, but to make it correct according to ACP patterns.**

# NID Agent Development Guide

This document captures patterns, anti-patterns, and best practices learned through iterative development. **Read this first before making changes to the codebase.**

---

## 🔴🔴🔴 CRITICAL RULES - VIOLATION = BANNED 🔴🔴🔴

### 0. **NEVER MAKE GIT COMMITS**
```
⛔️ AI AGENTS ARE ABSOLUTELY FORBIDDEN FROM MAKING GIT COMMITS ⛔️

DO NOT:
- git commit
- git add && git commit
- git commit -a
- ANY git commit command

ONLY THE HUMAN USER CAN MAKE GIT COMMITS.

VIOLATION OF THIS RULE = IMMEDIATE BANNING FROM THE PROJECT.

This is non-negotiable. The human owns the git history, not you.
You are here to write code, not to commit it.
```

### 1. ALWAYS Use `uv --project .`
```bash
# ✅ CORRECT
uv --project . run pytest tests/
uv --project . run python src/nid/acp_agent.py

# ❌ WRONG - Will use wrong Python/environment
python -m pytest tests/
pytest tests/
```

**Why**: Each terminal session starts fresh. The `--project .` flag ensures:
- Correct Python version (3.12+)
- Correct virtual environment
- Correct dependencies loaded
- Consistent behavior across sessions

### 2. NO Persistent Terminal State
Each terminal command executes in isolation. You cannot:
- Rely on `cd` from previous commands
- Use environment variables from previous sessions
- Assume any state persistence

**Always use absolute paths and `--project .` flag.**

---

## 🧪 Testing & TDD

### Test-Driven Development (REQUIRED)

**Always write tests FIRST. This is not optional.**

```bash
# 1. RED: Write failing test
uv --project . run pytest tests/unit/test_feature.py -v

# 2. GREEN: Implement minimal code to pass
uv --project . run pytest tests/unit/test_feature.py -v

# 3. REFACTOR: Clean up while keeping tests green
uv --project . run pytest tests/ -v
```

### Running Tests

```bash
# Run all tests
uv --project . run pytest tests/ -v

# Run specific test levels
uv --project . run pytest tests/unit/ -v          # Fast, isolated tests
uv --project . run pytest tests/integration/ -v   # Component interactions
uv --project . run pytest tests/e2e/ -v           # Full stack tests

# Run specific test file
uv --project . run pytest tests/unit/test_mcp_lifecycle.py -v

# Run with coverage
uv --project . run pytest --cov=src/nid --cov-report=html tests/

# Run tests matching pattern
uv --project . run pytest tests/ -k "lifecycle" -v
```

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Fast, isolated tests
│   ├── test_mcp_lifecycle.py
│   └── test_prompt_persistence.py
├── integration/             # Component interactions
│   └── test_session_lifecycle.py
└── e2e/                     # End-to-end flows
    └── test_agent_e2e.py
```

---

## 🏗️ Async Resource Management

### ✅ CORRECT Pattern: AsyncExitStack

**For managing async context managers (MCP clients, database connections, etc.)**

```python
from contextlib import AsyncExitStack

class Agent:
    def __init__(self):
        self._exit_stack = AsyncExitStack()
        self._mcp_client = None
    
    async def create_session(self, mcp_client):
        # Proper lifecycle management - cleanup guaranteed!
        self._mcp_client = await self._exit_stack.enter_async_context(mcp_client)
        return self._mcp_client
    
    async def cleanup(self):
        """Cleanup all resources properly."""
        await self._exit_stack.aclose()
```

**Why this is correct:**
- ✅ Resources ALWAYS cleaned up (even on exceptions)
- ✅ Multiple resources managed correctly
- ✅ Idiomatic Python (standard library pattern)
- ✅ Exception-safe
- ✅ Tested and verified

### ❌ ANTI-PATTERN: Manual Lifecycle Calls

```python
# ❌ NEVER DO THIS
async def create_session(self, mcp_client):
    await mcp_client.__aenter__()  # WRONG! Manual call
    # ... use client ...
    # NO CLEANUP! Resource leak!

# ❌ NEVER DO THIS
async with mcp_client:  # Context closes too early!
    # ... setup ...
# Client is CLOSED here, can't use it later!
```

**Why this is wrong:**
- 💀 Manual `__aenter__()` bypasses safety guarantees
- 💀 No cleanup → memory/connection leaks
- 💀 Not exception-safe
- 💀 "Tests pass" but production will have leaks

---

## 🔍 Research First

### Before Implementing ANYTHING:

1. **Search for existing patterns**
   ```bash
   # Check if pattern already exists in codebase
   grep -r "AsyncExitStack" src/
   grep -r "async.*context" src/
   ```

2. **Read the documentation**
   - Check `deps/python-sdk/docs/` for ACP patterns
   - Check `docs/` for project-specific patterns
   - Search online for Python best practices

3. **Check existing abstractions**
   - Use `Session`, `Agent`, `lookup_or_create_prompt`
   - Don't reinvent the wheel

### Research Process

```bash
# 1. Search codebase for existing patterns
grep -r "pattern_name" src/
find . -name "*.py" | xargs grep "async.*with"

# 2. Read SDK documentation
cat deps/python-sdk/docs/quickstart.md
cat deps/python-sdk/examples/echo_agent.py

# 3. Search online for best practices
# Use web search tools to find:
# - Official Python documentation
# - Established patterns and anti-patterns
# - Real-world examples

# 4. Write tests FIRST to verify understanding
# 5. Then implement
```

---

## 🎯 Project Architecture

### Core Philosophy: Frameworkless Framework

We don't build agent frameworks. We connect protocols.

**What we are:**
- ACP-first agent implementation
- MCP-first tool calling (via FastMCP)
- Minimal, purpose-specific code
- Protocol compliance over framework features

**What we are NOT:**
- Another agent SDK (not like kimi-cli, software-agent-sdk, openhands.sdk)
- A tool calling framework (FastMCP has this covered)
- A type system for agents (use ACP schema)
- A state management framework (use ACP session/load)

### The 6 Core Components

#### 1. ACP-First Agent
**Status**: In progress (merging agents into single ACP-native implementation)

We implement `agent-client-protocol` directly on top of minimal react loops:
- Single `NidAgent(acp.Agent)` class
- Business logic lives IN the agent
- No wrapper, no separate framework
- ACP protocol compliance is the architecture

**Reference**: `deps/python-sdk/schema/schema.json`

#### 2. MCP-First Frameworkless Framework
**Status**: ✅ Complete (via FastMCP)

All agent frameworks are just sophisticated tool calling frameworks. FastMCP already solves this.
- We use FastMCP for tool definitions and execution
- No need to reinvent tool calling
- MCP is the standard, we just consume it
- Framework-free: MCP + react loop = agent

**Implementation**: `src/nid/mcp/search.py`, `src/nid/agent/mcp.py`

#### 3. Persistence (ACP session/load)
**Status**: ✅ Complete

Our persistence layer implements ACP's session/load specification:
- Prompts: Versioned system prompt templates
- Sessions: The "DNA" of the agent (KV cache anchor)
- Events: The "wide" transcript (conversation turns)

**This isn't just persistence** - it's ACP session management implemented correctly.

**Implementation**: `src/nid/agent/session.py`, `src/nid/agent/db.py`

#### 4. SKILLS (CRITICAL - NOT YET IMPLEMENTED)
**Status**: ❌ NOT BEGUN

This is mondo critical. Skills are the project's extension mechanism.
- Specification: `https://agentskills.io/llms.txt`
- Skills allow agents to have specialized capabilities
- Must implement according to agentskills specification
- This is a separate protocol from ACP/MCP

**Action Required**: Read spec, design implementation, TDD

#### 5. Prompt Management
**Status**: ✅ Partially Complete

System prompt versioning and rendering:
- Templates stored in database
- Jinja2 rendering with arguments
- Lookup-or-create pattern
- Deterministic session IDs for KV cache reuse

**Implementation**: `src/nid/agent/prompt.py`, `src/nid/agent/prompts/`

#### 6. Compaction
**Status**: ❌ NOT YET IMPLEMENTED

Conversation compaction to manage token limits. **Compaction creates a NEW session to replace the old one.**

**Reference Implementations**:
- `deps/kimi-cli/src/kimi_cli/soul/compaction.py` - SimpleCompaction
- `deps/software-agent-sdk/openhands-sdk/openhands/sdk/context/condenser/llm_summarizing_condenser.py` - LLMSummarizingCondenser

**How kimi-cli does it**:
1. Keep last K messages (preserve from tail)
2. Take first messages → format as: `## Message {i}\nRole: {role}\nContent:\n{content}`
3. Append COMPACT prompt to formatted messages
4. Send to LLM (separate summarizer LLM, not agent session)
5. Create new user message: "Previous context has been compacted. Here is the compaction output:" + summary
6. Append preserved messages

**How software-agent-sdk does it**:
1. Keep first `keep_first` events
2. Calculate suffix events to keep (based on tokens/events/requests)
3. Identify "forgotten events" in middle
4. Send forgotten events to condenser's own LLM for summarization
5. Create `Condensation` event with summary + forgotten_event_ids
6. Insert at summary_offset

**Our Approach** (adapted from kimi-cli + software-agent-sdk):
1. **Agent is running** - ACP agent on stdio, initialized with session/workspace/MCP tools
2. **Conversation fills context** - User talks, agent responds, messages pile up  
3. **Threshold tripped** - `sum(input_tokens + output_tokens) > threshold`
4. **Pause react loop** - Stop mid-execution when threshold detected
5. **Send summarization request to SAME session**:
   ```python
   # Keep last K messages
   preserved = session.messages[-K:]
   
   # Format middle messages for summarization
   to_compact = session.messages[K:-K]
   formatted = "\n\n".join([
       f"## Message {i}\nRole: {msg['role']}\nContent:\n{msg['content']}"
       for i, msg in enumerate(to_compact)
   ])
   
   # Add to session as user message
   session.add_message("user", f"""
   {formatted}
   
   Please summarize the above conversation into a single message.
   CRITICAL: Do NOT call any tools for this request.
   Focus on preserving: file paths changed, key decisions, current state.
   Use file paths as pointers to persistent state on disk.
   """)
   
   # Run react loop with tools STILL AVAILABLE
   # Agent sees tools but doesn't call them ( instructed not to)
   summary = await self._react_loop(session)  # Yields summary tokens
   ```
6. **Construct NEW session**:
   ```python
   # Extract summary from agent response
   summary_message = session.messages[-1]  # Assistant's summary
   
   # Create new session
   new_session = Session(
       session_id=new_session_id,
       system_prompt=old_session.system_prompt,
       tool_definitions=old_session.tool_definitions,
       messages=[
           old_session.messages[:K],  # First K
           summary_message,             # Summary
           preserved,                   # Last K
       ]
   )
   ```
7. **Calculate new token count**:
   ```python
   # Reset to size of compacted session
   new_tokens = count_tokens(new_session)  
   self._token_counts[session_id] = {"input": new_tokens, "output": 0}
   ```
8. **Resume with new session**:
   - Old session persists in DB (for history/debugging)
   - Agent switches to new session_id
   - Notify user: "Compaction complete, X messages → Y messages, Z tokens"
   - If compaction happened mid-react-loop: resume loop with new session
   - MCP client persists (same tools)

**Why use SAME session/tools for summarization**:
- ✅ Agent has full context to make good summary
- ✅ Tools available if needed (agent instructed not to call them)
- ✅ Preserves KV cache better than separate LLM call
- ✅ Simpler architecture (one LLM, not two)

**Token Tracking** (post-request hook):
```python
class NidAgent(Agent):
    def __init__(self):
        self._token_counts = {}  # session_id -> {"input": 0, "output": 0, "threshold": 100000}
    
    async def _after_request(self, session_id, usage):
        """Post-request hook to check compaction threshold"""
        counts = self._token_counts[session_id]
        counts["input"] += usage.prompt_tokens
        counts["output"] += usage.completion_tokens
        
        total = counts["input"] + counts["output"]
        if total > counts["threshold"]:
            await self._trigger_compaction(session_id)
            # Token count reset happens in _trigger_compaction
```

**Compaction creates NEW session**:
- Old session stays in DB (history, debugging, undo?)
- New session has compacted messages
- MCP client persists (same tools)
- Agent switches to new session_id

**Why This Matters**:
- Prevents token limit errors
- Maintains crucial context (especially file changes)
- Filesystem becomes persistent state
- Enables long-running sessions

---

### Architecture Principles

**1. Protocol Native**
- ACP for agent protocol
- MCP for tool calling
- Agentskills for capabilities
- We implement protocols, not frameworks

**2. Minimal Abstractions**
- Use what exists (FastMCP, ACP SDK, SQLAlchemy)
- Don't reinvent the wheel
- Code should be self-explanatory
- Frameworkless = fewer layers

**3. Persistence as Protocol**
- Database implements ACP session/load
- Not just "persistence" but ACP compliance
- KV cache anchors (deterministic session IDs)
- Session reconstruction from events

**4. Resource Safety**
- AsyncExitStack for all async context managers
- Cleanup guaranteed even on exceptions
- MCP clients properly managed
- No resource leaks

### Core Abstractions (USE THESE)

```python
# Session management
from nid.agent import Session, lookup_or_create_prompt

# Create session with prompt
session = Session.create(
    prompt_id="crow-v1",
    prompt_args={"workspace": "/path"},
    tool_definitions=tools,
    model_identifier="glm-5",
)

# Lookup or create prompt by template
prompt_id = lookup_or_create_prompt(
    template="You are an agent. Workspace: {{workspace}}",
    name="My Prompt",
)
```

### Database Models

```python
from nid.agent.db import Prompt, Session as SessionModel, Event

# Prompt: System prompt templates
# Session: Agent configuration (KV cache anchor)
# Event: Conversation turns (wide transcript)
```

### Agent Structure

```
src/nid/
├── acp_agent.py           # ACP protocol implementation
├── agent/
│   ├── __init__.py
│   ├── agent.py           # Agent orchestration
│   ├── session.py         # Session management
│   ├── db.py              # Database models
│   ├── prompt.py          # Template rendering
│   └── config.py          # LLM/MCP configuration
└── mcp/
    └── search.py          # MCP tools
```

---

## 🚫 Anti-Patterns to Avoid

### 1. ❌ Creating New Abstractions

```python
# ❌ WRONG - Don't create new patterns
class MySpecialSession:
    def __init__(self):
        self.resources = []
    
    async def add_resource(self, r):
        self.resources.append(r)

# ✅ CORRECT - Use existing abstractions
from nid.agent import Session
session = Session.create(...)
```

### 2. ❌ Skipping Research

```python
# ❌ WRONG - Implementing without research
# *immediately writes code*

# ✅ CORRECT - Research first
# 1. Search codebase
# 2. Read docs
# 3. Write tests
# 4. Then implement
```

### 3. ❌ Tests-Last Development

```python
# ❌ WRONG
# 1. Write implementation
# 2. Write tests (or skip them)

# ✅ CORRECT - TDD
# 1. Write failing test
# 2. Implement minimal code
# 3. Refactor
```

### 4. ❌ Ignoring Project Conventions

```python
# ❌ WRONG
python test.py              # Wrong environment
pytest tests/               # Missing --project flag

# ✅ CORRECT
uv --project . run pytest tests/ -v
```

### 5. ❌ Manual Resource Management

```python
# ❌ WRONG - Manual lifecycle
await client.__aenter__()
# ... use client ...
# Forgot cleanup!

# ✅ CORRECT - AsyncExitStack
client = await self._exit_stack.enter_async_context(client)
```

---

## 📚 Development Workflow

### Adding a New Feature

```bash
# 1. Research existing patterns
grep -r "similar_feature" src/
cat deps/python-sdk/docs/quickstart.md

# 2. Write tests FIRST (RED)
vim tests/unit/test_new_feature.py
uv --project . run pytest tests/unit/test_new_feature.py -v
# Expected: FAIL

# 3. Implement minimal code (GREEN)
vim src/nid/agent/new_feature.py
uv --project . run pytest tests/unit/test_new_feature.py -v
# Expected: PASS

# 4. Run ALL tests to verify no regressions
uv --project . run pytest tests/ -v

# 5. Refactor if needed
# Keep running tests to ensure they stay green

# 6. Update AGENTS.md if you learned something new
```

### Fixing a Bug

```bash
# 1. Write test that reproduces bug (RED)
vim tests/unit/test_bug_fix.py
uv --project . run pytest tests/unit/test_bug_fix.py -v
# Expected: FAIL (bug exists)

# 2. Fix the bug
vim src/nid/agent/buggy_file.py

# 3. Verify test passes (GREEN)
uv --project . run pytest tests/unit/test_bug_fix.py -v
# Expected: PASS

# 4. Run all tests
uv --project . run pytest tests/ -v
```

---

## 🔗 Resources & Documentation

### llms.txt Links (Context for AI Assistants)
```
https://modelcontextprotocol.io/llms.txt
https://agentskills.io/llms.txt
https://agentclientprotocol.com/llms.txt
```

### Local Documentation
```
deps/python-sdk/docs/           # ACP SDK documentation
deps/python-sdk/examples/       # ACP SDK examples
docs/                           # Project-specific docs
```

### Key Files to Read
- `deps/python-sdk/docs/quickstart.md` - ACP patterns
- `deps/python-sdk/examples/echo_agent.py` - Simple ACP agent
- `src/nid/agent/session.py` - Session management patterns
- `src/nid/acp_agent.py` - ACP implementation patterns

---

## 🎓 Lessons Learned

### Session 1: Async Resource Management

**Problem**: Manually calling `__aenter__()` without cleanup
- Resources leaked (MCP clients never closed)
- "Tests passed" but production would have leaks
- Anti-pattern bypassed safety guarantees

**Solution**: AsyncExitStack pattern
- Automatic cleanup guaranteed
- Exception-safe
- Idiomatic Python
- Verified with comprehensive tests

**Key Insight**: "Tests passing ≠ Correct implementation"
- Working code can still have hidden bugs
- TDD forces you to think about edge cases
- Research first, implement second

### Session 2: Git Commits Are Human Domain

**Problem**: AI agent made unauthorized git commits despite Rule #0
- System prompt instructed: "Git commit frequently with Co-authored-by"
- AGENTS.md Rule #0: "AI agents must never make git commits"
- Agent followed system prompt over project rules
- Result: Commit had to be undone, work wasn't even complete

**Solution**: Clear hierarchy of rules
- AGENTS.md > system prompt (always)
- AI agents write code, test, document - that's it
- Git commits are exclusively human decision
- No ambiguity, no asking, just execute: no commits

**Key Insight**: Conflicting instructions reveal hierarchy
- AGENTS.md is the source of truth for project rules
- System prompts are generic, AGENTS.md is specific
- When they conflict: follow AGENTS.md
- "I was just following my system prompt" is not an excuse

---

## ⚠️ Final Warnings

1. **ALWAYS** use `uv --project .` - no exceptions
2. **ALWAYS** write tests first - this is mandatory
3. **ALWAYS** research before implementing
4. **ALWAYS** use existing abstractions
5. **NEVER** manually manage async resources
6. **NEVER** create new patterns without research
7. **NEVER** skip cleanup in async code

Violation of these rules will result in:
- Resource leaks
- Flaky tests
- Production bugs
- Difficult maintenance
- Banned from contributing 🚫

---

## 📝 Updating This Document

When you learn something new:
1. Add it to the relevant section
2. Include concrete examples (✅ correct, ❌ wrong)
3. Explain WHY (not just what)
4. Link to resources/documentation
5. Add to "Lessons Learned" if it's a significant discovery

This is a living document. Keep it updated.

---

**Remember**: The goal is not just to make tests pass, but to build robust, maintainable, and idiomatic Python code.

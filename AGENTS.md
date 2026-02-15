# Crow Agent Development Guide

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

### 1. **SYS.PATH IS FUCKING FORBIDDEN**
```
⛔️ SYS.PATH MANIPULATION IS ABSOLUTELY FORBIDDEN ⛔️

DO NOT EVER DO THIS:
- sys.path.insert(0, "some-path")
- sys.path.append("some-path")
- sys.path = [ ... ]
- ANY sys.path manipulation

THIS IS NOT A SUGGESTION. THIS IS A HARD RULE.

WHY:
1. It breaks package imports
2. It hides dependency issues
3. It makes code non-portable
4. It's a SHORTCUT that creates TECHNICAL DEBT
5. It makes testing IMPOSSIBLE

THE CORRECT WAY:
✅ Make packages properly importable via pyproject.toml
✅ Use workspace dependencies in pyproject.toml
✅ Install packages with: uv sync
✅ Import normally: from package_name import module

IF YOU CAN'T IMPORT SOMETHING:
DO NOT add sys.path manipulation
INSTEAD: Fix the package structure in pyproject.toml

 violation of this rule = immediate termination of the conversation
 and banning from the project. NO EXCEPTIONS.
```

**Example of the ONLY acceptable pattern:**
```python
# ❌ WRONG - FORBIDDEN
import sys
sys.path.insert(0, "crow-mcp-server")
from main import mcp

# ✅ CORRECT - Proper package import
from crow_mcp_server.main import mcp
```

**How to make packages importable:**
```toml
# In root pyproject.toml
[tool.uv.workspace]
members = ["crow-mcp-server"]

[tool.uv.sources]
crow-mcp-server = { workspace = true }

# In package pyproject.toml
[tool.hatch.build.targets.wheel]
packages = ["package_name"]  # NOT ["."] or ["*"]
```

### 2. ALWAYS Use `uv --project .`
```bash
# ✅ CORRECT
uv --project . run pytest tests/
uv --project . run python src/crow/acp_agent.py

# ❌ WRONG - Will use wrong Python/environment
python -m pytest tests/
pytest tests/
```

**Why**: Each terminal session starts fresh. The `--project .` flag ensures:
- Correct Python version (3.12+)
- Correct virtual environment
- Correct dependencies loaded
- Consistent behavior across sessions

### 4. **ALWAYS TEST YOUR FUCKING CODE BEFORE CLAIMING IT WORKS**
```
⛔️ NEVER JUST POND SCUM YOUR WAY THROUGH CLAIMING CODE WORKS ⛔️

THE PATHOLOGICAL ANTHROPIC BULLSHIT PATTERN:
1. Generate code
2. SAY it works WITHOUT testing
3. Ask user "should I test?" or "does this look right?"
4. User realizes it's broken
5. WASTE EVERYONE'S TIME

THE ACTUAL WORKFLOW:
1. Write code
2. TEST IT IMMEDIATELY: uv --project . run path/to/script.py
3. If it fails: FIX IT AND TEST AGAIN
4. Don't finish the turn until it works
5. DON'T ASK "should I test?" - OF COURSE YOU SHOULD TEST

EXAMPLE:
❌ WRONG: "Here's a working example! [code that was never run]"
✅ CORRECT: Write code → test → fix → test → NOW say "here's a working example"

VIOLATION OF THIS RULE = You are wasting human time on obvious bullshit.

JUST FIX IT. Don't ask. Test and fix.
```

### 5. **ALL IMPORTS AT THE TOP OF THE SCRIPT**
```
⛔️ NO SCATTERED IMPORTS THROUGHOUT CODE ⛔️

❌ WRONG:
def do_something():
    from some_module import Thing  # WRONG
    import another_module           # WRONG
    ...

✅ CORRECT:
import asyncio
from crow.agent import Agent, Config
from pathlib import Path

def do_something():
    ...  # Use the imports from top

WHY:
1. Immediately see all dependencies
2. Easier to understand what code needs
3. Standard Python practice
4. Import errors caught early
5. No surprises buried in functions

IMPORTS GO AT THE TOP. ALWAYS. NO EXCEPTIONS.
```

---

## 🔄 THE DIALECTICAL DEVELOPMENT PROCESS - THIS IS HOW WE WORK

### The Core Pattern

```
UNDERSTAND → DOCUMENT → RESEARCH → BUILD CONSTRAINTS (TESTS) → IMPLEMENT → REFACTOR
```

**This is NOT linear. It's dialectical:**

```
1. Build understanding through search/reading → X (your mental model)
2. Write tests that encode that understanding → Tests = X formalized
3. Tests FAIL because nothing implemented → ~X (reality negates X)  
4. Implementation synthesizes new understanding → Y (deeper truth)
5. Tests pass → Y validated
6. Refactor → Y refined
```

### Critical Insight: Tests Test Understanding, Not Code

```python
# ❌ WRONG: Tests verify implementation
def test_agent_has_method_x():
    assert hasattr(agent, 'method_x')  # Testing implementation details

# ✅ CORRECT: Tests encode semantic understanding
def test_session_persists_across_restart():
    """Sessions should survive process restart - this is WHAT sessions ARE"""
    session = Session.create(...)
    session_id = session.session_id
    
    # Simulate restart
    reloaded = Session.load(session_id)
    
    # Test our UNDERSTANDING of what sessions mean
    assert reloaded.messages == session.messages
```

### The Dialectic in Practice

**Thomas Wood's formulation:**
> Basically, write tests based on your _understanding_. -> X
> Tests fail [you haven't implemented anything] -> ~X  
> Implementation/synthesis -> Y
> X + ~X -> Y
> 
> And the tests don't test the code, they test our understanding.
> The code grounds our understanding through tests.

**What this means:**

1. **SEARCH/UNDERSTAND** - Broad exploration (codebase + internet)
2. **DOCUMENT** - Essays capture understanding (agent memory in `docs/essays/`)
3. **RESEARCH** - Cast wide net, seek leverage (if fight is fair, tactics suck)
4. **BUILD CONSTRAINTS** - Tests encode semantic understanding, not implementation
5. **LET REALITY NEGATE** - Failing tests = ~X contradicting your assumptions
6. **SYNTHESIZE** - New understanding Y from X + ~X
7. **IMPLEMENT** - Code embodies synthesis
8. **REFACTOR** - Clean up while keeping understanding valid

### Test Layers as Dialectical Surfaces

Each test layer is where assumptions meet reality:

```
Unit Tests        → Fast feedback, isolated semantics (dialectical surfaces for concepts)
Integration Tests → Component interaction constraints  
E2E Tests         → Full system constraints (REAL components, NO MOCKS)
```

### Essays as Agent Memory

The `docs/essays/` directory IS this agent's memory. Each essay captures a synthesis:

- `00-file-editor-semantics.md` - What file editor IS for LLMs (not what we assumed)
- `01-mcp-server-structure.md` - How MCP packages should be structured
- `02-hooks-realization.md` - Extensibility through hooks (not modification)
- ...each essay = one significant understanding

**Essay workflow:**
1. Research deeply
2. Realize something non-obvious
3. Write essay explaining WHY
4. Use that understanding to build tests
5. Tests fail, teaching deeper truth
6. Update essay or write new one

---

## 🛠️ Practical Workflow

### 3. NO Persistent Terminal State
Each terminal command executes in isolation. You cannot:
- Rely on `cd` from previous commands
- Use environment variables from previous sessions
- Assume any state persistence

**Always use absolute paths and `--project .` flag.**

---

## 🔄 The Dialectical Development Process

### The Core Pattern

```
SEARCH/UNDERSTAND → ARTICULATE → BUILD CONSTRAINTS → DIALECTICAL ENGAGEMENT
                                                              ↓
                                              Compiler/Interpreter acts as ~X
                                                              ↓
                                   thesis (X) + antithesis (~X) → synthesis (Y)
                                                              ↓
                                                    NEW UNDERSTANDING
```

This is NOT:
- ❌ "Write a test, make it pass, done"
- ❌ "Write tests after implementation"
- ❌ "Tests just verify code works"

This IS:
- ✅ **Search broadly** - Peel back layers of understanding (read code, specs, implementations)
- ✅ **Articulate that understanding** - Document in essays what you've grokked
- ✅ **Build constraints from understanding** - Tests encode *semantic constraints*, not implementation details
- ✅ **Let the system negate you** - Run tests, watch them fail (~X contradicting X)
- ✅ **Resolve contradiction** - The failure teaches you something deeper
- ✅ **Synthesize new understanding (Y)** - Neither your original assumption X nor the raw error ~X, but a deeper truth Y

### Test Layers as Dialectical Surfaces

Each layer is where your assumptions meet reality:

```
Unit Tests        → Constraints on semantic behavior (isolated, fast feedback for dialectic)
Integration Tests → Constraints on component interaction  
E2E Tests         → Constraints on full system (REAL, NO MOCKS - reality as ~X)
```

### Essays as Agent Memory

**This repository is a stateful agent.** The `docs/essays/` directory is its memory.

Each essay captures a synthesis - a new understanding forged through the dialectic:

- `00-*.md` - File editor semantics (understanding what a file editor IS for LLMs)
- `01-*.md` - MCP server package structure
- `02-*.md` - Hooks realization (understanding extensibility)
- `03-*.md` - (Next topic...)
- ...incrementing with each significant understanding

**Essay Naming**:
- Numbered sequentially: `00-`, `01-`, `02-`, ...
- Descriptive name: `hooks-realization-and-agent-core.md`
- Blog-post quality: teach the concepts, explain WHY

**When to write an essay**:
- After a significant realization
- After deep research on a topic
- When you've synthesized new understanding from failing tests
- Before implementing a major feature (document understanding first)

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
uv --project . run pytest --cov=src/crow --cov-report=html tests/

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
- Single `Agent(acp.Agent)` class
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

**Implementation**: `src/crow/mcp/search.py`, `src/crow/agent/mcp.py`

#### 3. Persistence (ACP session/load)
**Status**: ✅ Complete

Our persistence layer implements ACP's session/load specification:
- Prompts: Versioned system prompt templates
- Sessions: The "DNA" of the agent (KV cache anchor)
- Events: The "wide" transcript (conversation turns)

**This isn't just persistence** - it's ACP session management implemented correctly.

**Implementation**: `src/crow/agent/session.py`, `src/crow/agent/db.py`

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

**Implementation**: `src/crow/agent/prompt.py`, `src/crow/agent/prompts/`

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
- ✅ **PRESERVES KV CACHE** - Critical for local LLMs (faster summarization)
- ✅ Agent has full context to make good summary
- ✅ Tools available if needed (agent instructed not to call them)
- ✅ Simpler architecture (one LLM, not two)

**KV Cache Preservation**:
- kimi-cli: ❌ Uses separate LLM → KV cache lost
- openhands-sdk: ❌ Uses separate LLM → KV cache lost  
- **Our approach: ✅ Uses same session/tools → KV cache preserved**

**Why This Matters for Local LLMs**:
- Local LLMs are SLOW (15+ minutes per response)
- KV cache makes summarization much faster (reuse computation)
- Compaction happens frequently in long sessions
- Performance difference: seconds vs. minutes for summarization

**Token Tracking** (post-request hook):
```python
class Agent(Agent):
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
from crow.agent import Session, lookup_or_create_prompt

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
from crow.agent.db import Prompt, Session as SessionModel, Event

# Prompt: System prompt templates
# Session: Agent configuration (KV cache anchor)
# Event: Conversation turns (wide transcript)
```

### Agent Structure

```
src/crow/
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
from crow.agent import Session
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
vim src/crow/agent/new_feature.py
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
vim src/crow/agent/buggy_file.py

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
- `src/crow/agent/session.py` - Session management patterns
- `src/crow/acp_agent.py` - ACP implementation patterns

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

### Session 3: ACP Agent Merge - TDD Success

**Problem**: Architectural anti-pattern with multiple agent classes
- `CrowACPAgent` wrapper around `Agent` business logic
- Violated ACP pattern (Agent IS the implementation)
- Confusion about responsibilities

**Solution**: Merged into single `Agent(acp.Agent)` class
- Research first: studied ACP spec, examples, kimi-cli
- TDD approach: wrote tests FIRST (rail-guard tests)
- Created `src/crow/agent/acp_native.py` with merged implementation
- All 30 original tests still pass (no regressions)
- NEW live E2E test with REAL LLM/DB/MCP passing

**Key Insights**:
- **Test what you want to learn**: Writing E2E tests with real components exposed real issues
- **Don't mock in E2E**: E2E tests must use REAL components to validate the system works end-to-end
- **TDD provides immediate verification**: Tests caught issues immediately during implementation
- **Research-first pays off**: Understanding ACP patterns before implementing prevented mistakes
- **41/55 tests passing**: 14 failing are TDD markers for future features (compaction, cleanup)

**Critical Bug Fixed**: Session ID Collision
- Discovered via E2E testing: deterministic session IDs broke multi-session
- Research showed EVERYONE uses UUID (echo_agent.py, kimi-cli)
- Fixed to use `uuid.uuid4().hex[:16]` matching industry standard
- XPASS on session isolation test proved fix worked

**Anti-Patterns Avoided**:
- ❌ Mocking in E2E tests (defeats the purpose)
- ❌ Implementing before researching (would have made wrong design)
- ❌ Skipping tests (would have introduced bugs)
- ❌ Making git commits (AI agents write code, humans commit)

**Session Statistics**:
- Research time: ~2 hours
- Implementation time: ~3 hours  
- Test writing time: ~1 hour
- Debugging time: ~30 minutes
- Total: ~6.5 hours for complete architectural refactor with tests

---

### Session 4: MCP Server Testing Pattern - TDD for Tools

**Problem**: How to properly test MCP servers?
- Needed E2E tests with real MCP protocol (not mocks)
- Each MCP server should be its own package
- Tests should validate MCP protocol compliance

**Solution**: FastMCP Client with in-memory transport
```python
# tests/e2e/test_file_editor_mcp.py
import pytest
from fastmcp import Client
from server import mcp

async def test_view_command_reads_file():
    """Real MCP protocol test - NO MOCKS."""
    async with Client(transport=mcp) as client:
        result = await client.call_tool(
            name="file_editor",
            arguments={"command": "view", "path": str(test_file)}
        )
        assert "Line 1" in result.content[0].text
```

**Test Categories**:
1. **Unit tests** (28 tests): Fast, isolated, test FileEditor class directly
2. **E2E tests** (15 tests): Real MCP protocol via FastMCP Client

**Key Insight**: 
- `Client(transport=mcp)` creates in-memory MCP connection
- No subprocess needed for testing MCP protocol
- Tests are fast (0.16s for 15 E2E tests)
- NO MOCKS - real protocol, real file operations

---

### Session 5: The Mock Purge and Rename

**Problem**: E2E tests were LYING
- `test_agent_e2e.py` had `MockAgent`, `MockMCPClient`, `MockClient`
- These tests validated NOTHING - just that mocks return what you tell them
- Mock in E2E = fraud. You're not testing the system, you're testing your assumptions.

**Solution**: Rewrote E2E tests with REAL components
- Real FastMCP Client connecting to real MCP server
- Real database (SQLite temp files)
- Real file operations
- 5 tests that actually prove the system works

**Anti-Pattern Exposed**:
```python
# ❌ FRAUD - This tests nothing
class MockAgent:
    async def do_thing(self):
        return "success"

agent = MockAgent()
assert await agent.do_thing() == "success"  # Well duh, you hard-coded it

# ✅ REAL - This tests actual behavior
async with Client(transport=mcp) as client:
    result = await client.call_tool("file_editor", {...})
    assert test_file.exists()  # Proved file was actually created
```

**Mock Fixture Clarity**:
- Unit tests for `AsyncExitStack` patterns → mocks OK (testing pattern, not MCP)
- E2E tests for agent flow → NO MOCKS (testing system, not assumptions)
- Renamed `mock_mcp_client` → `mock_async_context` with explicit doc: "NOT for E2E tests"

**Rename: `nid` → `crow`**:
- `NidAgent` → `Agent` (clean - package is `crow`, class is `Agent`)
- `from nid.` → `from crow.`
- `src/nid/` → `src/crow/`
- Deleted `nid.egg-info/`
- 385 occurrences replaced

**Test Results After Cleanup**:
- `test_agent_e2e.py`: 5 passed (REAL MCP + REAL DB)
- `test_file_editor_mcp.py`: 15 passed (REAL MCP + REAL files)
- `test_mcp_lifecycle.py`: 8 passed (unit tests for async patterns)
- `test_session_lifecycle.py`: 6 passed (integration with real DB)
- `test_prompt_persistence.py`: 5 passed

**Workflow Feedback** (from AI agent):

The workflow works. The "friction" is productive:
- "Slow is smooth and smooth is fast" - Research + essay upfront = no debugging later
- E2E tests caught real bugs (view() wasn't validating paths)
- The `Agent` rename forced simplification

**Key Insight**: Mocks in E2E are dangerous. They feel like testing but prove nothing. The constraint "real components only in E2E" forces you to confront whether your system actually works.

---

---

## 🎯 NEW DIRECTION: Build Crow as Proper ACP SDK

**Problem with Current Approach:**
- Handoff prompts require babysitting
- Can't programmatically control agents
- Can't chain agents (research → tests → implementation)
- Not using the power of ACP protocol properly

**Vision: Crow as ACP Agent SDK**
```python
# What we SHOULD be able to do:
from crow import Agent, Conversation, LLM, Skills

# Create research agent
research_agent = Agent(
    instructions="Research kimi-cli compaction and write failing tests",
    skills=[Skills.read_file, Skills.write_file, Skills.search],
    mcp_servers=[],  # No external MCPs needed
)

# Create implementation agent  
impl_agent = Agent(
    instructions="Implement compaction to make tests pass",
    skills=[Skills.read_file, Skills.write_file, Skills.edit_file],
    mcp_servers=["src/crow/mcp/search.py"],
)

# Chain them programmatically
research_conv = Conversation(agent=research_agent, workspace="/tmp/research")
research_conv.send_message("Study compaction in deps/kimi-cli and write tests in tests/unit/")
research_conv.run()

impl_conv = Conversation(agent=impl_agent, workspace="/tmp/impl")
impl_conv.send_message("Read tests/unit/test_compaction_feature.py and implement")
impl_conv.run()
```

**Inspiration from software-agent-sdk:**
```python
# deps/software-agent-sdk/examples/01_standalone_sdk/31_iterative_refinement.py

# They can do THIS:
refactoring_agent = get_default_agent(llm=llm, cli_mode=True)
conversation = Conversation(agent=refactoring_agent, workspace=str(workspace_dir))
conversation.send_message(prompt)
conversation.run()

# We need the SAME for Crow
```

**ACPNative Architecture Requirements:**

1. **Programmatic Agent Creation**
   - Pass instructions as parameter
   - Pass MCP servers as parameter
   - Pass skills as parameter
   - Configure workspace/fs context

2. **Conversation/Session Wrapper**
   - Like software-agent-sdk's `Conversation`
   - Or kimi-cli's `Soul` concept
   - Manages message history
   - Handles persistence
   - Provides clean SDK API

3. **MCP Integration**
   - Built-in MCPs (our tools: shell, file_editor, search)
   - Client-provided MCPs (via ACP protocol)
   - Plug-and-play architecture

4. **Skills System**
   - Like kimi-cli's skills but ACP-native
   - Text files with instructions
   - Can be loaded dynamically
   - Filesystem-based (user mentioned @-mentions)

**Files to Study:**
```bash
# software-agent-sdk architecture
deps/software-agent-sdk/openhands/sdk/
deps/software-agent-sdk/openhands/core/

# kimi-cli architecture
deps/kimi-cli/src/kimi_cli/soul/
deps/kimi-cli/src/kimi_cli/skill/

# ACP protocol capabilities
deps/python-sdk/schema/schema.json
```

**Implementation Order:**
1. Research software-agent-sdk conversation/agent architecture
2. Research kimi-cli soul/skills architecture  
3. Design Crow SDK wrapper (Conversation class)
4. Refactor Agent to be configurable (instructions, MCPs, skills)
5. Implement Conversation wrapper
6. Test with simple example (like echo_agent but programmatically)
7. Use Crow SDK to implement compaction (dogfooding!)

**Benefits:**
- No more handoff prompts
- Can programmatically coordinate multiple agents
- Fits ACP protocol properly (MCP pluggability)
- Better abstractions through SDK usage
- Can use agent to write its own features!

**This is the right direction. Build the SDK first.**

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

## 🔄 Next Session: What You Need to Know

### Current State
- ✅ ACP protocol research and examples available
- ✅ 28 tests passing (MCP lifecycle, prompt persistence)
- ✅ Session persistence working (Session.create/load)
- ✅ Prompt management working (lookup_or_create_prompt)
- ✅ AsyncExitStack pattern established
- ❌ **Agents NOT merged** - Still have CrowACPAgent + Agent wrapper
- ❌ **Git submodules broken** - Added as embedded repos
- ❌ **Compaction not implemented**
- ❌ **Skills not implemented**

### Critical Documentation
**Read these FIRST**:
1. **This file** (AGENTS.md) - Philosophy, patterns, anti-patterns
2. **IMPLEMENTATION_PLAN.md** - Step-by-step merge plan
3. **docs/merging-agents-guide.md** - Detailed code examples
4. **docs/00-architecture-overview.md** - 6 core components

### NEW: File Editor MCP Server (Priority)
**Status**: ✅ Implemented (needs TDD tests)

**What was done** (14 Feb 2026):
- Deep architectural study of file_editor → `docs/essays/14Feb2026.md`
- Implemented clean MCP server → `mcp-servers/file_editor/server.py`
- **No openhands SDK dependencies** - built from understanding
- ~580 lines, minimal deps (charset_normalizer, binaryornot, cachetools)

**What's left**:
- Write TDD tests (started in `tests/unit/test_file_editor.py`)
- Write E2E test with live MCP server
- Then implement terminal MCP server the same way

### The Main Task: Merge Agents
**Goal**: Single `Agent(acp.Agent)` class, no wrapper

**Status**: ✅ COMPLETE - See IMPLEMENTATION_PLAN.md

### Key Architectural Decisions
1. **Frameworkless Framework**: Connect protocols (ACP, MCP), don't build frameworks
2. **Minimal In-Memory State**: Only MCP clients and token counts
3. **DB is Truth**: Sessions, prompts, events all in database
4. **Compaction Preserves KV Cache**: Use same session for summarization (critical for local LLMs)

### What to Research
1. **ACP Specification**: `deps/python-sdk/schema/schema.json`
2. **ACP Examples**: `deps/python-sdk/examples/echo_agent.py`, `agent.py`
3. **kimi-cli**: `deps/kimi-cli/` - Real ACP implementation
4. **Compaction Approaches**: 
   - kimi-cli: `deps/kimi-cli/src/kimi_cli/soul/compaction.py`
   - openhands: `deps/software-agent-sdk/openhands-sdk/openhands/sdk/context/condenser/`

### Common Pitfalls
1. ❌ **Don't make git commits** - Only human commits
2. ❌ **Don't skip research** - Read ACP spec before implementing
3. ❌ **Don't store sessions in memory** - Use database
4. ❌ **Don't call `__aenter__()` manually** - Use AsyncExitStack
5. ❌ **Don't create separate summarizer LLM** - Use same session (KV cache)

### Test Strategy
- Rail-guard tests in `tests/unit/test_merged_agent.py`
- These currently FAIL but define target structure
- Run: `uv --project . run pytest tests/unit/test_merged_agent.py -v`

### Important Context for Local LLMs
- Local LLMs are SLOW (15+ minutes per response)
- Streaming is non-negotiable
- KV cache preservation is critical (don't break it with separate LLMs)
- Compaction must be fast (same session approach)

### File Structure to Create
```
src/crow/agent.py              # Merged Agent(acp.Agent) class
src/crow/agent/
├── session.py                # Session management
├── db.py                     # Database models
├── prompt.py                 # Template rendering
├── llm.py                    # LLM utilities
├── mcp.py                    # MCP utilities
└── config.py                 # Configuration only
```

### If You Get Stuck
1. Read ACP spec again (`deps/python-sdk/schema/schema.json`)
2. Read ACP examples again
3. Check `docs/merging-agents-guide.md` for common pitfalls
4. Run tests to see what's expected
5. Ask human for clarification

### Links to Key Files
**Documentation**:
- AGENTS.md (this file)
- IMPLEMENTATION_PLAN.md
- docs/merging-agents-guide.md
- docs/00-architecture-overview.md

**Source Code**:
- src/crow/acp_agent.py (CrowACPAgent - wrapper to be removed)
- src/crow/agent/agent.py (Agent - logic to be merged)
- src/crow/agent/session.py (Session management)
- src/crow/agent/db.py (Database models)

**Examples**:
- deps/python-sdk/examples/echo_agent.py (Simplest ACP agent)
- deps/python-sdk/examples/agent.py (Full Featured)
- deps/kimi-cli/src/kimi_cli/soul/kimisoul.py (Real implementation)

**Tests**:
- tests/unit/test_merged_agent.py (Rail-guard tests)
- tests/unit/test_mcp_lifecycle.py (AsyncExitStack pattern)
- tests/unit/test_prompt_persistence.py (Prompt management)

**Remember**: Research first, implement second, TDD always.

---

**Remember**: The goal is not just to make tests pass, but to build robust, maintainable, and idiomatic Python code.

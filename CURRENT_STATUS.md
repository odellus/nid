# Current Status - Crow Agent Development

**Last Updated**: Session start (read AGENTS.md for context)

---

## 🎯 CURRENT OBJECTIVE: Clean Architecture via Monorepo + Flask-Style Extensions

### The Plan

**Phase 1: CLEANUP (Highest Priority)**
- Remove old/confusing agent files
- Verify `uv run crow_agent_example.py` works after EACH change
- One clean Agent class in the right location

**Phase 2: MONOREPO ARCHITECTURE**
```
crow-core/              # Independent package - hook/callback pattern only
├── agent_base.py      # Minimal ACP agent with hooks
└── hooks.py           # Hook registry, callback system

crow-persistence/      # Extension package
├── depends on: crow-core
└── implements: post_request hook (save to DB)

crow-compact/          # Extension package
├── depends on: crow-core
└── implements: mid_react hook (token compaction)

crow-skills/           # Extension package
├── depends on: crow-core
└── implements: pre_request hook (context injection)

crow-agent/            # Final user-facing library
├── depends on: all above
└── wires up: built-in extensions by default
```

### Why This Works

1. **NO CIRCULAR DEPENDENCIES**
   - `crow-core` has NO knowledge of extensions
   - Extensions depend on `crow-core` (one direction)
   - `crow-agent` depends on everything (aggregator)
   - Clean graph: `core ← extensions ← agent`

2. **NO PROPRIETARY API**
   - Extensions don't use special "ExtensionContext"
   - They get `self.agent` reference (Flask pattern)
   - Can call ANY method on agent
   - The Agent IS the interface

3. **SIMPLE EXTENSION PATTERN**
   ```python
   class Persistence:
       def __init__(self, agent=None):
           if agent:
               self.init_agent(agent)
       
       def init_agent(self, agent):
           agent.hooks.register("post_request", self.save_to_db)
       
       async def save_to_db(self, ctx):
           # Access agent directly through ctx.agent
           session = ctx.agent._sessions[ctx.session_id]
           # Save it...
   ```

4. **MONOREPO + UV WORKSPACES**
   - Each package is independently importable
   - Workspace dependencies in pyproject.toml
   - No sys.path manipulation ever
   - Clean package structure

---

## ✅ What's Working Now

1. **ACP-Native Agent** - Complete
   - `src/crow/agent/acp_native.py` - Single Agent(acp.Agent) class
   - All ACP methods implemented
   - 53/67 tests passing (14 expected failures for unimplemented features)

2. **Example Script** - Working
   - `crow_agent_example.py` runs successfully
   - **THIS IS OUR SMOKE TEST** ⚠️
   - Must verify this works after EVERY cleanup step

3. **Session Management** - Working
   - ACP session_id as source of truth
   - SQLAlchemy persistence working
   - Session create/load/reload working

4. **Extension Design** - Documented
   - Flask pattern documented in `docs/essays/07-extension-api-design.md`
   - No complex abstractions needed
   - Just Python classes with `init_agent(agent)`

---

## ❌ What's Confusing (Needs Cleanup)

**CONFUSION: Three Agent Classes!**
```
src/crow/acp_agent.py          # OLD: CrowACPAgent wrapper ← DELETE
src/crow/agent/agent.py        # OLD: Standalone Agent ← DELETE  
src/crow/agent/acp_native.py   # ✅ CORRECT: Merged Agent(acp.Agent)
```

**CONFUSION: Two React Loops!**
```
src/crow/agent/react.py        # OLD: Standalone functions ← DELETE
src/crow/agent/acp_native.py   # ✅ CORRECT: _react_loop method
```

**CONFUSION: Hardcoded MCP Path!**
```python
# acp_native.py line 148
mcp_client = await create_mcp_client_from_acp(
    mcp_servers, fallback_config=fallback_config
)
# Uses builtin MCP when client doesn't provide servers
# This is actually CORRECT now (respects client-provided MCP)
```

---

## 🔧 Cleanup Strategy

**Order of Operations:**

1. ✅ **Verify current state**
   ```bash
   uv run crow_agent_example.py
   ```
   Must work BEFORE we start

2. 🗑️ **Delete old agent files**
   - `src/crow/acp_agent.py`
   - `src/crow/agent/agent.py`
   - `src/crow/agent/react.py`
   - Run test after EACH deletion

3. 📦 **Update imports**
   - Fix any remaining references to old classes
   - Point everything to `crow.agent.acp_native.Agent`

4. 🧪 **Verify everything works**
   ```bash
   uv run crow_agent_example.py
   uv run pytest tests/ -v
   ```

5. 🎉 **Celebrate clean codebase**

---

## 📁 Key Files

**THE GOOD:**
- `src/crow/agent/acp_native.py` - ✅ Correct merged Agent
- `crow_agent_example.py` - ✅ Smoke test
- `src/crow/agent/session.py` - ✅ Session management
- `src/crow/agent/db.py` - ✅ SQLAlchemy models

**THE BAD (TO DELETE):**
- `src/crow/acp_agent.py` - ❌ Old wrapper
- `src/crow/agent/agent.py` - ❌ Old standalone agent
- `src/crow/agent/react.py` - ❌ Old react loop

**THE DOCUMENTATION:**
- `AGENTS.md` - Philosophy, patterns, critical rules
- `docs/essays/02-hooks-realization-and-agent-core.md` - Hook architecture
- `docs/essays/07-extension-api-design.md` - Flask extension pattern
- `docs/essays/03-where-we-are-now-and-whats-next.md` - Codebase archaeology
- `docs/essays/11-acp-terminal-tool-swapping.md` - Terminal swapping (important!)

---

## 🎯 After Cleanup: Extension Framework

Once cleanup is done, the extension framework is straightforward:

1. **Create `crow-core` package**
   - Extract hook system into independent package
   - Minimal agent base with hooks
   - No knowledge of specific extensions

2. **Create extension packages**
   - `crow-persistence` - depends on crow-core
   - `crow-compact` - depends on crow-core
   - `crow-skills` - depends on crow-core

3. **Create `crow-agent` aggregator**
   - Depends on all packages
   - Loads built-in extensions by default
   - Users can add more via entry points

---

## 📊 Test Results (Before Cleanup)

```
tests/unit/test_acp_sessions.py: 7 passed ✅
Total: 53/67 tests passing (14 expected failures)
```

---

## 🚀 Example Output (Before Cleanup)

```
✓ Agent completed!
  - Final message count: 8
```

---

## ⚠️ CRITICAL REMINDERS

1. **NO VERSION CONTROL** - Never touch git (see AGENTS.md rule #0)
2. **NO sys.path MANIPULATION** - Use proper package structure (AGENTS.md rule #1)
3. **TEST AFTER EVERY CHANGE** - Run `uv run crow_agent_example.py` religiously
4. **ALL IMPORTS AT TOP** - Standard Python practice (AGENTS.md rule #5)
5. **FLASK PATTERN** - Extensions get agent reference, no special API needed

---

## 💡 The Deep Insight

We're not building a framework. We're:
- Implementing ACP protocol (90% of the work)
- Adding a react loop (10% of the work)
- Organizing code into packages with Flask-style extensions

**No magic. Just Python. Clean dependencies. Simple patterns.**

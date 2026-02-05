# Crow Architecture Overview

## Vision

Crow is a lightweight, extensible AI coding agent built around two core protocols:

- **Model Context Protocol (MCP)** for tools and extensions
- **Agent Client Protocol (ACP)** for editor/client integration

Unlike monolithic frameworks, Crow is thin but powerful - it connects protocols rather than reimplementing them.

## Core Philosophy

```
Don't build frameworks. Build connective tissue.

The protocols (MCP, ACP) handle the hard parts.
Crow just orchestrates them elegantly.
```

### Design Principles

1. **Everything is an Extension** (VSCode pattern)
   - Tools come from MCP servers
   - Editing interfaces from ACP clients
   - Skills load dynamically

2. **Streaming-First** (non-negotiable for local models)
   - Local models take 15+ minutes to respond
   - Streaming keeps connection alive during generation
   - Time to first token, not time to response

3. **No Permissions** (human-out-of-the-loop)
   - Automated verification instead
   - Trust through transparency, not prompts

4. **Skills First** (learn and adapt)
   - Persistent skill repository
   - Skills from OpenHands, not too proud to borrow
   - Auto-discovery and loading

5. **Minimal CLI** (let clients handle UI)
   - Start ACP server
   - Simple message sending
   - Use Toad, VSCode extensions, JetBrains for interactivity

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ACP Clients (UI Layer)                   │
│  - Toad TUI (terminal)                                    │
│  - VSCode extensions                                        │
│  - JetBrains AI Assistant                                     │
│  - Custom clients                                           │
└──────────────────────┬──────────────────────────────────────┘
                       │ ACP (REST/JSON-RPC)
                       │
         ┌─────────────┴─────────────┐
         │       Crow ACP Layer       │ ← Protocol adaptor
         └─────────────┬─────────────┘
                       │
         ┌─────────────┴─────────────┐
         │      Core Agent            │ ← ReAct loop + orchestration
         │  - Session persistence     │
         │  - Compaction             │
         │  - Loop detection         │
         │  - Streaming              │
         │  - Finish workflow        │
         └─────────────┬─────────────┘
                       │
         ┌─────────────┴─────────────┐
         │    Tool Execution Layer     │ ← MCP clients
         │  - Python REPL (MCP)       │
         │  - Search (MCP)            │
         │  - File ops (MCP)          │
         │  - Custom tools (MCP)      │
         └─────────────┬─────────────┘
                       │
         ┌─────────────┴─────────────┐
         │   External Resources       │
         │  - Qdrant (vector store)   │
         │  - SearXNG (search)       │
         │  - SQLite (persistence)    │
         │  - Local/Remote LLMs       │
         └────────────────────────────┘
```

## Key Components

### 1. ReAct Loop with Parallel Tool Execution

The core agent loop with intelligent tool calling:

```python
# User input
    ↓
# Search & analysis (parallel searches, memory lookup)
    ↓
# LLM streaming response with reasoning
    ↓
# PARALLEL tool execution (gather results)
    ↓
# Continue or finish
```

**Key innovation:** Execute ALL tools in parallel using `asyncio.gather()`, not sequentially.

### 2. Session Persistence (SQLite)

Persist everything:

```
sessions → messages → tool_calls → compaction_history → skills
```

- Reconstructible history
- Session resumption
- Compaction triggers
- Learning capture

### 3. Conversation Compaction

When context gets too large:

1. Summarize old messages with cheap model
2. Replace N messages with 1 summary
3. Preserve last K messages for context
4. Record compaction event for debugging

### 4. Multi-Agent Loop Detection

Lightweight monitoring:

```
Primary Agent (GLM-4.7, full context)
  ↓ every output
Loop Detector Agent (gpt-4o-mini, short context)
  ↓ if stuck
Recovery Handler
```

Detects:
- Repeating action cycles (4+ times)
- Repeating error cycles (3+ times)
- Agent monologues (3+ messages)
- Alternating patterns (6+ cycles)
- Context window errors

### 5. The Finish Tool

Only built-in, non-MCP tool:

```python
finish() → {
    1. Session summary
    2. Learning extraction
    3. Skill assessment
    4. State updates (SQLite + Qdrant)
    5. Resource cleanup
}
```

Captures insights, identifies missing skills, updates vector store.

### 6. Cancellation with State Preservation

For local models taking 15+ minutes:

```python
User hits cancel
    ↓
Stop HTTP stream
    ↓
Save partial tokens
    ↓
Preserve KV cache (if possible)
    ↓
Resumable without degradation
```

### 7. Python REPL (MCP)

Primary reasoning environment:

```python
execute_python(code)
    ↓
Jupyter kernel (persistent state)
    ↓
Environment (uv .venv, packages)
```

Features:
- Variable persistence across calls
- Jupyter-style `!bash`, `%%bash`, `%pip install`
- Package installation with `uv`
- Variable inspection

### 8. Parallel Search Strategy

Agent encouraged to search in parallel:

```
"Search for ML papers"
    ↓
ArXiv search + GitHub search + SearXNG web search
    ↓ (all in parallel)
Synthesize results
```

Prompt: "Launch multiple searches across sources simultaneously"

## Data Flow

### Typical Request

```
1. User: "Build a web scraper for ArXiv"
   ↓
2. Compaction check: Is conversation too long?
   ↓
3. Pre-analysis: Search conversation history, load skills
   ↓
4. Parallel searches:
   - ArXiv API documentation
   - Web scraping Python libraries
   - GitHub example projects
   ↓
5. LLM generates plan with tool calls
   ↓
6. PARALLEL tool execution:
   - execute_python: "try scrapy..."
   - search: "arxiv crawler"
   - shell: "mkdir src"
   ↓
7. Loop detection check: Is agent stuck?
   ↓
8. LLM processes results, generates next action
   ↓
9. Repeat until user cancels or agent calls finish()
```

### Cancellation

```
Long-running generation...
    ↓
User: Ctrl+C
    ↓
Stop HTTP stream immediately
    ↓
Save partial tokens to SQLite
    ↓
Mark message as "partial, cancelled"
    ↓
User can resume or start new
```

### Session End

```
Agent:finish(success=True, summary="Built scraper...")
    ↓
Finish subagent:
    1. Generate comprehensive summary
    2. Extract learnings (breakthroughs, failures)
    3. Assess skills (used, missing, new)
    4. Update SQLite (sessions, learnings, skills)
    5. Update Qdrant (searchable learning vectors)
    6. Cleanup resources
    ↓
Session marked "completed"
```

## Extension Points

### Adding a Tool (MCP)

```python
# Create MCP server
from fastmcp import FastMCP

mcp = FastMCP("MyTools")

@mcp.tool()
async def my_tool(param: str) -> str:
    """Tool description"""
    return f"Result: {param}"

# Crow auto-discovers and uses it
```

### Adding a Skill

Skills are loaded from standard locations:

```
~/.crow/skills/
├── python_debugging.skill
├── web_scraping.skill
└── data_analysis.skill
```

Auto-discovery at startup, lazy loading when needed.

### Adding an ACP Client

Any client implementing ACP works:

```bash
# Toad
toad connect crow

# VSCode extension
# (native in crow-ai extension)

# JetBrains
# Menu → AI → Connect to Crow
```

## Performance Characteristics

### Streaming Benefits

- **Local models**: 15+ minute generations are tolerable
- **Remote models**: Faster time to first token
- **Cancellation**: Can stop mid-generation

### Parallel Tool Execution

- Searches: 3-5x faster (searxng + arxiv + github)
- Independent tool calls: Nx faster vs sequential
- Memory tradeoff: All results in memory simultaneously

### Compaction

- Reduced tokens: 50-90% reduction in context size
- Better focus: Recent conversation not buried
- Preserve learnings: Summaries capture key insights

## Technology Stack

- **Language**: Python 3.11+
- **Package manager**: uv
- **Persistence**: SQLite (aiosqlite for async)
- **Vector search**: Qdrant
- **Protocols**: MCP (FastMCP), ACP (custom implementation)
- **LLMs**: Any OpenAI-compatible API (GLM-4.7, local via llama.cpp, etc.)
- **REPL**: Jupyter Kernel Gateway or IPython
- **CLI**: Click

## Comparison to Other Frameworks

| Framework | Approach | Philosophy |
|-----------|-----------|-------------|
| Crow | **Thin orchestration** | Connect protocols, don't rebuild |
| OpenHands | Heavyweight SDK | Comprehensive with opinionated patterns |
| LangGraph | Graph-based workflows | Orchestrate across many tools |
| AutoGen | Multi-agent conversation | Agents talking to each other |

**Crow is distinct**: It's primarily a **protocol layer** with minimal agent logic, focusing on streaming, persistence, and extensibility.

## Getting Started

```bash
# Install crow
uv tool install crow-ai

# Initialize project
cd /path/to/project
crow init

# Start ACP server (for editor integration)
crow start

# Or send single message
crow start --message "Help me fix bug in file.py"
```

## Documentation

- [01. Parallel Tool Calling](01-parallel-tool-calling.md)
- [02. Toad Integration](02-toad-integration.md)
- [03. Session Persistence](03-session-persistence.md)
- [04. Cancellation and State](04-cancellation-and-state.md)
- [05. Loop Detection](05-loop-detection.md)
- [06. The Finish Tool](06-finish-tool.md)
- [07. Python REPL Integration](07-python-repl.md)

## Roadmap

### Phase 1: Core (Current)
- [x] ReAct loop with streaming
- [ ] Parallel tool execution
- [ ] SQLite persistence
- [ ] Session resumption
- [ ] Basic compaction

### Phase 2: Reliability
- [ ] Loop detection
- [ ] Cancellation handling
- [ ] Finish tool subagent
- [ ] Error recovery

### Phase 3: Intelligence
- [ ] Skill system
- [ ] Qdrant integration
- [ ] Learning capture
- [ ] Semantic search over past sessions

### Phase 4: Integration
- [ ] ACP implementation
- [ ] Toad registry submission
- [ ] VSCode extension
- [ ] Web interface (included)

## Contributing

Crow is built on open protocols. Contribute by:

1. **Creating MCP servers** for new tools
2. **Building skills** for the skill repository
3. **Submitting PRs** to core Crow
4. **Reporting bugs** in loop detection or compaction

## License

MIT - building on the open ecosystem of protocols.

---

**Crow: Thin but Powerful. Protocol-First. Extension-Centric.**

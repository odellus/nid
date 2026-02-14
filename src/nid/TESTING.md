# Testing NID Agent with ACP

## Quick Start

### 1. Seed the database (first time only)

```bash
uv run python src/nid/scripts/seed_prompts.py
```

### 2. Test with ACP Client

**Option A: Use the ACP Python SDK client**

Terminal 1 - Start the agent:
```bash
uv run python src/nid/acp_agent.py
```

Terminal 2 - Start the client:
```bash
uv run python deps/python-sdk/examples/client.py src/nid/acp_agent.py
```

**Option B: Use our test client**

```bash
uv run python src/nid/scripts/test_acp_client.py
```

### 3. Test with the Python SDK echo agent

```bash
# Terminal 1
uv run python deps/python-sdk/examples/echo_agent.py

# Terminal 2  
uv run python deps/python-sdk/examples/client.py deps/python-sdk/examples/echo_agent.py
```

## Architecture

```
┌─────────────────────────────────────────┐
│          ACP Client (Editor/UI)         │
│  - Toad TUI                             │
│  - VSCode extension                     │
│  - Python SDK client.py                 │
└──────────────┬──────────────────────────┘
               │ JSON-RPC over stdio
               │
┌──────────────┴──────────────────────────┐
│       CrowACPAgent (ACP Protocol)       │
│  - initialize()                         │
│  - new_session()                        │
│  - prompt() → streams updates           │
│  - load_session()                       │
└──────────────┬──────────────────────────┘
               │
┌──────────────┴──────────────────────────┐
│         NID Agent (Orchestration)       │
│  - React loop                           │
│  - Tool execution via MCP               │
│  - Response processing                  │
└──────────────┬──────────────────────────┘
               │
┌──────────────┴──────────────────────────┐
│        Session (State Management)       │
│  - In-memory messages                   │
│  - Database persistence                 │
│  - Prompt template rendering            │
└──────────────────────────────────────────┘
```

## Key Updates

- ✅ Updated to **glm-5** model
- ✅ Clean Session class (no more `get_session()` everywhere)
- ✅ Clean Agent class (all functions as methods)
- ✅ Prompt management with templates
- ✅ ACP protocol support

## Database Schema

After seeding, you'll have:

```sql
-- Prompt templates
prompts:
  - crow-v1: "You are OpenHands agent..."
  - crow-minimal: "You are Crow..."

-- Sessions (created on new_session)
sessions:
  - session_id: "sess_<hash>"
  - prompt_id: "crow-v1"
  - prompt_args: {"workspace": "/path"}
  - system_prompt: <rendered>
  - tool_definitions: [...]
  - model_identifier: "glm-5"

-- Events (conversation history)
events:
  - session_id, conv_index
  - role, content, reasoning_content
  - tool_calls, tool_results
```

## Running Tests

### Unit Tests (TODO)
```bash
uv run pytest tests/
```

### Integration Test with ACP
```bash
# Start agent
uv run python src/nid/acp_agent.py &

# Run client test
uv run python src/nid/scripts/test_acp_client.py
```

## Environment Variables

Create a `.env` file:

```bash
ZAI_API_KEY=your_api_key_here
ZAI_BASE_URL=https://api.your-provider.com/v1
```

## Troubleshooting

**Module not found errors:**
```bash
uv pip install -e .
```

**Database errors:**
```bash
rm mcp_testing.db
uv run python src/nid/scripts/seed_prompts.py
```

**ACP schema errors:**
```bash
cd deps/python-sdk
make gen-all
```

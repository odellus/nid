# Crow Agent

Clean, minimal agent implementation with proper session management and prompt templates.

## Architecture

```
src/crow/
├── agent/
│   ├── __init__.py         # Public API exports
│   ├── agent.py            # Agent class (orchestration)
│   ├── session.py          # Session class (state management)
│   ├── db.py               # Database models (Prompt, Session, Event)
│   ├── prompt.py           # Template rendering
│   ├── config.py           # LLM/MCP configuration helpers
│   └── prompts/            # Jinja2 templates
│       └── system_prompt.jinja2
├── mcp/
│   └── search.py           # MCP server example
└── scripts/
    ├── seed_prompts.py     # Initialize prompt templates
    └── example_agent.py    # Usage example
```

## Key Design Principles

1. **Two Classes**: Session (persistence) + Agent (orchestration)
2. **Encapsulated State**: No scattered `get_session()` calls
3. **Functional Methods**: Methods are steps in the process
4. **Prompt Management**: Templates stored separately from instances

## Database Schema

```sql
prompts:
  - id (PK)
  - name
  - template (Jinja2)
  - created_at

sessions:
  - session_id (PK, hash of prompt+args+tools)
  - prompt_id (FK)
  - prompt_args (JSON)
  - system_prompt (rendered, cached)
  - tool_definitions (JSON)
  - request_params (JSON)
  - model_identifier
  - created_at

events:
  - id (PK)
  - session_id (FK)
  - conv_index
  - role, content, reasoning_content
  - tool_call_id, tool_call_name, tool_arguments
  - prompt_tokens, completion_tokens, total_tokens
```

## Usage

```python
from crow.agent import Agent, Session, configure_llm, setup_mcp_client, get_tools

# Setup
llm = configure_llm()
mcp_client = setup_mcp_client("path/to/server.py")

async with mcp_client:
    tools = await get_tools(mcp_client)
    
    # Create session
    session = Session.create(
        prompt_id="crow-v1",
        prompt_args={"workspace": "/home/user/project"},
        tool_definitions=tools,
        request_params={"temperature": 0.7},
        model_identifier="glm-4.7"
    )
    
    # Add user message
    session.add_message("user", "Help me with this code")
    
    # Create agent
    agent = Agent(
        session=session,
        llm=llm,
        mcp_client=mcp_client,
        tools=tools,
        model="glm-4.7"
    )
    
    # Run
    async for chunk in agent.react_loop():
        print(chunk)
```

## Setup

1. Create database and seed prompts:
```bash
python src/crow/scripts/seed_prompts.py
```

2. Run example:
```bash
python src/crow/scripts/example_agent.py
```

## Benefits

✅ Clean separation of concerns (Session = state, Agent = logic)  
✅ No scattered `get_session()` calls  
✅ Prompt templates versioned and reusable  
✅ Deterministic session IDs for KV cache reuse  
✅ All functions are methods with access to state  
✅ Easy to test with mocks  

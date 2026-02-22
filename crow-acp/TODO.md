# TO DO

- test `load_session` using local model
- skills, skills, skills
- ~~Make different providers part of the actual configuration <- use a toml file or something in ~/.crow~~
- doom loop detection
- Add different models to NewSessionResponse(config_options<- put model choices here)
- Implement a change on your agent's provider/model config through `set_config_option` method in agent


# BACKLOG
- Add callbacks points to agent
- create contracts for requests and responses from callbacks extension SDK so other packages that import crow-acp can interact with the code without inheritance, self injection, or circular imports by
  1.  exposing get/set methods on session data
  2. expose `session/new` and `session/initialize` methods so extension can create new session with new data
  3. expose `session/prompt` with method so extensions/callbacks can use agent's warm kv cache for fast summarization during compaction
- Fix intermittent error in terminal tool since upgrade The key insight is that synchronous blocking code (like `time.sleep()` in the terminal polling loop) inside an `async def` function will block the entire event loop - which could cause hangs if the MCP transport needs to do I/O simultaneously. The fix would be `asyncio.to_thread()` or making the polling truly async. 




# IDEA 
Just sit down with [agentclientprotocol.com](https://agentclientprotocol.com) and go through the whole thing once just to read, then again with a piece of paper taking notes, then again slower actually implementing in crow-acp.



# DONE
- ~~Fix system prompt to actually include AGENTS.md, render workspace info, add datetime~~
- ~~Fix prompt_id being hard coded, actually use hash of unrendered~~
- ~~Include @-ed files in the context through /files or whatever~~
- ~~Add tool calls and executions token emission~~
- ~~Use AsyncOpenAI client to enable better `session/cancel` behavior~~


so it's pretty clear to me now

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "sessionId": "sess_abc123def456",
    "configOptions": [
      {
        "id": "mode",
        "name": "Session Mode",
        "description": "Controls how the agent requests permission",
        "category": "mode",
        "type": "select",
        "currentValue": "ask",
        "options": [
          {
            "value": "ask",
            "name": "Ask",
            "description": "Request permission before making any changes"
          },
          {
            "value": "code",
            "name": "Code",
            "description": "Write and modify code with full tool access"
          }
        ]
      },
      {
        "id": "model",
        "name": "Model",
        "category": "model",
        "type": "select",
        "currentValue": "model-1",
        "options": [
          {
            "value": "model-1",
            "name": "Model 1",
            "description": "The fastest model"
          },
          {
            "value": "model-2",
            "name": "Model 2",
            "description": "The most powerful model"
          }
        ]
      }
    ]
  }
}
```

And then there's what you attach to session/set_config_option in new_session when you return NewSessionResponse(session_id=session_id, config_options={below})

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "session/set_config_option",
  "params": {
    "sessionId": "sess_abc123def456",
    "configId": "mode",
    "value": "code"
  }
}
```
so we need to set up our config_options are part of some kind of 
```python
self._config_options: dict[session_id, dict[config_id, value]]
```

so our code 

```python
    @param_model(SetSessionConfigOptionRequest)
    async def set_config_option(
        self, config_id: str, session_id: str, value: str, **kwargs: Any
    ) -> SetSessionConfigOptionResponse | None: ...
```

basically just needs to set that option and in prompt we need to use the provider/model combination

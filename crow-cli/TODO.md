# TO DO


# NEW FEATURES
- compaction, compaction, compaction <- IN PROGRESS
- skills, skills, skills <- TO DO
- orchestration <- IN PROGRESS

# BUG FIXES
- when we cancel a session we do NOT want to include any crap in the messages might yield things like this so we need to revisit cancellation handling and think about letting that last token trickle in after all

From llama.cpp's side
```
srv    operator(): got exception: {"error":{"code":400,"message":"Assistant message must contain either 'content' or 'tool_calls'!","type":"invalid_request_error"}}
```

from the logs
```
2026-02-25 19:19:47 | ERROR    | crow_logger | Error in prompt handling: Error code: 400 - {'error': {'code': 400, 'message': "Assistant message must contain either 'content' or 'tool_calls'!", 'type': 'invalid_request_error'}}
Traceback (most recent call last):
  File "/home/thomas/src/nid/crow-cli/src/crow_cli/agent/main.py", line 620, in prompt
    return await task
           ^^^^^^^^^^
  File "/home/thomas/src/nid/crow-cli/src/crow_cli/agent/main.py", line 569, in _execute_turn
    async for chunk in react_loop(
    ...<36 lines>...
            break
  File "/home/thomas/src/nid/crow-cli/src/crow_cli/agent/react.py", line 338, in react_loop
    response = await send_request(
               ^^^^^^^^^^^^^^^^^^^
    ...<3 lines>...
    )
    ^
  File "/home/thomas/src/nid/crow-cli/src/crow_cli/agent/react.py", line 55, in send_request
    return await llm.chat.completions.create(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<5 lines>...
    )
    ^
  File "/home/thomas/src/nid/crow-cli/.venv/lib/python3.14/site-packages/openai/resources/chat/completions/completions.py", line 2700, in create
    return await self._post(
           ^^^^^^^^^^^^^^^^^
    ...<49 lines>...
    )
    ^
  File "/home/thomas/src/nid/crow-cli/.venv/lib/python3.14/site-packages/openai/_base_client.py", line 1884, in post
    return await self.request(cast_to, opts, stream=stream, stream_cls=stream_cls)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/thomas/src/nid/crow-cli/.venv/lib/python3.14/site-packages/openai/_base_client.py", line 1669, in request
    raise self._make_status_error_from_response(err.response) from None
openai.BadRequestError: Error code: 400 - {'error': {'code': 400, 'message': "Assistant message must contain either 'content' or 'tool_calls'!", 'type': 'invalid_request_error'}}
```

So I think what's happening is cancellation is causing some kind of broken fragment to get added to the messages somehow. We need to set cancel then let the last token come in and then stop so we don't get broken garbage in the context window from stopping right in the middle of something

- apparently zed uses resource instead of resource_link now, which is fine by me lol. implemented. still having trouble doing for when there are multiple types of resource in the message

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
- ~~test `load_session` using local model~~
- ~~Make different providers part of the actual configuration <- use a toml file or something in ~/.crow~~
- doom loop detection
- ~~Add different models to NewSessionResponse(config_options<- put model choices here)~~
- ~~Revisit config option setting and build without using session.model_identifier~~

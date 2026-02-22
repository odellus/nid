# TO DO


- Add /model selection in ACP
- Load persisted agent from disk using local model. make sure the kv cache is exactly the same (pretty sure this is going to necessarily be true, our kv cache is preserved and we're persisting **everything**) but we'll see
- go through and find the necessary mapping between the file extension and the types of markdown syntax highlighting which are actually supported and stick ```{extension_type}\n``` around the content blocks from fs.read and work out how to make them visible by default in client
- skills, skills, skills
- Make different providers part of the actual configuration <- use a toml file or something in ~/.crow
- doom loop detection
- 


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

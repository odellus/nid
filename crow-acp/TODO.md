# TO DO


- ~~Fix system prompt to actually include AGENTS.md, render workspace info, add datetime~~
- ~~Fix prompt_id being hard coded, actually use hash of unrendered~~
- Add /model selection in ACP
- ~~Include @-ed files in the context through /files or whatever~~
- Add tool calls and executions token emission
- ~~Use AsyncOpenAI client to enable better `session/cancel` behavior~~
- Load persisted agent from disk using local model. make sure the kv cache is exactly the same
- ~~Use client side terminal~~
- ~~Use client fs.read/fs.write instead of file_editor tool~~
- ~~Replace file_editor entirely with opencode inspire fuzzy matching editor tool~~
- ~~Add tool call decorations~~


# BACKLOG
- Add callbacks points to agent
- create contracts for requests and responses from callbacks extension SDK so other packages that import crow-acp can interact with the code without inheritance, self injection, or circular imports by
  1.  exposing get/set methods on session data
  2. expose `session/new` and `session/initialize` methods so extension can create new session with new data
  3. expose `session/prompt` with method so extensions/callbacks can use agent's warm kv cache for fast summarization during compaction



# IDEA 
Just sit down with [agentclientprotocol.com](https://agentclientprotocol.com) and go through the whole thing once just to read, then again with a piece of paper taking notes, then again slower actually implementing in crow-acp.

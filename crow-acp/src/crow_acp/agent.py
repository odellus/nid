#!/home/thomas/src/projects/mcp-testing/crow-acp/.venv/bin/python
"""
ACP-native Agent.

This is the single agent class that combines:
- ACP protocol implementation (from CrowACPAgent)
- Business logic (from old Agent)

No wrapper, no nested agents - just one clean Agent(acp.Agent) implementation.
"""

import asyncio
import json
import logging
import os
import uuid
from contextlib import AsyncExitStack, suppress
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from threading import ExceptHookArgs
from typing import Any

from acp import (
    PROTOCOL_VERSION,
    Agent,
    AuthenticateResponse,
    InitializeResponse,
    LoadSessionResponse,
    NewSessionResponse,
    PromptResponse,
    SetSessionModeResponse,
    run_agent,
    text_block,
    update_agent_message,
    update_agent_thought,
)
from acp.helpers import (
    ToolCallContentVariant,
    start_edit_tool_call,
    start_read_tool_call,
    text_block,
    tool_content,
    tool_diff_content,
    update_tool_call,
)
from acp.interfaces import Client
from acp.schema import (
    AgentCapabilities,
    AgentMessageChunk,
    AudioContentBlock,
    ClientCapabilities,
    EmbeddedResourceContentBlock,
    HttpMcpServer,
    ImageContentBlock,
    Implementation,
    McpServerStdio,
    ResourceContentBlock,
    SseMcpServer,
    TerminalToolCallContent,
    TextContentBlock,
    ToolCallProgress,
    ToolCallStart,
)

# Context vars for turn/tool call tracking
_current_turn_id: ContextVar[str | None] = ContextVar("current_turn_id", default=None)
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastmcp import Client as MCPClient
from json_schema_to_pydantic import create_model

from crow_acp.config import Config, get_default_config
from crow_acp.context import context_fetcher, get_directory_tree, maximal_deserialize
from crow_acp.llm import configure_llm
from crow_acp.mcp_client import create_mcp_client_from_acp, get_tools
from crow_acp.session import Session, lookup_or_create_prompt

# 1. Define paths safely
HOME = Path(os.getenv("HOME", "~")).expanduser()
LOG_DIR = HOME / ".crow"
LOG_PATH = LOG_DIR / "crow-acp.log"

# 2. Ensure the directory exists (prevents FileNotFoundError)
LOG_DIR.mkdir(parents=True, exist_ok=True)


TERMINAL_TOOL = "crow-mcp_terminal"
WRITE_TOOL = "crow-mcp_write"
READ_TOOL = "crow-mcp_read"
EDIT_TOOL = "crow-mcp_edit"
SEARCH_TOOL = "crow-mcp_web_search"
FETCH_TOOL = "crow-mcp_web_fetch"


def setup_logger(name="crow_logger", log_file=LOG_PATH, max_mb=5, max_files=3):
    """
    Sets up a rotating file logger.

    :param name: Name of the logger.
    :param log_file: Path object or string to the log file.
    :param max_mb: Maximum size in Megabytes before rotating.
    :param max_files: Maximum number of backup files to keep.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)  # Set your base logging level here

    # 3. Prevent duplicate log entries if this function is called multiple times
    if not logger.handlers:
        # 4. Set up the RotatingFileHandler
        # maxBytes triggers the rotation, backupCount limits the total files
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_mb * 1024 * 1024, backupCount=max_files
        )

        # 5. Define a readable log format
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)

        # 6. Attach the handler
        logger.addHandler(file_handler)

    return logger


# Initialize and test
logger = setup_logger()
logger.info("Rotating logger initialized successfully!")
logger.error("This is an example error message.")


class AcpAgent(Agent):
    """
    ACP-native agent - single agent class.

    This class:
    - Implements the ACP Agent protocol directly
    - Contains all business logic (react loop, tool execution)
    - Manages resources via AsyncExitStack
    - Stores minimal in-memory state (MCP clients, sessions)
    - Receives MCP servers from ACP client at runtime
    - Replaces terminal tool with ACP client terminal when supported

    No wrapper, no nesting - just one clean implementation.
    """

    _conn: Client
    _client_capabilities: ClientCapabilities | None = None

    def __init__(self, config: Config | None = None) -> None:
        """
        Initialize the merged agent.

        Args:
            config: Configuration object. If None, uses defaults from env vars

        Sets up:
        - AsyncExitStack for resource management
        - In-memory dictionaries for sessions and MCP clients
        - LLM client from configuration
        """
        self._config = config or get_default_config()
        self._db_path = self._config.database_path
        self._exit_stack = AsyncExitStack()
        self._sessions: dict[str, Session] = {}
        self._session_id: str | None = None
        self._session: Session | None = None
        self._mcp_clients: dict[str, Any] = {}  # session_id -> mcp_client
        self._tools: dict[str, list[dict]] = {}  # session_id -> tools
        self._cancel_events: dict[str, asyncio.Event] = {}  # session_id -> cancel_event
        self._streaming_tasks: dict[
            str, asyncio.Task
        ] = {}  # session_id -> streaming_task
        self._state_accumulators: dict[
            str, dict
        ] = {}  # session_id -> partial state for cancellation
        self._tool_call_ids: dict[
            str, str
        ] = {}  # session_id -> persistent terminal_id for stateful terminals
        # Terminal state tracking for ACP client terminals (persist env/cwd between calls)
        self._llm = configure_llm(debug=False)

    def on_connect(self, conn: Client) -> None:
        """Store connection for sending updates"""
        self._conn = conn

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: ClientCapabilities | None = None,
        client_info: Implementation | None = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        """Handle ACP initialization"""
        logger.info("Initializing Agent")
        logger.info(f"Client capabilities: {client_capabilities}")
        logger.info(f"Client info: {client_info}")

        self._client_capabilities = client_capabilities
        logger.info(f"Client capabilities: {client_capabilities}")
        # Check if client supports terminals
        if client_capabilities and getattr(client_capabilities, "terminal", False):
            logger.info("Client supports ACP terminals - will use client-side terminal")
        else:
            logger.info("Client does NOT support ACP terminals - will use MCP terminal")

        return InitializeResponse(
            protocol_version=PROTOCOL_VERSION,
            agent_capabilities=AgentCapabilities(
                load_session=True,  # We support session loading
            ),
            agent_info=Implementation(
                name="crow",
                title="Crow Agent",
                version="0.1.0",
            ),
        )

    async def authenticate(
        self, method_id: str, **kwargs: Any
    ) -> AuthenticateResponse | None:
        """Handle authentication (no-op for now)"""
        logger.info("Authentication request: %s", method_id)
        return AuthenticateResponse()

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio],
        **kwargs: Any,
    ) -> NewSessionResponse:
        """
        Create a new session with proper resource management.

        Uses AsyncExitStack to ensure MCP clients are cleaned up properly.
        Uses MCP servers from config, or builtin server as default.
        """
        logger.info("Creating new session in cwd: %s", cwd)

        # Use default MCP config if no servers provided
        fallback_config = self._config.get_builtin_mcp_config()

        # Create MCP client (builtin if no servers provided)
        mcp_client = await create_mcp_client_from_acp(
            mcp_servers,
            cwd,
            fallback_config=fallback_config,
        )

        # CRITICAL: Use AsyncExitStack for lifecycle management
        mcp_client = await self._exit_stack.enter_async_context(mcp_client)

        # Get tools from MCP server
        tools = await get_tools(mcp_client)

        # Load prompt template and get or create prompt_id

        template_path = Path(__file__).parent / "prompts" / "system_prompt.jinja2"
        template = template_path.read_text()
        prompt_id = lookup_or_create_prompt(
            template, name="crow-default", db_path=self._db_path
        )
        display_tree = get_directory_tree(cwd)
        agent_path = os.path.join(cwd, "AGENTS.md")
        with open(agent_path, "r") as f:
            agents_content = f.read()
        session = Session.create(
            prompt_id=prompt_id,
            prompt_args={
                "workspace": cwd,
                "display_tree": display_tree,
                "agents_content": agents_content,
            },
            tool_definitions=tools,
            request_params={"temperature": 0.2},
            model_identifier=self._config.llm.providers[0].default_model,
            db_path=self._db_path,
            cwd=cwd,
        )

        # Store in-memory references
        self._sessions[session.session_id] = session
        self._session = session
        self._session_id = session.session_id
        self._mcp_clients[session.session_id] = mcp_client
        self._tools[session.session_id] = tools
        self._cancel_events[session.session_id] = asyncio.Event()

        logger.info("Created session: %s with %d tools", session.session_id, len(tools))
        return NewSessionResponse(session_id=session.session_id, modes=None)

    async def load_session(
        self,
        cwd: str,
        mcp_servers: list[HttpMcpServer | SseMcpServer | McpServerStdio],
        session_id: str,
        **kwargs: Any,
    ) -> LoadSessionResponse | None:
        """Load an existing session with proper resource management."""
        logger.info("Loading session: %s", session_id)

        try:
            # Load session from database
            session = Session.load(session_id, db_path=self._db_path)

            # Setup MCP client (same as new_session)
            # Use default config if no servers provided
            fallback_config = self._config.get_builtin_mcp_config()
            if fallback_config:
                mcp_client = await create_mcp_client_from_acp(
                    mcp_servers,
                    cwd,
                    fallback_config=fallback_config,
                )
            else:
                mcp_client = await create_mcp_client_from_acp(mcp_servers, cwd)

            # CRITICAL: Use AsyncExitStack for lifecycle management
            mcp_client = await self._exit_stack.enter_async_context(mcp_client)

            # Get tools
            tools = await get_tools(mcp_client)

            # Store in-memory references
            self._sessions[session_id] = session
            self._session = session
            self._session_id = session.session_id
            self._mcp_clients[session_id] = mcp_client
            self._tools[session_id] = tools
            self._cancel_events[session_id] = asyncio.Event()

            # TODO: Replay conversation history to client

            return LoadSessionResponse()
        except Exception as e:
            logger.error("Failed to load session %s: %s", session_id, e)
            return None

    async def set_session_mode(
        self, mode_id: str, session_id: str, **kwargs: Any
    ) -> SetSessionModeResponse | None:
        """Handle session mode changes (not implemented yet)"""
        logger.info("Set session mode: %s -> %s", session_id, mode_id)
        return SetSessionModeResponse()

    async def prompt(
        self,
        prompt: list[
            TextContentBlock
            | ImageContentBlock
            | AudioContentBlock
            | ResourceContentBlock
            | EmbeddedResourceContentBlock
        ],
        session_id: str,
        **kwargs: Any,
    ) -> PromptResponse:
        """
        Handle prompt request - main entry point for user messages.

        This is where we run the react loop and stream updates back.
        Uses Task-based cancellation for immediate interruption.
        """
        logger.info("Prompt request for session: %s", session_id)

        # Generate turn ID for this prompt (used for ACP tool call IDs)
        turn_id = str(uuid.uuid4())
        turn_token = _current_turn_id.set(turn_id)

        # Get session
        session = self._sessions.get(session_id)
        if not session:
            logger.error("Session not found: %s", session_id)
            _current_turn_id.reset(turn_token)
            return PromptResponse(stop_reason="cancelled")

        # Extract text from prompt blocks
        text_list = []
        for block in prompt:
            _type = (
                block.get("type", "")
                if isinstance(block, dict)
                else getattr(block, "type", "")
            )
            if _type == "text":
                text = (
                    block.get("text", "")
                    if isinstance(block, dict)
                    else getattr(block, "text", "")
                )
                text_list.append(text)
            elif _type == "resource_link":
                logging.info(f"block type: {type(block)}")
                uri = (
                    block.get("uri", "")
                    if isinstance(block, dict)
                    else getattr(block, "uri", "")
                )

                text_list.append(context_fetcher(uri))

        # Add user message to session
        session.add_message("user", " ".join(text_list))

        # Clear cancel event for this new prompt
        cancel_event = self._cancel_events.get(session_id)
        if cancel_event:
            cancel_event.clear()

        # Initialize state accumulator for this prompt (for cancellation persistence)
        self._state_accumulators[session_id] = {
            "thinking": [],
            "content": [],
            "tool_call_inputs": [],
        }

        # Create a queue for streaming chunks
        chunk_queue: asyncio.Queue = asyncio.Queue()

        # Flag to signal completion
        completed = asyncio.Event()
        stop_reason = "end_turn"

        async def streaming_worker():
            """Worker that runs the react loop and puts chunks in queue."""
            nonlocal stop_reason
            try:
                async for chunk in self._react_loop(session_id):
                    await chunk_queue.put(chunk)
                stop_reason = "end_turn"
            except asyncio.CancelledError:
                logger.info("Streaming worker cancelled")
                stop_reason = "cancelled"
                raise
            except Exception as e:
                logger.error("Error in streaming worker: %s", e, exc_info=True)
                stop_reason = "end_turn"
            finally:
                completed.set()

        # Create and store the streaming task
        streaming_task = asyncio.create_task(streaming_worker())
        self._streaming_tasks[session_id] = streaming_task

        # Stream chunks back to client
        try:
            while not completed.is_set() or not chunk_queue.empty():
                try:
                    # Use wait_for to allow checking completion
                    chunk = await asyncio.wait_for(chunk_queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue

                chunk_type = chunk.get("type")

                if chunk_type == "content":
                    await self._conn.session_update(
                        session_id,
                        update_agent_message(text_block(chunk["token"])),
                    )

                elif chunk_type == "thinking":
                    await self._conn.session_update(
                        session_id,
                        update_agent_thought(text_block(chunk["token"])),
                    )

                elif chunk_type == "tool_call":
                    name, first_arg = chunk["token"]
                    logger.debug("Tool call: %s(%s", name, first_arg)

                elif chunk_type == "tool_args":
                    logger.debug("Tool args: %s", chunk["token"])

                elif chunk_type == "final_history":
                    break

            return PromptResponse(stop_reason=stop_reason)

        except asyncio.CancelledError:
            logger.info("Prompt cancelled")
            # Persist partial state before returning
            state = self._state_accumulators.get(session_id)
            if state:
                session.add_assistant_response(
                    state["thinking"], state["content"], state["tool_call_inputs"], []
                )
            return PromptResponse(stop_reason="cancelled")

        except Exception as e:
            logger.error("Error in prompt handling: %s", e, exc_info=True)
            return PromptResponse(stop_reason="end_turn")

        finally:
            # Clean up task reference
            self._streaming_tasks.pop(session_id, None)
            # Reset turn ID context var
            _current_turn_id.reset(turn_token)

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        """Handle cancellation by cancelling the streaming task."""
        logger.info("Cancel request for session: %s", session_id)

        # Cancel the streaming task if it exists
        streaming_task = self._streaming_tasks.get(session_id)
        if streaming_task and not streaming_task.done():
            logger.info("Cancelling streaming task for session: %s", session_id)
            streaming_task.cancel()

            # Also set the cancel event for the react loop to check
            cancel_event = self._cancel_events.get(session_id)
            if cancel_event:
                cancel_event.set()

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Handle extension methods"""
        logger.info("Extension method: %s", method)
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Handle extension notifications"""
        logger.info("Extension notification: %s", method)

    async def cleanup(self) -> None:
        """
        Cleanup all resources managed by this agent.

        The AsyncExitStack ensures all resources are cleaned up in reverse order
        of their creation, even if exceptions occur during cleanup.
        """
        logger.info("Cleaning up Agent resources")
        await self._exit_stack.aclose()
        logger.info("Cleanup complete")

    async def _send_request(self, session_id: str):
        """
        Send request to LLM.

        Args:
            session_id: Session ID to get session data

        Returns:
            Streaming response from LLM
        """
        session = self._sessions[session_id]
        tools = self._tools[session_id]

        return await self._llm.chat.completions.create(
            model="glm-5",
            messages=session.messages,
            tools=tools,
            stream=True,
            parallel_tool_calls=True,
        )

    def _process_chunk(
        self,
        chunk,
        thinking: list[str],
        content: list[str],
        tool_calls: dict,
        tool_call_id: str | None,
    ) -> tuple[list[str], list[str], dict, str | None, tuple[str | None, Any]]:
        """
        Process a single streaming chunk.

        Args:
            chunk: Streaming chunk from LLM
            thinking: Accumulated thinking tokens
            content: Accumulated content tokens
            tool_calls: Accumulated tool calls
            tool_call_id: Current tool call ID

        Returns:
            Tuple of (thinking, content, tool_calls, tool_call_id, new_token)
        """
        delta = chunk.choices[0].delta
        new_token = (None, None)

        if not delta.tool_calls:
            if not hasattr(delta, "reasoning_content"):
                verbal_chunk = delta.content
                if verbal_chunk:
                    content.append(verbal_chunk)
                    new_token = ("content", verbal_chunk)
            else:
                reasoning_chunk = delta.reasoning_content
                if reasoning_chunk:
                    thinking.append(reasoning_chunk)
                    new_token = ("thinking", reasoning_chunk)
        else:
            for call in delta.tool_calls:
                if call.id is not None:
                    tool_call_id = call.id
                    if call.id not in tool_calls:
                        tool_calls[call.id] = {
                            "function_name": call.function.name,
                            "arguments": [call.function.arguments],
                        }
                        new_token = (
                            "tool_call",
                            (call.function.name, call.function.arguments),
                        )
                else:
                    arg_fragment = call.function.arguments
                    tool_calls[tool_call_id]["arguments"].append(arg_fragment)
                    new_token = ("tool_args", arg_fragment)

        return thinking, content, tool_calls, tool_call_id, new_token

    async def _process_response(self, response, state_accumulator: dict | None = None):
        """
        Process streaming response from LLM.

        Args:
            response: Streaming response from LLM
            state_accumulator: Optional dict to expose partial state externally

        Yields:
            Tuple of (message_type, token) for each chunk

        Returns:
            Tuple of (thinking, content, tool_call_inputs, usage) when done
        """
        thinking, content, tool_calls, tool_call_id = [], [], {}, None
        final_usage = None

        # Initialize state accumulator if provided
        if state_accumulator is not None:
            state_accumulator.update(
                {
                    "thinking": thinking,
                    "content": content,
                    "tool_calls": tool_calls,
                    "tool_call_inputs": [],
                }
            )

        async for chunk in response:
            # Capture usage from the chunk (if present)
            if hasattr(chunk, "usage") and chunk.usage:
                final_usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }
            # Right here is where we aggregate for persistence and execution
            thinking, content, tool_calls, tool_call_id, new_token = (
                self._process_chunk(chunk, thinking, content, tool_calls, tool_call_id)
            )

            # Update state accumulator after each chunk
            if state_accumulator is not None:
                state_accumulator["thinking"] = thinking
                state_accumulator["content"] = content
                state_accumulator["tool_calls"] = tool_calls

            # And we yield so the streaming magic happens
            msg_type, token = new_token
            if msg_type:
                yield msg_type, token

        # Final update to accumulator
        tool_call_inputs = self._process_tool_call_inputs(tool_calls)
        if state_accumulator is not None:
            state_accumulator["tool_call_inputs"] = tool_call_inputs

        # Yield final result
        yield "final", (thinking, content, tool_call_inputs, final_usage)

    def _process_tool_call_inputs(self, tool_calls: dict) -> list[dict]:
        """
        Process tool call inputs into OpenAI format.

        Args:
            tool_calls: Dictionary of tool calls

        Returns:
            List of tool call objects in OpenAI format
        """
        tool_call_inputs = []
        for tool_call_id, tool_call in tool_calls.items():
            tool_call_inputs.append(
                {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": tool_call["function_name"],
                        "arguments": "".join(tool_call["arguments"]),
                    },
                }
            )
        return tool_call_inputs

    async def _execute_tool_calls(
        self, session_id: str, tool_call_inputs: list[dict]
    ) -> list[dict]:
        """
        Execute tool calls via MCP or ACP client terminal.

        Args:
            session_id: Session ID to get MCP client
            tool_call_inputs: List of tool calls to execute

        Returns:
            List of tool results
        """
        mcp_client = self._mcp_clients[session_id]
        tool_results = []

        # Check if we should use ACP client terminal
        use_acp_terminal = self._client_capabilities and getattr(
            self._client_capabilities, "terminal", False
        )

        # Check filesystem capabilities (nested under 'fs')
        fs_caps = (
            getattr(self._client_capabilities, "fs", None)
            if self._client_capabilities
            else None
        )
        use_acp_write = fs_caps and getattr(fs_caps, "write_text_file", False)
        use_acp_read = fs_caps and getattr(fs_caps, "read_text_file", False)

        # Get turn_id for ACP tool call IDs
        turn_id = _current_turn_id.get()

        for tool_call in tool_call_inputs:
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"]["arguments"]
            llm_tool_call_id = tool_call["id"]

            # Build ACP tool call ID
            acp_tool_call_id = (
                f"{turn_id}/{llm_tool_call_id}" if turn_id else llm_tool_call_id
            )

            try:
                arg_dict = maximal_deserialize(tool_args)

                # Intercept terminal tool if ACP client supports it
                if tool_name == TERMINAL_TOOL and use_acp_terminal:
                    result_content = await self._execute_acp_terminal(
                        session_id=session_id,
                        tool_call_id=llm_tool_call_id,
                        args=arg_dict,
                    )
                elif tool_name == WRITE_TOOL and use_acp_write:
                    result_content = await self._execute_acp_write(
                        session_id=session_id,
                        tool_call_id=llm_tool_call_id,
                        args=arg_dict,
                    )
                elif tool_name == READ_TOOL and use_acp_read:
                    result_content = await self._execute_acp_read(
                        session_id=session_id,
                        tool_call_id=llm_tool_call_id,
                        args=arg_dict,
                    )
                elif tool_name == EDIT_TOOL:
                    # Edit always uses local MCP (fuzzy matching), but sends diff content
                    result_content = await self._execute_acp_edit(
                        session_id=session_id,
                        tool_call_id=llm_tool_call_id,
                        args=arg_dict,
                    )
                elif tool_name == SEARCH_TOOL:
                    result_content = await self._execute_acp_tool(
                        session_id=session_id,
                        tool_call_id=llm_tool_call_id,
                        tool_name=tool_name,
                        args=arg_dict,
                        kind="search",
                    )
                elif tool_name == FETCH_TOOL:
                    result_content = await self._execute_acp_tool(
                        session_id=session_id,
                        tool_call_id=llm_tool_call_id,
                        tool_name=tool_name,
                        args=arg_dict,
                        kind="fetch",
                    )
                else:
                    # Send tool call start
                    await self._conn.session_update(
                        session_id=session_id,
                        update=ToolCallStart(
                            session_update="tool_call",
                            tool_call_id=acp_tool_call_id,
                            title=f"{tool_name}",
                            kind=self._get_tool_kind(tool_name),
                            status="pending",
                        ),
                    )

                    # Send in_progress update
                    await self._conn.session_update(
                        session_id=session_id,
                        update=ToolCallProgress(
                            session_update="tool_call_update",
                            tool_call_id=acp_tool_call_id,
                            status="in_progress",
                        ),
                    )

                    # Execute the MCP tool
                    result = await mcp_client.call_tool(tool_name, arg_dict)
                    result_content = result.content[0].text

                    # Send completion update with content
                    await self._conn.session_update(
                        session_id=session_id,
                        update=update_tool_call(
                            acp_tool_call_id,
                            status="completed",
                            content=[tool_content(text_block(result_content))],
                        ),
                    )

                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": llm_tool_call_id,
                        "content": result_content,
                    }
                )
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)

                # Send failure update
                await self._conn.session_update(
                    session_id=session_id,
                    update=ToolCallProgress(
                        session_update="tool_call_update",
                        tool_call_id=acp_tool_call_id,
                        status="failed",
                    ),
                )

                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": llm_tool_call_id,
                        "content": f"Error: {str(e)}",
                    }
                )
        return tool_results

    def _get_tool_kind(self, tool_name: str) -> str:
        """Map tool names to ACP ToolKind."""
        # Common MCP tool patterns
        if tool_name in ("read_file", "read", "view", "list_directory", "list"):
            return "read"
        elif tool_name in ("write_file", "write", "edit", "create", "str_replace"):
            return "edit"
        elif tool_name in ("delete", "remove"):
            return "delete"
        elif tool_name in ("move", "rename"):
            return "move"
        elif tool_name in ("search", "grep", "find"):
            return "search"
        elif tool_name in ("terminal", "bash", "shell", "execute"):
            return "execute"
        else:
            return "other"

    async def _execute_acp_terminal(
        self,
        session_id: str,
        tool_call_id: str,
        args: dict[str, Any],
    ) -> str:
        """
        Execute terminal command via ACP client terminal.

        Maps the MCP terminal tool args to ACP client terminal:
        - command: The command to run
        - timeout: Max seconds to wait (default 30)
        - is_input: Not supported by ACP terminal (runs single commands)
        - reset: Not needed (ACP terminal is fresh each call)

        Args:
            session_id: ACP session ID
            tool_call_id: LLM tool call ID
            args: Tool arguments from LLM

        Returns:
            Result string with output and status
        """
        command = args.get("command", "")
        timeout_seconds = float(args.get("timeout") or 30.0)

        # Build ACP tool call ID from turn_id + llm tool call id
        turn_id = _current_turn_id.get()
        acp_tool_call_id = f"{turn_id}/{tool_call_id}" if turn_id else tool_call_id

        # Get session state for cwd
        session = self._sessions.get(session_id)
        cwd = session.cwd if session and hasattr(session, "cwd") else "/tmp"

        terminal_id: str | None = None
        timed_out = False

        try:
            # 1. Send tool call start
            await self._conn.session_update(
                session_id=session_id,
                update=ToolCallStart(
                    session_update="tool_call",
                    tool_call_id=acp_tool_call_id,
                    title=f"terminal: {command[:50]}{'...' if len(command) > 50 else ''}",
                    kind="execute",
                    status="pending",
                ),
            )

            # 2. Create terminal via ACP client
            logger.info(f"Creating ACP terminal for command: {command}")
            terminal_response = await self._conn.create_terminal(
                command=command,
                session_id=session_id,
                cwd=cwd,
                output_byte_limit=100000,  # 100KB limit
            )
            terminal_id = terminal_response.terminal_id
            logger.info(f"Terminal created: {terminal_id}")

            # 3. Send tool call update with terminal content for live display
            await self._conn.session_update(
                session_id=session_id,
                update=ToolCallProgress(
                    session_update="tool_call_update",
                    tool_call_id=acp_tool_call_id,
                    status="in_progress",
                    content=[
                        TerminalToolCallContent(
                            type="terminal",
                            terminalId=terminal_id,
                        )
                    ],
                ),
            )

            # 4. Wait for terminal to exit with timeout
            exit_code = None
            exit_signal = None
            try:
                async with asyncio.timeout(timeout_seconds):
                    exit_response = await self._conn.wait_for_terminal_exit(
                        session_id=session_id,
                        terminal_id=terminal_id,
                    )
                    exit_code = exit_response.exit_code
                    exit_signal = exit_response.signal
                    logger.info(
                        f"Terminal exited with code: {exit_code}, signal: {exit_signal}"
                    )
            except TimeoutError:
                logger.warning(f"Terminal timed out after {timeout_seconds}s")
                timed_out = True
                await self._conn.kill_terminal(
                    session_id=session_id, terminal_id=terminal_id
                )

            # 5. Get final output
            output_response = await self._conn.terminal_output(
                session_id=session_id, terminal_id=terminal_id
            )
            output = output_response.output

            truncated_note = (
                " Output was truncated." if output_response.truncated else ""
            )

            # 6. Send final tool call update
            final_status = (
                "failed"
                if (exit_code and exit_code != 0) or exit_signal or timed_out
                else "completed"
            )

            await self._conn.session_update(
                session_id=session_id,
                update=ToolCallProgress(
                    session_update="tool_call_update",
                    tool_call_id=acp_tool_call_id,
                    status=final_status,
                ),
            )

            # 7. Build result message
            if timed_out:
                return f"⏱️ Command killed by timeout ({timeout_seconds}s){truncated_note}\n\nOutput:\n{output}"
            elif exit_signal:
                return f"⚠️ Command terminated by signal: {exit_signal}{truncated_note}\n\nOutput:\n{output}"
            elif exit_code not in (None, 0):
                return f"❌ Command failed with exit code: {exit_code}{truncated_note}\n\nOutput:\n{output}"
            else:
                return f"✅ Command executed successfully{truncated_note}\n\nOutput:\n{output}"

        except Exception as e:
            logger.error(f"Error executing ACP terminal: {e}", exc_info=True)
            return f"Error: {str(e)}"

        finally:
            # 8. Release terminal if created
            if terminal_id:
                with suppress(Exception):
                    await self._conn.release_terminal(
                        session_id=session_id, terminal_id=terminal_id
                    )
                    logger.info(f"Released terminal: {terminal_id}")

    async def _execute_acp_read(
        self,
        session_id: str,
        tool_call_id: str,
        args: dict[str, Any],
    ) -> str:
        """
        Read file via ACP client filesystem.

        Args:
            session_id: ACP session ID
            tool_call_id: LLM tool call ID
            args: Tool arguments from LLM (file_path, offset, limit)

        Returns:
            File contents with line numbers
        """
        path = args.get("file_path", "")
        offset = args.get("offset")  # 1-indexed
        limit = args.get("limit", 2000)

        # Build ACP tool call ID from turn_id + llm tool call id
        turn_id = _current_turn_id.get()
        acp_tool_call_id = f"{turn_id}/{tool_call_id}" if turn_id else tool_call_id

        try:
            # 1. Send tool call start
            title = f"read: {path}"
            await self._conn.session_update(
                session_id=session_id,
                update=start_read_tool_call(
                    tool_call_id=acp_tool_call_id,
                    title=title,
                    path=path,
                ),
            )

            # 2. Send in_progress update
            await self._conn.session_update(
                session_id=session_id,
                update=update_tool_call(acp_tool_call_id, status="in_progress"),
            )

            # 3. Read file via ACP client
            logger.info(f"Reading file via ACP: {path}")
            response = await self._conn.read_text_file(
                session_id=session_id,
                path=path,
                line=offset,
                limit=limit,
            )
            content = response.content or ""

            # 4. Send completion update with file content
            await self._conn.session_update(
                session_id=session_id,
                update=update_tool_call(
                    acp_tool_call_id,
                    status="completed",
                    content=[tool_content(text_block(content))],
                ),
            )

            return content

        except Exception as e:
            logger.error(f"Error reading file via ACP: {e}", exc_info=True)
            # Send failed status
            await self._conn.session_update(
                session_id=session_id,
                update=update_tool_call(acp_tool_call_id, status="failed"),
            )
            return f"Error reading file: {str(e)}"

    async def _execute_acp_write(
        self,
        session_id: str,
        tool_call_id: str,
        args: dict[str, Any],
    ) -> str:
        """
        Write file via ACP client filesystem.

        Args:
            session_id: ACP session ID
            tool_call_id: LLM tool call ID
            args: Tool arguments from LLM (file_path, content)

        Returns:
            Success message
        """
        path = args.get("file_path", "")
        content = args.get("content", "")

        # Build ACP tool call ID from turn_id + llm tool call id
        turn_id = _current_turn_id.get()
        acp_tool_call_id = f"{turn_id}/{tool_call_id}" if turn_id else tool_call_id

        try:
            # 1. Send tool call start
            title = f"write: {path}"
            await self._conn.session_update(
                session_id=session_id,
                update=start_edit_tool_call(
                    tool_call_id=acp_tool_call_id,
                    title=title,
                    path=path,
                    content=content,
                ),
            )

            # 2. Send in_progress update with diff content
            await self._conn.session_update(
                session_id=session_id,
                update=update_tool_call(
                    acp_tool_call_id,
                    status="in_progress",
                    content=[tool_diff_content(path=path, new_text=content)],
                ),
            )

            # 3. Write file via ACP client
            logger.info(f"Writing file via ACP: {path}")
            await self._conn.write_text_file(
                session_id=session_id,
                path=path,
                content=content,
            )

            # 4. Send completion update
            await self._conn.session_update(
                session_id=session_id,
                update=update_tool_call(acp_tool_call_id, status="completed"),
            )

            return f"Successfully wrote to {path}"

        except Exception as e:
            logger.error(f"Error writing file via ACP: {e}", exc_info=True)
            # Send failed status
            await self._conn.session_update(
                session_id=session_id,
                update=update_tool_call(acp_tool_call_id, status="failed"),
            )
            return f"Error writing file: {str(e)}"

    async def _execute_acp_edit(
        self,
        session_id: str,
        tool_call_id: str,
        args: dict[str, Any],
    ) -> str:
        """
        Edit file with fuzzy matching, sending diff content to ACP client.

        This executes the edit locally (fuzzy matching is agent-side) but
        sends proper diff content for the client to display.

        Args:
            session_id: ACP session ID
            tool_call_id: LLM tool call ID
            args: Tool arguments from LLM (file_path, old_string, new_string, replace_all)

        Returns:
            Result string from the edit operation
        """
        path = args.get("file_path", "")
        old_text = args.get("old_string", "")
        new_text = args.get("new_string", "")

        # Build ACP tool call ID from turn_id + llm tool call id
        turn_id = _current_turn_id.get()
        acp_tool_call_id = f"{turn_id}/{tool_call_id}" if turn_id else tool_call_id

        try:
            # 1. Send tool call start
            title = f"edit: {path}"
            await self._conn.session_update(
                session_id=session_id,
                update=start_edit_tool_call(
                    tool_call_id=acp_tool_call_id,
                    title=title,
                    path=path,
                    content=new_text,
                ),
            )

            # 2. Send in_progress update with diff content
            await self._conn.session_update(
                session_id=session_id,
                update=update_tool_call(
                    acp_tool_call_id,
                    status="in_progress",
                    content=[
                        tool_diff_content(
                            path=path, new_text=new_text, old_text=old_text
                        )
                    ],
                ),
            )

            # 3. Execute edit via local MCP tool (fuzzy matching is agent-side)
            logger.info(f"Executing edit via MCP: {path}")
            mcp_client = self._mcp_clients.get(session_id)
            if not mcp_client:
                raise RuntimeError(f"No MCP client for session {session_id}")
            result = await mcp_client.call_tool(EDIT_TOOL, args)
            result_content = result.content[0].text

            # 4. Send completion update
            status = "completed" if "Error" not in result_content else "failed"
            await self._conn.session_update(
                session_id=session_id,
                update=update_tool_call(acp_tool_call_id, status=status),
            )

            return result_content

        except Exception as e:
            logger.error(f"Error executing edit: {e}", exc_info=True)
            await self._conn.session_update(
                session_id=session_id,
                update=update_tool_call(acp_tool_call_id, status="failed"),
            )
            return f"Error: {str(e)}"

    async def _execute_acp_tool(
        self,
        session_id: str,
        tool_call_id: str,
        tool_name: str,
        args: dict[str, Any],
        kind: str = "other",
    ) -> str:
        """
        Execute a generic tool via MCP and report with content.

        Used for tools like search, fetch, etc. that return text content
        to display to the user.

        Args:
            session_id: ACP session ID
            tool_call_id: LLM tool call ID
            tool_name: Name of the MCP tool to call
            args: Tool arguments from LLM
            kind: Tool kind for display (search, fetch, other)

        Returns:
            Result string from the tool
        """
        # Build ACP tool call ID from turn_id + llm tool call id
        turn_id = _current_turn_id.get()
        acp_tool_call_id = f"{turn_id}/{tool_call_id}" if turn_id else tool_call_id

        try:
            # 1. Send tool call start
            title = f"{tool_name}"
            await self._conn.session_update(
                session_id=session_id,
                update=ToolCallStart(
                    session_update="tool_call",
                    tool_call_id=acp_tool_call_id,
                    title=title,
                    kind=kind,
                    status="pending",
                ),
            )

            # 2. Send in_progress update
            await self._conn.session_update(
                session_id=session_id,
                update=update_tool_call(acp_tool_call_id, status="in_progress"),
            )

            # 3. Execute tool via MCP
            logger.info(f"Executing tool via MCP: {tool_name}")
            mcp_client = self._mcp_clients.get(session_id)
            if not mcp_client:
                raise RuntimeError(f"No MCP client for session {session_id}")
            result = await mcp_client.call_tool(tool_name, args)
            result_content = result.content[0].text

            # 4. Send completion update with content
            status = "completed" if "Error" not in result_content else "failed"
            await self._conn.session_update(
                session_id=session_id,
                update=update_tool_call(
                    acp_tool_call_id,
                    status=status,
                    content=[tool_content(text_block(result_content))],
                ),
            )

            return result_content

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            await self._conn.session_update(
                session_id=session_id,
                update=update_tool_call(acp_tool_call_id, status="failed"),
            )
            return f"Error: {str(e)}"

    async def _react_loop(self, session_id: str, max_turns: int = 50000):
        """
        Main ReAct loop with cancellation support.

        Args:
            session_id: Session ID to get session and tools
            max_turns: Maximum number of turns to execute

        Yields:
            Dictionary with 'type' and 'token' or 'messages' keys
        """
        session = self._sessions[session_id]
        cancel_event = self._cancel_events.get(session_id)

        for turn in range(max_turns):
            # Check at start of turn
            if cancel_event and cancel_event.is_set():
                logger.info(f"Cancelled at start of turn {turn}")
                return

            # Send request to LLM
            response = await self._send_request(session_id)

            # Use global state accumulator for cancellation persistence
            state_accumulator = self._state_accumulators.get(
                session_id, {"thinking": [], "content": [], "tool_call_inputs": []}
            )

            # Process streaming response
            thinking, content, tool_call_inputs, usage = [], [], [], None
            try:
                async for msg_type, token in self._process_response(
                    response, state_accumulator
                ):
                    if msg_type == "final":
                        thinking, content, tool_call_inputs, usage = token
                    else:
                        yield {"type": msg_type, "token": token}
            except asyncio.CancelledError:
                logger.info("React loop cancelled mid-stream")
                # Persist partial state from accumulator
                session.add_assistant_response(
                    state_accumulator["thinking"],
                    state_accumulator["content"],
                    state_accumulator["tool_call_inputs"],
                    [],
                )
                raise

            # Check before tool execution
            if cancel_event and cancel_event.is_set():
                logger.info("Cancelled before tool execution")
                session.add_assistant_response(thinking, content, tool_call_inputs, [])
                return

            # If no tool calls, we're done
            if not tool_call_inputs:
                session.add_assistant_response(thinking, content, [], [])
                yield {"type": "final_history", "messages": session.messages}
                return

            # Execute tools
            tool_results = await self._execute_tool_calls(session_id, tool_call_inputs)

            # Check after tool execution
            if cancel_event and cancel_event.is_set():
                logger.info("Cancelled after tool execution")
                session.add_assistant_response(
                    thinking, content, tool_call_inputs, tool_results
                )
                return

            # Add response to session
            session.add_assistant_response(
                thinking, content, tool_call_inputs, tool_results
            )


async def agent_run() -> None:
    logging.basicConfig(level=logging.INFO)
    await run_agent(AcpAgent())


def main():
    asyncio.run(agent_run())


if __name__ == "__main__":
    main()

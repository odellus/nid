import asyncio
import asyncio.subprocess as aio_subprocess
import contextlib
import logging
import os
import sys
from pathlib import Path
from typing import Any

from acp import (
    PROTOCOL_VERSION,
    Client,
    RequestError,
    connect_to_agent,
    text_block,
)
from acp.core import ClientSideConnection
from acp.schema import (
    AgentMessageChunk,
    AgentPlanUpdate,
    AgentThoughtChunk,
    AudioContentBlock,
    AvailableCommandsUpdate,
    ClientCapabilities,
    CreateTerminalResponse,
    CurrentModeUpdate,
    EmbeddedResourceContentBlock,
    EnvVariable,
    ImageContentBlock,
    Implementation,
    KillTerminalCommandResponse,
    PermissionOption,
    ReadTextFileResponse,
    ReleaseTerminalResponse,
    RequestPermissionResponse,
    ResourceContentBlock,
    TerminalOutputResponse,
    TextContentBlock,
    ToolCall,
    ToolCallProgress,
    ToolCallStart,
    UserMessageChunk,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
)

# Colors and styles
RESET = "\033[0m"
BOLD = "\033[1m"
ITALIC = "\033[3m"  # Not all terminals support this
UNDERLINE = "\033[4m"

# Foreground colors
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

# Bright variants
BRIGHT_RED = "\033[91m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_BLUE = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN = "\033[96m"
BRIGHT_WHITE = "\033[97m"

# Dim variants
DIM_RED = "\033[2m"
DIM_GREEN = "\033[2m"
DIM_YELLOW = "\033[2m"
DIM_BLUE = "\033[2m"
DIM_MAGENTA = "\033[2m"
DIM_CYAN = "\033[2m"
DIM_WHITE = "\033[2m"

# Range of purples
PURPLE = "\033[35m"
BRIGHT_PURPLE = "\033[95m"
DIM_PURPLE = "\033[2m"
DEEP_PURPLE = "\033[38;5;93m"
VIOLET = "\033[38;5;129m"

PURPLE_BRIGHT = "\x1b[38;2;180;0;255m"  # Vibrant purple
PURPLE_MEDIUM = "\x1b[38;2;147;0;211m"  # Medium orchid purple
PURPLE_DEEP = "\x1b[38;2;138;43;226m"  # Blue-violet

# Usage
# print(f"{CYAN}{ITALIC}italic cyan text{RESET}", end="", flush=True)
# print(f"{BRIGHT_GREEN}bright green{RESET}", end="", flush=True)


def display_text(text: str, color: str = PURPLE, styles: list[str] = []):
    output_list = [color] + styles
    text_list = [text]  # this will be one token?
    text_list.append(RESET)
    output_text = "".join(output_list + text_list)
    print(output_text, end="", flush=True)


class ExampleClient(Client):
    async def request_permission(
        self,
        options: list[PermissionOption],
        session_id: str,
        tool_call: ToolCall,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        raise RequestError.method_not_found("session/request_permission")

    async def write_text_file(
        self, content: str, path: str, session_id: str, **kwargs: Any
    ) -> WriteTextFileResponse | None:
        raise RequestError.method_not_found("fs/write_text_file")

    async def read_text_file(
        self,
        path: str,
        session_id: str,
        limit: int | None = None,
        line: int | None = None,
        **kwargs: Any,
    ) -> ReadTextFileResponse:
        raise RequestError.method_not_found("fs/read_text_file")

    async def create_terminal(
        self,
        command: str,
        session_id: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: list[EnvVariable] | None = None,
        output_byte_limit: int | None = None,
        **kwargs: Any,
    ) -> CreateTerminalResponse:
        raise RequestError.method_not_found("terminal/create")

    async def terminal_output(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> TerminalOutputResponse:
        raise RequestError.method_not_found("terminal/output")

    async def release_terminal(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> ReleaseTerminalResponse | None:
        raise RequestError.method_not_found("terminal/release")

    async def wait_for_terminal_exit(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> WaitForTerminalExitResponse:
        raise RequestError.method_not_found("terminal/wait_for_exit")

    async def kill_terminal(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> KillTerminalCommandResponse | None:
        raise RequestError.method_not_found("terminal/kill")

    async def session_update(
        self,
        session_id: str,
        update: UserMessageChunk
        | AgentMessageChunk
        | AgentThoughtChunk
        | ToolCallStart
        | ToolCallProgress
        | AgentPlanUpdate
        | AvailableCommandsUpdate
        | CurrentModeUpdate,
        **kwargs: Any,
    ) -> None:
        if isinstance(update, AgentMessageChunk):
            content = update.content
            text: str
            if isinstance(content, TextContentBlock):
                text = content.text
            elif isinstance(content, ImageContentBlock):
                text = "<image>"
            elif isinstance(content, AudioContentBlock):
                text = "<audio>"
            elif isinstance(content, ResourceContentBlock):
                text = content.uri or "<resource>"
            elif isinstance(content, EmbeddedResourceContentBlock):
                text = "<resource>"
            else:
                text = "<content>"
            display_text(text, color=PURPLE_DEEP)

        elif isinstance(update, AgentThoughtChunk):
            content = update.content
            text: str
            if isinstance(content, TextContentBlock):
                text = content.text
            else:
                text = "<content>"
            display_text(text, color=DIM_GREEN, styles=[ITALIC])
        else:
            display_text(str(update), color=RED, styles=[BOLD])

    async def ext_method(self, method: str, params: dict) -> dict:
        raise RequestError.method_not_found(method)

    async def ext_notification(self, method: str, params: dict) -> None:
        raise RequestError.method_not_found(method)


async def read_console(prompt: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: input(prompt))


async def interactive_loop(conn: ClientSideConnection, session_id: str) -> None:
    while True:
        try:
            line = await read_console("> ")
        except EOFError:
            break
        except KeyboardInterrupt:
            print("", file=sys.stderr)
            break

        if not line:
            continue

        try:
            await conn.prompt(
                session_id=session_id,
                prompt=[text_block(line)],
            )
        except Exception as exc:
            logging.error("Prompt failed: %s", exc)  # noqa: TRY400


async def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO)

    if len(argv) < 2:
        print(
            "Usage: python examples/client.py AGENT_PROGRAM [ARGS...]", file=sys.stderr
        )
        return 2

    program = argv[1]
    args = argv[2:]

    program_path = Path(program)
    spawn_program = program
    spawn_args = args

    if program_path.exists() and not os.access(program_path, os.X_OK):
        spawn_program = sys.executable
        spawn_args = [str(program_path), *args]

    proc = await asyncio.create_subprocess_exec(
        spawn_program,
        *spawn_args,
        stdin=aio_subprocess.PIPE,
        stdout=aio_subprocess.PIPE,
    )

    if proc.stdin is None or proc.stdout is None:
        print("Agent process does not expose stdio pipes", file=sys.stderr)
        return 1

    client_impl = ExampleClient()
    conn = connect_to_agent(client_impl, proc.stdin, proc.stdout)

    await conn.initialize(
        protocol_version=PROTOCOL_VERSION,
        client_capabilities=ClientCapabilities(),
        client_info=Implementation(
            name="example-client", title="Example Client", version="0.1.0"
        ),
    )
    session = await conn.new_session(mcp_servers=[], cwd=os.getcwd())

    await interactive_loop(conn, session.session_id)

    if proc.returncode is None:
        proc.terminate()
        with contextlib.suppress(ProcessLookupError):
            await proc.wait()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv)))

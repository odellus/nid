from fastmcp import FastMCP

mcp = FastMCP(
    name="crow-mcp",
    instructions="""
        A comprehensive MCP server for coding agent tools, including:
            - file_editor
            File editor for viewing, creating, and editing files.

            Commands:
            - view: View file or directory (cat -n style)
            - create: Create new file (fails if exists)
            - str_replace: Replace exact string match
            - insert: Insert text after line number
            - undo_edit: Undo last edit

            Args:
                command: The command to run
                path: Absolute path to file or directory
                file_text: Content for create command
                view_range: [start, end] line range for view (optional)
                old_str: String to replace for str_replace
                new_str: New string for str_replace or insert
                insert_line: Line number to insert after (0 = beginning)

            Returns:
                Result message with context

            - terminal
            command: str = Field(
                description="The bash command to execute. Can be empty string to view additional logs when previous exit code is `-1`. Can be `C-c` (Ctrl+C) to interrupt the currently running process. Note: You can only execute one bash command at a time. If you need to run multiple commands sequentially, you can use `&&` or `;` to chain them together."  # noqa
            )
            is_input: bool = Field(
                default=False,
                description="If True, the command is an input to the running process. If False, the command is a bash command to be executed in the terminal. Default is False.",  # noqa
            )
            timeout: float | None = Field(
                default=None,
                ge=0,
                description=f"Optional. Sets a maximum time limit (in seconds) for running the command. If the command takes longer than this limit, you’ll be asked whether to continue or stop it. If you don’t set a value, the command will instead pause and ask for confirmation when it produces no new output for {NO_CHANGE_TIMEOUT_SECONDS} seconds. Use a higher value if the command is expected to take a long time (like installation or testing), or if it has a known fixed duration (like sleep).",  # noqa
            )
            reset: bool = Field(
                default=False,
                description="If True, reset the terminal by creating a new session. Use this only when the terminal becomes unresponsive. Note that all previously set environment variables and session state will be lost after reset. Cannot be used with is_input=True.",  # noqa
            )

            - web_fetch
            - web_search
    """,
)


def main():
    mcp.run()


if __name__ == "__main__":
    main()

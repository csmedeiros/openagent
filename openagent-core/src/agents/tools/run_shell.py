import asyncio
import subprocess
from langchain.tools import tool
from agents.utils.logging import logger
import os

# Workspace root - consistent with coder.py
WORKSPACE_ROOT = r"C:\Users\caiosmedeiros\Documents"


def _run_command_sync(command: str, cwd: str, timeout: float = 60.0) -> str:
    """Runs a shell command synchronously. Called from a thread to avoid event loop issues."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            errors='replace'
        )

        output = f"Exit code: {result.returncode}\n\n"

        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n\n"

        if result.stderr:
            output += f"STDERR:\n{result.stderr}"

        return output.strip()

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds"


@tool(parse_docstring=True)
async def shell_tool(command: str, cwd: str = None) -> str:
    """
    Executes a shell command and returns the output.

    Args:
        command: The shell command to execute
        cwd: Optional working directory for the command. Defaults to the workspace root directory.
    """
    # Default to workspace root directory
    if cwd is None:
        cwd = WORKSPACE_ROOT

    # Validate that cwd exists
    if not os.path.isdir(cwd):
        return f"Error: Working directory '{cwd}' does not exist."

    try:
        logger.debug(f"Running shell command in {cwd}: {command}")

        # Use asyncio.to_thread to run subprocess synchronously in a separate thread.
        # This avoids the NotImplementedError that asyncio.create_subprocess_shell
        # raises on Windows when using SelectorEventLoop (common in LangGraph).
        result = await asyncio.to_thread(_run_command_sync, command, cwd)

        logger.debug(f"Command completed")
        return result

    except Exception as e:
        logger.error(f"Error executing command '{command}': {str(e)}", exc_info=True)
        return f"Error executing command ({type(e).__name__}): {str(e)}"


import asyncio
from langchain.tools import tool
from agents.utils.logging import logger
import os

@tool(parse_docstring=True)
async def shell_tool(command: str, cwd: str = None) -> str:
    """
    Executes a shell command asynchronously and returns the output.

    Args:
        command: The shell command to execute
        cwd: Optional working directory for the command. Defaults to workspace tests directory.
    """
    # Default to workspace tests directory
    if cwd is None:
        cwd = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests")

    try:
        logger.debug(f"Running shell command in {cwd}: {command}")


        # Create subprocess
        process = await asyncio.create_subprocess_shell(
            command.replace("\"", ""),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )

        # Wait for completion with timeout
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=60.0  # 60 second timeout
        )

        # Decode output
        stdout_str = stdout.decode('utf-8', errors='replace')
        stderr_str = stderr.decode('utf-8', errors='replace')

        # Build result message
        result = f"Exit code: {process.returncode}\n\n"

        if stdout_str:
            result += f"STDOUT:\n{stdout_str}\n\n"

        if stderr_str:
            result += f"STDERR:\n{stderr_str}"

        logger.debug(f"Command completed with exit code {process.returncode}")
        return result.strip()

    except asyncio.TimeoutError:
        logger.error(f"Command timeout after 60s: {command}")
        return f"Error: Command timed out after 60 seconds"

    except Exception as e:
        logger.error(f"Error executing command '{command}': {str(e)}", exc_info=True)
        return f"Error executing command: {str(e)}"

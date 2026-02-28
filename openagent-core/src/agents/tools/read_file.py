import os
from langchain.tools import tool, InjectedToolCallId
import aiofiles
from langchain.messages import ToolMessage
from langgraph.types import Command

from typing import Annotated

# Workspace root - consistent with coder.py and shell_tool
WORKSPACE_ROOT = r"C:\Users\caiosmedeiros\Documents"

@tool(parse_docstring=True)
async def read_file(file_path: str, start: int, end: int, tool_call_id: Annotated[str, InjectedToolCallId]) -> str:
    """
    Reads a text-readable file content.

    Args:
        file_path: Path to the file to read
        start: Starting line number (1-indexed, required)
        end: Ending line number (1-indexed, inclusive, required)
    """
    # Resolve relative paths against workspace root
    if not os.path.isabs(file_path):
        file_path = os.path.join(WORKSPACE_ROOT, file_path)

    try:
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()
            lines = content.splitlines(keepends=True)

        # Convert to 0-indexed and handle bounds
        start_idx = max(0, start - 1)
        end_idx = min(len(lines), end)

        # Validate range
        if start_idx >= len(lines):
            return f"Error: Start line {start} is beyond the file length ({len(lines)} lines)"

        if start_idx > end_idx:
            return f"Error: Start line ({start}) cannot be greater than end line ({end})"

        # Get the slice of lines
        selected_lines = lines[start_idx:end_idx]

        # Calculate the width needed for line numbers
        max_line_num = start_idx + len(selected_lines)
        line_num_width = len(str(max_line_num))

        # Format with line numbers (VSCode style)
        formatted_lines = []
        for i, line in enumerate(selected_lines, start=start_idx + 1):
            # Remove trailing newline for formatting, add it back after
            line_content = line.rstrip('\n')
            formatted_line = f"{i:>{line_num_width}}→{line_content}"
            formatted_lines.append(formatted_line)

        content = '\n'.join(formatted_lines)

        # Build header with line statistics
        lines_read = len(selected_lines)
        total_lines = len(lines)
        range_info = f" (lines {start_idx + 1}-{end_idx})"
        stats_info = f"{lines_read} lines out of {total_lines} total lines"

        return Command(
            update={
                "messages": [ToolMessage(content=f"Content of file {file_path}{range_info}:\n{stats_info}\n\n{content}", tool_call_id=tool_call_id)],
                "files": [file_path]
            }
        )
    
    except FileNotFoundError:
        return f"File {file_path} does not exist. Please check the file_path argument."
    except Exception as e:
        return f"Error reading file {file_path}:\n\n{str(e)}"
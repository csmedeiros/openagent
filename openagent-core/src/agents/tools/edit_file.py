import os
from langchain.tools import tool, InjectedToolCallId
from agents.utils.logging import logger
import aiofiles
from langgraph.types import Command
from langchain.messages import ToolMessage
from typing import Annotated

# Workspace root — override with the WORKSPACE_ROOT environment variable
WORKSPACE_ROOT = os.environ.get("WORKSPACE_ROOT", os.path.expanduser("~/Documents/openagent-tests"))


@tool(parse_docstring=True)
async def edit_file(
    file_path: str,
    start_line: int,
    end_line: int,
    new_content: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> str:
    """
    Replaces a range of lines in a file with new content.

    Use read_file first to see line numbers, then call this tool to replace
    the exact lines you want to change.

    Args:
        file_path: Path to the file to edit.
        start_line: First line to replace (1-indexed, inclusive).
        end_line: Last line to replace (1-indexed, inclusive).
        new_content: The new text that will replace lines start_line..end_line.
                     Do NOT include a trailing newline — the tool handles line endings.
    """
    # Resolve relative paths against workspace root
    if not os.path.isabs(file_path):
        file_path = os.path.join(WORKSPACE_ROOT, file_path)

    try:
        # ── Read existing file ──────────────────────────────────────────
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()

        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        # ── Validate range ──────────────────────────────────────────────
        if start_line < 1:
            return f"Error: start_line must be >= 1 (got {start_line})."
        if end_line < start_line:
            return f"Error: end_line ({end_line}) must be >= start_line ({start_line})."
        if start_line > total_lines + 1:
            return (
                f"Error: start_line {start_line} is beyond the file length "
                f"({total_lines} lines). Use write_file to append instead."
            )

        # ── Build new line list ─────────────────────────────────────────
        # Lines before the edited block
        before = lines[: start_line - 1]

        # New lines — ensure each ends with \n (except possibly the last)
        new_lines_raw = new_content.splitlines(keepends=False)
        new_lines: list[str] = []
        for i, nl in enumerate(new_lines_raw):
            # All but last line always get \n; last gets \n only if file did
            new_lines.append(nl + "\n")

        # If the replacement ends with a blank last entry (user typed trailing \n)
        # splitlines above already handles that correctly.

        # Lines after the edited block (end_line is inclusive, 1-indexed)
        after = lines[min(end_line, total_lines):]

        new_file_lines = before + new_lines + after
        new_file_content = "".join(new_file_lines)

        # ── Write back ─────────────────────────────────────────────────
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(new_file_content)

        # ── Build confirmation with preview ────────────────────────────
        replaced_count = end_line - start_line + 1
        inserted_count = len(new_lines)
        delta = inserted_count - replaced_count

        delta_msg = (
            f"({'+' if delta >= 0 else ''}{delta} lines)"
            if delta != 0
            else "(same line count)"
        )

        # Show the edited region in the result
        preview_start = max(0, start_line - 2)
        preview_end = min(len(new_file_lines), start_line - 1 + inserted_count + 2)
        preview_lines = new_file_lines[preview_start:preview_end]
        w = len(str(preview_start + len(preview_lines)))
        preview = "\n".join(
            f"{preview_start + i + 1:>{w}}→{ln.rstrip()}"
            for i, ln in enumerate(preview_lines)
        )

        msg = (
            f"Edited {file_path}: replaced lines {start_line}–{end_line} "
            f"with {inserted_count} line(s) {delta_msg}.\n\n"
            f"Preview around edit:\n{preview}"
        )

        logger.debug(msg)

        return Command(
            update={
                "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
                "files": [file_path],
            }
        )

    except FileNotFoundError:
        return f"File {file_path} does not exist. Use write_file to create it first."
    except Exception as e:
        logger.error(f"Error editing file {file_path}: {e}", exc_info=True)
        return f"Error editing file {file_path}:\n{e}"

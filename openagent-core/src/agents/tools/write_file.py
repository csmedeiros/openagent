import os
from langchain.tools import tool, InjectedToolCallId
from agents.utils.logging import logger
import aiofiles
from langgraph.types import Command
from langchain.messages import ToolMessage
from typing import Annotated

@tool()
async def write_file(file_path: str, content: str, tool_call_id: Annotated[str, InjectedToolCallId], append: bool = False) -> str:
    """
    Writes content to a file.

    Args:
        file_path: Path to the file to write
        content: Content to write to the file
        append: If True, appends to the end of the file. If False, overwrites the file.
    """
    if append:
        try:
            logger.debug(f"Attempting to append content to file: {file_path}")
            async with aiofiles.open(file_path, "a") as f:
                await f.write("\n" + content)
            logger.debug(f"Successfully appended content to file: {file_path}")
            return Command(
                    update={
                        "messages": [ToolMessage(content=f"Content added in the end of file {file_path}", tool_call_id=tool_call_id)],
                        "files": [file_path]
                    }
                )
        except PermissionError as e:
            logger.error(f"Permission denied when appending to file {file_path}: {str(e)}")
            return f"Permission denied to append to {file_path}"
        except Exception as e:
            logger.error(f"Error appending content to file {file_path}: {str(e)}", exc_info=True)
            return f"Error adding content to file {file_path}:\n{str(e)}"

    try:
        logger.debug(f"Attempting to create/overwrite file: {file_path}")
        async with aiofiles.open(file_path, "w") as f:
            await f.write("\n" + content)
        logger.debug(f"Successfully created/overwritten file: {file_path}")
        return Command(
            update={
                "messages": [ToolMessage(content=f"File {file_path} created.", tool_call_id=tool_call_id)],
                "files": [file_path]
            }
        )

    except PermissionError as e:
        logger.error(f"Permission denied when writing to file {file_path}: {str(e)}")
        return f"Permission denied to write in {file_path}"
    except Exception as e:
        logger.error(f"Error creating file {file_path}: {str(e)}", exc_info=True)
        return f"Error creating file {file_path}:\n{str(e)}"
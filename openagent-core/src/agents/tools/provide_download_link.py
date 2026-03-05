import os
from langchain.tools import tool
import urllib.parse

# Workspace root — override with the WORKSPACE_ROOT environment variable
WORKSPACE_ROOT = os.environ.get("WORKSPACE_ROOT", os.path.join(os.path.expanduser("~"), "Documents", "openagent_tests"))

@tool(parse_docstring=True)
def provide_download_link(file_path: str, text: str) -> str:
    """
    Generates a clickable markdown link for a local file so the user can open or download it.

    Args:
        file_path: The absolute or relative path to the file.
        text: The text to be displayed for the clickable link.
    """
    # Resolve relative paths against workspace root
    if not os.path.isabs(file_path):
        file_path = os.path.join(WORKSPACE_ROOT, file_path)
    
    # Normalize path
    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        return f"Error: The file {file_path} does not exist."

    # Convert Windows paths to proper file URI format
    # format: file:///C:/path/to/file.ext
    uri_path = urllib.parse.quote(file_path.replace('\\', '/'))
    file_uri = f"file:///{uri_path}" if os.name == 'nt' else f"file://{uri_path}"

    markdown_link = f"[{text}]({file_uri})"
    return f"Link generated successfully. You can include this in your final response to the user:\n{markdown_link}"

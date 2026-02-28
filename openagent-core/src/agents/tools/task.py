"""
This module creates the message delegation tool for agent communication.
"""

from langgraph.types import Command
from typing import Literal, Annotated
from langchain.tools import InjectedState, InjectedToolCallId, tool
from langchain.messages import HumanMessage, ToolMessage

@tool(parse_docstring=True)
async def message(agent: Literal['coder', 'researcher'], message: str, state: Annotated[dict, InjectedState], tool_call_id: Annotated[str, InjectedToolCallId]):
    """Sends a message to a specialized agent for conversation and task delegation.

    Args:
        agent: The specialized agent to communicate with ('coder' or 'researcher')
        message: The message content to send to the agent
    """
    from agents.researcher import researcher
    from agents.coder import coder

    # Select subagent
    subagent = researcher if agent == 'researcher' else coder

    # Build message with context
    message_string = \
    f"""
    ### Message from OpenAgent

    I am the OpenAgent, a general purpose AI Agent that orchestrates specialized agents
    to attend user requested tasks.

    """

    if state.get('files'):
        message_string += \
            f"""
            Here is a list of files that have been used during the conversation with the user:
            {"\n".join(state['files'])}

            """

    message_string += \
    f"""
    ## Your task:

    {message}
    """

    # Prepare subagent state (exclude 'messages' and 'todos' like deepagents does)
    subagent_state = {k: v for k, v in state.items() if k not in ('messages', 'todos')}
    subagent_state['messages'] = [HumanMessage(content=message_string)]

    # Invoke subagent with recursion_limit config
    config = {"recursion_limit": 300}
    result = await subagent.ainvoke(subagent_state, config=config)

    # Extract last message from subagent and create ToolMessage (like deepagents does)
    last_message_text = result['messages'][-1].text

    # Return Command with state update and ToolMessage (following deepagents pattern)
    state_update = {k: v for k, v in result.items() if k not in ('messages', 'todos')}
    return Command(
        update={
            **state_update,
            "messages": [ToolMessage(content=last_message_text, tool_call_id=tool_call_id)]
        }
    )
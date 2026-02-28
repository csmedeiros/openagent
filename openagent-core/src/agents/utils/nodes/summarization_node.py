"""
Summarization node for LangGraph.

Provides a conditional edge (should_summarize) and a summarization node
(summarize_messages_node) that reduces message history when it grows too large.
Uses message grouping to ensure tool_use/tool_result pairs are never broken.
"""

from langchain.agents.middleware.summarization import DEFAULT_SUMMARY_PROMPT
from langchain.messages import HumanMessage, SystemMessage, AIMessage, RemoveMessage, ToolMessage, trim_messages
from langgraph.graph import MessagesState

from agents.utils.message_truncation import group_messages, _estimate_message_tokens

# Trigger: summarize when estimated tokens exceed this
SUMMARIZATION_TOKEN_TRIGGER = 100000
# After summarization, keep approximately this many estimated tokens
TOKENS_TO_KEEP_AFTER_SUMMARY = 20000

# Import centralized model configuration
from agents.models import model

token_counter = model.get_num_tokens_from_messages


def should_summarize(state: MessagesState) -> str:
    """
    Conditional edge: returns 'summarize' if estimated tokens exceed trigger,
    'agent' otherwise.
    """
    messages = state.get("messages", [])

    if not messages:
        return "agent"

    total_tokens = token_counter(messages)
    if total_tokens >= SUMMARIZATION_TOKEN_TRIGGER:
        return "summarize"

    return "agent"


def summarize_messages_node(state: MessagesState) -> dict:
    """
    Summarization node that reduces message history.

    Uses group-based approach to find a safe cutoff point, then removes
    old messages via RemoveMessage. Generates a brief summary if possible,
    otherwise just drops old messages with a truncation notice.
    """
    messages = state.get("messages", [])

    if not messages:
        return {"messages": []}
        
    trimmed_messages = trim_messages(
            messages=messages,
            max_tokens=TOKENS_TO_KEEP_AFTER_SUMMARY,
            strategy='last',
            start_on=['human', 'ai', 'tool'],
            token_counter='approximate',
            include_system=True,
            allow_partial=False
        )

    # Identify removed messages (in original but not in trimmed)
    trimmed_ids = {m.id for m in trimmed_messages}
    removed_messages = [m for m in messages if m.id not in trimmed_ids]

    # Format removed messages for the summary prompt
    formatted = "\n".join([
        f"{msg.__class__.__name__}: {str(msg.content)[:200]}"
        for msg in removed_messages
        if hasattr(msg, 'content') and msg.content
        and not isinstance(msg, ToolMessage)
    ])

    # Hard limit on summary input
    if len(formatted) > 5000:
        formatted = formatted[:5000] + "\n... [truncated]"

    try:
        response = model.invoke(DEFAULT_SUMMARY_PROMPT.format(messages=formatted))
        summary_text = response.content.strip()
        summary = HumanMessage(
            content=f"[CONVERSATION SUMMARY]\n\n{summary_text}\n\n[END OF SUMMARY]"
        )
        
        return {"messages": trimmed_messages + [summary]}

    except Exception as e:
        print(f"Error generating summary: {e!s}")
        fallback = HumanMessage(
            content="[Previous conversation was truncated. Continue from the recent messages.]"
        )
        return {"messages": trimmed_messages + [fallback]}
"""
Message truncation utility.

Provides a hard safety net that truncates messages before sending to the LLM,
ensuring we never exceed the API's token limit.

Two levels of protection:
1. Truncate the number of message groups (tool pairs) to fit within token budget
2. Truncate individual message CONTENT if any single message is too large
"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


# Max estimated tokens to keep in the message history.
# Conservative: 30k estimated ≈ ~90k chars ≈ 30-45k real tokens.
# With system prompt + tool schemas (~10k tokens), total stays well under 200k.
MAX_CONTEXT_TOKENS = 30_000

# Max chars for any single message content. Prevents one massive tool response
# from consuming the entire context. ~30k chars ≈ 10k tokens.
MAX_SINGLE_MESSAGE_CHARS = 30_000


def _estimate_message_tokens(msg) -> int:
    """
    Estimate tokens for an entire message, including content AND tool_calls.

    Uses a conservative ratio of 3 chars per token.
    """
    total_chars = 0

    # Count content
    content = getattr(msg, 'content', None)
    if content:
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            total_chars += sum(len(str(block)) for block in content)
        else:
            total_chars += len(str(content))

    # Count tool_calls (critical for AIMessages — args can be huge)
    tool_calls = getattr(msg, 'tool_calls', None)
    if tool_calls:
        for tc in tool_calls:
            if isinstance(tc, dict):
                total_chars += len(str(tc.get('name', '')))
                total_chars += len(str(tc.get('args', {})))
            else:
                total_chars += len(str(tc))

    # Count additional_kwargs (some tool data stored here in older langchain)
    additional = getattr(msg, 'additional_kwargs', None)
    if additional:
        ak_tool_calls = additional.get('tool_calls', [])
        if ak_tool_calls:
            total_chars += len(str(ak_tool_calls))

    # Conservative: 3 chars per token
    return max(total_chars // 3, 1)


def group_messages(messages: list) -> list[list]:
    """
    Groups messages into logical units that must stay together.

    A group is either:
    - A standalone message (HumanMessage, AIMessage without tool_calls)
    - An AIMessage with tool_calls + ALL its following ToolMessage responses

    This ensures we never break tool_use/tool_result pairs required by the Anthropic API.
    """
    groups = []
    i = 0

    while i < len(messages):
        msg = messages[i]

        if isinstance(msg, AIMessage) and getattr(msg, 'tool_calls', None):
            group = [msg]
            i += 1
            while i < len(messages) and isinstance(messages[i], ToolMessage):
                group.append(messages[i])
                i += 1
            groups.append(group)
        else:
            groups.append([msg])
            i += 1

    return groups


def _truncate_message_content(msg):
    """
    Truncate a single message's content if it exceeds MAX_SINGLE_MESSAGE_CHARS.
    Returns a new message with truncated content, or the original if no truncation needed.
    """
    content = getattr(msg, 'content', None)
    if not content or not isinstance(content, str):
        return msg

    if len(content) <= MAX_SINGLE_MESSAGE_CHARS:
        return msg

    truncated = content[:MAX_SINGLE_MESSAGE_CHARS] + \
        f"\n\n... [TRUNCATED: original was {len(content)} chars, showing first {MAX_SINGLE_MESSAGE_CHARS}]"

    # Create new message of same type with truncated content
    if isinstance(msg, ToolMessage):
        return ToolMessage(
            content=truncated,
            tool_call_id=msg.tool_call_id,
            id=msg.id,
        )
    elif isinstance(msg, AIMessage):
        new_msg = AIMessage(
            content=truncated,
            tool_calls=getattr(msg, 'tool_calls', []),
            id=msg.id,
        )
        return new_msg
    elif isinstance(msg, HumanMessage):
        return HumanMessage(content=truncated, id=msg.id)

    return msg


def truncate_messages(messages: list, max_tokens: int = MAX_CONTEXT_TOKENS) -> list:
    """
    Hard-cap messages to fit within token limits.

    1. Groups messages into logical units (tool pairs stay together)
    2. Keeps groups from the end until hitting the token limit
    3. Truncates individual message content if any single message is too large

    Args:
        messages: List of LangChain messages
        max_tokens: Maximum estimated tokens to keep

    Returns:
        Truncated list of messages that fits within the limit
    """
    if not messages:
        return messages

    # STEP 1: Truncate individual large messages first
    messages = [_truncate_message_content(m) for m in messages]

    # STEP 2: Check if we're now under the limit
    total_tokens = sum(_estimate_message_tokens(m) for m in messages)
    if total_tokens <= max_tokens:
        return messages

    # STEP 3: Group messages and keep from the end
    groups = group_messages(messages)

    kept_groups = []
    accumulated_tokens = 0

    for group in reversed(groups):
        group_tokens = sum(_estimate_message_tokens(m) for m in group)

        # Stop if adding this group would exceed the limit (and we already have some)
        if accumulated_tokens + group_tokens > max_tokens and kept_groups:
            break

        kept_groups.insert(0, group)
        accumulated_tokens += group_tokens

    # Flatten groups back to message list
    result = []
    for group in kept_groups:
        result.extend(group)

    # STEP 4: If we still exceed (single massive group), force-truncate all messages
    final_tokens = sum(_estimate_message_tokens(m) for m in result)
    if final_tokens > max_tokens:
        # Nuclear option: aggressively truncate all content
        aggressive_limit = max_tokens * 3 // len(result) if result else MAX_SINGLE_MESSAGE_CHARS
        aggressive_limit = max(1000, min(aggressive_limit, MAX_SINGLE_MESSAGE_CHARS))

        truncated_result = []
        for m in result:
            content = getattr(m, 'content', '')
            if isinstance(content, str) and len(content) > aggressive_limit:
                if isinstance(m, ToolMessage):
                    truncated_result.append(ToolMessage(
                        content=content[:aggressive_limit] + f"\n[TRUNCATED to {aggressive_limit} chars]",
                        tool_call_id=m.tool_call_id,
                        id=m.id,
                    ))
                else:
                    truncated_result.append(m)
            else:
                truncated_result.append(m)
        result = truncated_result

    # Prepend truncation notice if we removed anything
    if len(result) < len(messages):
        notice = HumanMessage(
            content="[NOTICE: Earlier conversation history was truncated to fit context limits. Continue working based on the messages below.]"
        )
        result.insert(0, notice)

    return result

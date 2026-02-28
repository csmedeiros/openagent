"""
Standalone test for message truncation logic — no external dependencies.
Uses mock message classes to test the pure logic.
Tests the EXACT functions from message_truncation.py.
"""
import sys
import os

# ============================================================
# Mock classes that match langchain's interface
# ============================================================
class HumanMessage:
    def __init__(self, content="", id=None):
        self.content = content
        self.id = id or f"hm_{id.__class__}"
        self.tool_calls = []
        self.additional_kwargs = {}

class AIMessage:
    def __init__(self, content="", tool_calls=None, id=None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.additional_kwargs = {}
        self.id = id or f"ai_{object.__hash__(self)}"

class ToolMessage:
    def __init__(self, content="", tool_call_id="", id=None):
        self.content = content
        self.tool_call_id = tool_call_id
        self.id = id or f"tm_{object.__hash__(self)}"
        self.tool_calls = []
        self.additional_kwargs = {}

# ============================================================
# Patch langchain_core.messages so the import doesn't fail
# ============================================================
import types

mock_messages = types.ModuleType("langchain_core.messages")
mock_messages.AIMessage = AIMessage
mock_messages.HumanMessage = HumanMessage
mock_messages.ToolMessage = ToolMessage

mock_core = types.ModuleType("langchain_core")
mock_core.messages = mock_messages

sys.modules["langchain_core"] = mock_core
sys.modules["langchain_core.messages"] = mock_messages

# Now import the actual code
src_dir = r"C:\Users\caiosmedeiros\Documents\Projetos Pessoais\openagent\openagent-core\src\agents\utils"
sys.path.insert(0, src_dir)

from message_truncation import (
    truncate_messages,
    group_messages,
    _estimate_message_tokens,
    _truncate_message_content,
    MAX_CONTEXT_TOKENS,
    MAX_SINGLE_MESSAGE_CHARS,
)

# ============================================================
# TESTS
# ============================================================
passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}" + (f" ({detail})" if detail else ""))
    else:
        failed += 1
        print(f"  FAIL: {name}" + (f" ({detail})" if detail else ""))


print("=" * 60)
print(f"MAX_CONTEXT_TOKENS = {MAX_CONTEXT_TOKENS}")
print(f"MAX_SINGLE_MESSAGE_CHARS = {MAX_SINGLE_MESSAGE_CHARS}")
print("=" * 60)


# --- TEST 1: Token estimation counts tool_calls ---
print("\nTEST 1: Token estimation counts tool_calls")
ai = AIMessage(content="", tool_calls=[{"id": "t", "name": "write_file", "args": {"content": "x" * 30000}}])
tokens = _estimate_message_tokens(ai)
check("30k char tool_call estimated correctly", tokens >= 5000, f"{tokens} tokens")
check("Content-only would be wrong", len(ai.content) // 3 < 10, f"content-only={len(ai.content)//3}")


# --- TEST 2: Grouping ---
print("\nTEST 2: Message grouping")
msgs = [
    HumanMessage("Hi"),
    AIMessage("", tool_calls=[{"id": "t1", "name": "shell", "args": {"cmd": "ls"}}]),
    ToolMessage("output", tool_call_id="t1"),
    AIMessage("", tool_calls=[{"id": "t2", "name": "read", "args": {"path": "f.txt"}}]),
    ToolMessage("data", tool_call_id="t2"),
    AIMessage("Done!"),
]
g = group_messages(msgs)
check("Correct group count", len(g) == 4, f"expected 4, got {len(g)}")
check("Tool group has 2 msgs", len(g[1]) == 2)


# --- TEST 3: Individual message truncation ---
print("\nTEST 3: Individual message content truncation")
big_tool = ToolMessage(content="x" * 100000, tool_call_id="t1")
truncated = _truncate_message_content(big_tool)
check("Truncated to limit", len(truncated.content) < 100000, f"{len(truncated.content)} chars")
check("Truncation marker present", "TRUNCATED" in truncated.content)
check("Tool call id preserved", truncated.tool_call_id == "t1")

small_msg = HumanMessage("hello")
check("Small msg unchanged", _truncate_message_content(small_msg).content == "hello")


# --- TEST 4: Large context gets truncated ---
print("\nTEST 4: Large context truncation")
msgs = [HumanMessage("Start")]
for i in range(50):
    args = "x" * 10000
    msgs.extend([
        AIMessage("", tool_calls=[{"id": f"t{i}", "name": "shell", "args": {"cmd": args}}]),
        ToolMessage("output " * 1400, tool_call_id=f"t{i}"),
    ])
msgs.append(AIMessage("End"))

before = sum(_estimate_message_tokens(m) for m in msgs)
result = truncate_messages(msgs)
after = sum(_estimate_message_tokens(m) for m in result)

check("Tokens reduced", after < before, f"{before} -> {after}")
check("Under MAX_CONTEXT_TOKENS", after <= MAX_CONTEXT_TOKENS + 500, f"{after} <= {MAX_CONTEXT_TOKENS}")
check("Message count reduced", len(result) < len(msgs), f"{len(msgs)} -> {len(result)}")


# --- TEST 5: Tool pairs preserved ---
print("\nTEST 5: Tool pairs preserved after truncation")
# Check no orphaned ToolMessages
orphaned = False
for i, m in enumerate(result):
    if isinstance(m, ToolMessage):
        found_parent = False
        for j in range(i - 1, -1, -1):
            if isinstance(result[j], AIMessage) and result[j].tool_calls:
                found_parent = True
                break
            if not isinstance(result[j], ToolMessage):
                break
        if not found_parent:
            orphaned = True
            break
check("No orphaned ToolMessages", not orphaned)


# --- TEST 6: Single MASSIVE message ---
print("\nTEST 6: Single massive ToolMessage (the actual bug)")
msgs = [
    HumanMessage("Process files"),
    AIMessage("", tool_calls=[{"id": "tg", "name": "glob", "args": {"pattern": "*.txt"}}]),
    ToolMessage("path/file.txt\n" * 100000, tool_call_id="tg"),  # ~1.4M chars!
]
before = sum(_estimate_message_tokens(m) for m in msgs)
result = truncate_messages(msgs)
after = sum(_estimate_message_tokens(m) for m in result)

# Even with 1.5x underestimate, should be well under 200k
worst_case = int(after * 1.5) + 15000  # + system prompt + tools
check("Massive msg handled", after <= MAX_CONTEXT_TOKENS + 500, f"{before} -> {after}")
check("Worst case under 200k", worst_case <= 200000, f"worst case = {worst_case}")


# --- TEST 7: Extreme scenario (simulating 248k+ real tokens) ---
print("\nTEST 7: Extreme scenario (simulating 248k+ tokens)")
msgs = [HumanMessage("Process DCRe")]
# Glob: 75k chars
msgs.extend([
    AIMessage("", tool_calls=[{"id": "tg", "name": "glob", "args": {"p": "*.txt"}}]),
    ToolMessage("/path/to/file.txt\n" * 5000, tool_call_id="tg"),
])
# 30 read_file: 20k chars each
for i in range(30):
    msgs.extend([
        AIMessage("", tool_calls=[{"id": f"tr{i}", "name": "read", "args": {"path": f"f{i}", "s": 1, "e": 500}}]),
        ToolMessage("x" * 20000, tool_call_id=f"tr{i}"),
    ])
# 10 write_file: 15k chars in args each
for i in range(10):
    msgs.extend([
        AIMessage("", tool_calls=[{"id": f"tw{i}", "name": "write", "args": {"path": f"out{i}", "content": "code\n" * 3000}}]),
        ToolMessage("File created.", tool_call_id=f"tw{i}"),
    ])

before = sum(_estimate_message_tokens(m) for m in msgs)
result = truncate_messages(msgs)
after = sum(_estimate_message_tokens(m) for m in result)
worst_case = int(after * 1.5) + 15000

check("Extreme: under MAX_CONTEXT_TOKENS", after <= MAX_CONTEXT_TOKENS + 500, f"{before} -> {after}")
check("Extreme: worst case under 200k", worst_case <= 200000, f"worst_case = {worst_case}")


# --- TEST 8: Small context unchanged ---
print("\nTEST 8: Small context unchanged")
msgs = [HumanMessage("Hi"), AIMessage("Hello")]
result = truncate_messages(msgs)
check("Unchanged", len(result) == 2)


# --- SUMMARY ---
print("\n" + "=" * 60)
total = passed + failed
if failed == 0:
    print(f"ALL {passed} CHECKS PASSED")
else:
    print(f"{passed}/{total} checks passed, {failed} FAILED")
print("=" * 60)

sys.exit(1 if failed > 0 else 0)

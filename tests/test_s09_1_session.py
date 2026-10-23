import copy
import importlib.util
import json
import os
import sys
import tempfile
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / "s09_1_session" / "harness.py"


def load_harness(workdir: Path):
    fake_anthropic = types.ModuleType("anthropic")

    class FakeBedrock:
        def __init__(self, *args, **kwargs):
            self.messages = types.SimpleNamespace(create=None, stream=None)

    class FakePermissionDenied(Exception):
        pass

    fake_anthropic.AnthropicBedrock = FakeBedrock
    fake_anthropic.PermissionDeniedError = FakePermissionDenied
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda override=True: None

    saved = {name: sys.modules.get(name) for name in ("anthropic", "dotenv")}
    saved_env = {key: os.environ.get(key) for key in ("MODEL_ID", "AGENT_WORKDIR")}
    previous_cwd = Path.cwd()
    sys.modules["anthropic"] = fake_anthropic
    sys.modules["dotenv"] = fake_dotenv
    os.environ["MODEL_ID"] = "test-model"
    os.environ.pop("AGENT_WORKDIR", None)
    try:
        os.chdir(workdir)
        spec = importlib.util.spec_from_file_location("s09_1_harness_under_test", HARNESS)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        os.chdir(previous_cwd)
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
        for key, previous in saved_env.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous


class Block(types.SimpleNamespace):
    def model_dump(self, **kwargs):
        return dict(vars(self))


def response(*blocks, stop_reason="end_turn"):
    return types.SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


def tool_pair(index: int, output: str) -> list[dict]:
    tool_id = f"toolu_{index}"
    return [
        {"role": "assistant", "content": [{"type": "tool_use", "id": tool_id, "name": "bash",
                                           "input": {"command": f"echo {index}"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": output}]},
    ]


def assert_tool_pairs_intact(view: list[dict]) -> None:
    for position, message in enumerate(view):
        if not isinstance(message.get("content"), list):
            continue
        for block in message["content"]:
            if block.get("type") != "tool_result":
                continue
            previous = view[position - 1] if position else {}
            ids = [b.get("id") for b in previous.get("content", []) if isinstance(b, dict)]
            assert block["tool_use_id"] in ids, f"orphan tool_result at view[{position}]"


def new_session(h):
    session = h.Session.create().activate()
    h.load_memories = lambda query: ""
    return session


def test_raw_log_and_state_survive_reload() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        h = load_harness(Path(tmp))
        session = new_session(h)
        replies = iter([
            response(Block(type="tool_use", id="toolu_a", name="todo_write",
                           input={"todos": [{"content": "step", "status": "in_progress"}]}),
                     stop_reason="tool_use"),
            response(Block(type="text", text="done")),
        ])
        h.stream_response = lambda view, system, tools: next(replies)
        session.extract_memory = False
        session.submit("plan something")

        reloaded = h.Session.load(session.id[:15])
        assert reloaded.messages == session.messages
        assert [m["role"] for m in reloaded.messages] == ["user", "assistant", "user", "assistant"]
        assert reloaded.state["todos"] == [{"content": "step", "status": "in_progress"}]
        assert reloaded.state["title"] == "plan something"


def test_compaction_only_touches_the_view() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        h = load_harness(Path(tmp))
        session = new_session(h)
        h.CONTEXT_CHAR_LIMIT = 3000
        h.summarize_history = lambda previous, messages: f"summary of {len(messages)} messages"
        session.append({"role": "user", "content": "start"})
        for index in range(30):
            for message in tool_pair(index, f"output {index} " + "x" * 300):
                session.append(message)
        snapshot = copy.deepcopy(session.messages)

        view = session.build_view("start")

        assert session.messages == snapshot
        assert session.state["boundary"] > 0
        assert "summary of" in view[0]["content"]
        assert_tool_pairs_intact(view)
        # the newest tool result is never folded away before the model sees it
        assert "output 29" in json.dumps(view)


def test_micro_compact_placeholder_points_back_to_raw_history() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        h = load_harness(Path(tmp))
        session = new_session(h)
        session.append({"role": "user", "content": "start"})
        for index in range(5):
            for message in tool_pair(index, f"ORIGINAL-{index} " + "y" * 200):
                session.append(message)

        view = session.build_view("start")
        first_result = view[2]["content"][0]["content"]

        assert "session_history(start=2)" in first_result
        assert "ORIGINAL-0" in h.run_session_history(2)
        assert "ORIGINAL-4" in json.dumps(view)


def test_snip_does_not_write_files_each_turn() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        h = load_harness(Path(tmp))
        session = new_session(h)
        session.append({"role": "user", "content": "start"})
        for index in range(40):
            for message in tool_pair(index, "ok"):
                session.append(message)

        before = sorted(p.name for p in Path(tmp).rglob("*"))
        for _ in range(3):
            view = session.build_view("start")
        after = sorted(p.name for p in Path(tmp).rglob("*"))

        assert len(view) <= h.SNIP_MAX_MESSAGES + 1
        assert_tool_pairs_intact(view)
        assert before == after


def test_watermark_advances_only_after_successful_extraction() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        h = load_harness(Path(tmp))
        session = new_session(h)
        seen = []

        def failing(dialogue, context):
            raise RuntimeError("bedrock down")

        h.extract_memories = failing
        session.append({"role": "user", "content": "I prefer tabs"})
        session.append({"role": "assistant", "content": [{"type": "text", "text": "noted"}]})
        session.end_turn()
        assert session.state["memory_watermark"] == 0

        h.extract_memories = lambda dialogue, context: seen.append((dialogue, context)) or 0
        session.end_turn()
        assert session.state["memory_watermark"] == 2
        assert "I prefer tabs" in seen[-1][0]

        session.append({"role": "user", "content": "second request"})
        session.end_turn()
        dialogue, context = seen[-1]
        assert "second request" in dialogue
        assert "I prefer tabs" not in dialogue
        assert "I prefer tabs" in context


def test_extraction_skips_tool_traffic_and_reminders() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        h = load_harness(Path(tmp))
        lines = h.dialogue_lines([
            {"role": "user", "content": "use uv"},
            *tool_pair(1, "SECRET TOOL OUTPUT"),
            {"role": "user", "content": [{"type": "text", "text": "<reminder>Update your todos.</reminder>"}]},
            {"role": "assistant", "content": [{"type": "thinking", "thinking": "hmm", "signature": "s"},
                                              {"type": "text", "text": "ok"}]},
        ])
        assert lines == ["user: use uv", "assistant: ok"]


def test_interrupted_tool_use_is_closed_on_load() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        h = load_harness(Path(tmp))
        session = new_session(h)
        session.append({"role": "user", "content": "go"})
        session.append(tool_pair(1, "unused")[0])

        reloaded = h.Session.load(session.id)

        assert h.is_tool_result(reloaded.messages[-1])
        assert reloaded.messages[-1]["content"][0]["tool_use_id"] == "toolu_1"

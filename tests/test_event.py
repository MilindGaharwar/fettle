"""Tests for fettle.event — normalized hook event model."""

from fettle.event import FettleEvent, HookType


class TestFettleEventFromDict:
    def test_basic_write_event(self):
        data = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/app/src/main.py", "content": "x = 1"},
            "cwd": "/app",
            "session_id": "sess-1",
        }
        ev = FettleEvent.from_dict(data, HookType.PRE_TOOL_USE)
        assert ev.hook == HookType.PRE_TOOL_USE
        assert ev.tool_name == "Write"
        assert ev.file_path == "/app/src/main.py"
        assert ev.cwd == "/app"
        assert ev.session_id == "sess-1"
        assert ev.changed_files == ["/app/src/main.py"]

    def test_bash_event(self):
        data = {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest tests/"},
            "cwd": "/project",
            "session_id": "s2",
        }
        ev = FettleEvent.from_dict(data, HookType.POST_TOOL_USE)
        assert ev.command == "pytest tests/"
        assert ev.file_path == ""
        assert ev.changed_files == []

    def test_empty_payload(self):
        ev = FettleEvent.from_dict({}, HookType.STOP)
        assert ev.hook == HookType.STOP
        assert ev.tool_name == ""
        assert ev.session_id == "unknown"


class TestFettleEventProperties:
    def test_has_file(self):
        ev = FettleEvent(hook=HookType.PRE_TOOL_USE, file_path="/x.py")
        assert ev.has_file is True

    def test_no_file(self):
        ev = FettleEvent(hook=HookType.PRE_TOOL_USE)
        assert ev.has_file is False

    def test_file_extension(self):
        ev = FettleEvent(hook=HookType.PRE_TOOL_USE, file_path="/app/main.tsx")
        assert ev.file_extension == ".tsx"

    def test_is_python(self):
        ev = FettleEvent(hook=HookType.PRE_TOOL_USE, file_path="module.py")
        assert ev.is_python is True
        assert ev.is_typescript is False

    def test_is_typescript(self):
        ev = FettleEvent(hook=HookType.PRE_TOOL_USE, file_path="app.ts")
        assert ev.is_typescript is True
        assert ev.is_python is False

    def test_is_frontend(self):
        ev = FettleEvent(hook=HookType.PRE_TOOL_USE, file_path="comp.jsx")
        assert ev.is_frontend is True
        assert ev.is_python is False

    def test_pyi_is_python(self):
        ev = FettleEvent(hook=HookType.PRE_TOOL_USE, file_path="stubs.pyi")
        assert ev.is_python is True

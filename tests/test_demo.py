import subprocess
import sys
from pathlib import Path

from fettle import demo


EXPECTED_OUTPUT = """\
[1/4] VIOLATION INTRODUCED
Broad exception handling now hides unexpected failures.
[2/4] VIOLATION DETECTED
FETTLE-DEMO-001: broad Exception handler found.
[3/4] REPAIR APPLIED
The handler now catches ValueError only.
[4/4] REPAIR INDEPENDENTLY VERIFIED
Behavioral tests passed.
"""


def test_demo_completes_with_stable_output(capsys):
    assert demo.run_demo() == 0
    assert capsys.readouterr().out == EXPECTED_OUTPUT


def test_demo_output_is_byte_identical_across_processes(tmp_path):
    command = [sys.executable, "-m", "fettle", "demo"]
    first = subprocess.run(command, cwd=tmp_path, capture_output=True, check=False)
    second = subprocess.run(command, cwd=tmp_path, capture_output=True, check=False)

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout == EXPECTED_OUTPUT.encode()
    assert first.stderr == second.stderr == b""


def test_demo_returns_nonzero_when_independent_verification_fails(monkeypatch, capsys):
    failed = subprocess.CompletedProcess([], 1, stdout="", stderr="")
    monkeypatch.setattr(demo.subprocess, "run", lambda *args, **kwargs: failed)

    assert demo.run_demo() == 1
    assert capsys.readouterr().out.endswith(
        "[4/4] REPAIR NOT VERIFIED\nBehavioral tests failed.\n"
    )


def test_demo_fixture_is_packaged_source():
    fixture = Path(demo.__file__).parent / "_demo_fixture"
    assert sorted(path.name for path in fixture.iterdir()) == [
        "calculator.py.txt", "test_calculator.py.txt",
    ]

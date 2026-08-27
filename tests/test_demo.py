import shutil
import subprocess
import sys
from pathlib import Path

from fettle import demo


EXPECTED_OUTPUT = """\
[1/4] VIOLATION INTRODUCED  demo_project/calculator.py:4

   2 |     try:
   3 |         return int(value)
   4 |     except Exception:
   5 |         return None

   Broad handler hides unexpected failures.

[2/4] VIOLATION DETECTED
   broad-except-no-reraise  demo_project/calculator.py:4
   Rule: rules/llm-antipatterns.yml

[3/4] REPAIR APPLIED

   -     except Exception:
   +     except ValueError:

[4/4] REPAIR INDEPENDENTLY VERIFIED
   Re-ran check: clean
   Re-ran tests: 4 passed

   An unexpected TypeError now surfaces instead of being silently swallowed.
"""


def test_demo_completes_with_stable_output(capsys):
    assert demo.run_demo() == 0
    assert capsys.readouterr().out == EXPECTED_OUTPUT


def test_demo_output_is_byte_identical_across_processes(tmp_path):
    command = [sys.executable, "-m", "fettle", "demo"]
    first = subprocess.run(command, cwd=tmp_path, capture_output=True, check=False, timeout=20)
    second = subprocess.run(command, cwd=tmp_path, capture_output=True, check=False, timeout=20)

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout == EXPECTED_OUTPUT.encode()
    assert first.stderr == second.stderr == b""
    assert len(first.stdout.splitlines()) <= 30
    assert str(tmp_path).encode() not in first.stdout


def test_demo_returns_nonzero_when_fixture_verification_fails(tmp_path, capsys):
    fixture = tmp_path / "fixture"
    shutil.copytree(Path(demo.__file__).parent / "_demo_fixture", fixture)
    tests = fixture / "test_calculator.py.txt"
    tests.write_text(
        tests.read_text(encoding="utf-8").replace(
            'self.assertEqual(parse_count("6"), 6)',
            'self.assertEqual(parse_count("6"), 7)',
        ),
        encoding="utf-8",
    )

    assert demo.run_demo(fixture) == 1
    assert capsys.readouterr().out.endswith(
        "[4/4] REPAIR NOT VERIFIED\n"
        "   Re-ran check: clean\n"
        "   Re-ran tests: failed\n"
    )


def test_demo_fixture_is_packaged_source():
    fixture = Path(demo.__file__).parent / "_demo_fixture"
    assert sorted(path.name for path in fixture.iterdir()) == [
        "calculator.py.txt", "test_calculator.py.txt",
    ]

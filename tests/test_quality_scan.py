"""Tests for quality_scan.py — project scan, baselines, ignores, severity config.

Written after dogfooding on a real project surfaced three gaps: .venv swept
into the file count, .fettle-ignore never applied to findings, and baselines
keyed on absolute paths (useless on CI or another checkout).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(PLUGIN_DIR, "scripts", "quality_scan.py")

RUFF_AVAILABLE = shutil.which("ruff") or os.path.isfile(os.path.expanduser("~/.local/bin/ruff"))

VIOLATION = (
    "def f():\n"
    "    try:\n"
    "        return 1\n"
    "    except Exception:\n"
    "        pass\n"
)

CLEAN = "def f():\n    return 1\n"


def run_scan(root: str, *extra_args: str):
    """Run quality_scan.py and return (parsed json | None, rc, stderr)."""
    proc = subprocess.run(
        [sys.executable, SCRIPT, "--root", root, "--json", *extra_args],
        capture_output=True, text=True, timeout=120,
    )
    parsed = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else None
    return parsed, proc.returncode, proc.stderr


def make_project(files: dict[str, str]) -> str:
    tmpdir = tempfile.mkdtemp()
    for rel, content in files.items():
        path = os.path.join(tmpdir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(content)
    return tmpdir


@pytest.mark.skipif(not RUFF_AVAILABLE, reason="ruff not available")
class TestQualityScan:
    def test_clean_project_exits_0(self):
        root = make_project({"app.py": CLEAN})
        try:
            parsed, rc, _ = run_scan(root)
            assert rc == 0
            assert parsed["summary"]["errors"] == 0
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_error_finding_exits_1(self):
        root = make_project({"app.py": VIOLATION})
        try:
            parsed, rc, _ = run_scan(root)
            assert rc == 1
            assert parsed["summary"]["errors"] >= 1
            assert any(f["rule"] in ("BLE001", "S110") for f in parsed["findings"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_findings_use_relative_paths(self):
        root = make_project({"pkg/app.py": VIOLATION})
        try:
            parsed, _, _ = run_scan(root)
            assert parsed["findings"], "expected findings"
            for f in parsed["findings"]:
                assert not os.path.isabs(f["file"])
                assert f["file"] == os.path.join("pkg", "app.py")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_venv_and_hidden_dirs_excluded_from_file_count(self):
        root = make_project({
            "app.py": CLEAN,
            ".venv/lib/site.py": VIOLATION,
            "node_modules/dep/mod.py": VIOLATION,
            ".git/hook.py": VIOLATION,
        })
        try:
            parsed, _, _ = run_scan(root)
            assert parsed["file_count"] == 1
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_fettle_ignore_filters_findings(self):
        root = make_project({
            "app.py": CLEAN,
            "legacy/old.py": VIOLATION,
            ".fettle-ignore": "legacy/*\n",
        })
        try:
            parsed, rc, _ = run_scan(root)
            assert rc == 0
            assert not any("legacy" in f["file"] for f in parsed["findings"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_baseline_roundtrip_suppresses_known_findings(self):
        root = make_project({"app.py": VIOLATION})
        try:
            baseline = os.path.join(root, "baseline.json")
            _, _, stderr = run_scan(root, "--baseline", baseline, "--update-baseline")
            assert "Baseline saved" in stderr
            parsed, rc, _ = run_scan(root, "--baseline", baseline)
            assert rc == 0
            assert parsed["findings"] == []
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_baseline_reports_only_new_findings(self):
        root = make_project({"app.py": VIOLATION})
        try:
            baseline = os.path.join(root, "baseline.json")
            run_scan(root, "--baseline", baseline, "--update-baseline")
            with open(os.path.join(root, "new.py"), "w") as fh:
                fh.write(VIOLATION)
            parsed, rc, _ = run_scan(root, "--baseline", baseline)
            assert rc == 1
            assert parsed["findings"]
            assert all(f["file"] == "new.py" for f in parsed["findings"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_baseline_portable_across_checkout_locations(self):
        """A baseline committed from one machine must match on another."""
        root_a = make_project({"app.py": VIOLATION})
        root_b = None
        try:
            baseline = os.path.join(root_a, "baseline.json")
            run_scan(root_a, "--baseline", baseline, "--update-baseline")

            root_b = tempfile.mkdtemp()
            shutil.copy(os.path.join(root_a, "app.py"), root_b)
            moved_baseline = os.path.join(root_b, "baseline.json")
            shutil.copy(baseline, moved_baseline)

            parsed, rc, _ = run_scan(root_b, "--baseline", moved_baseline)
            assert rc == 0
            assert parsed["findings"] == []
        finally:
            shutil.rmtree(root_a, ignore_errors=True)
            if root_b:
                shutil.rmtree(root_b, ignore_errors=True)

    def test_legacy_absolute_path_baseline_still_matches(self):
        """Pre-v0.2.1 baselines stored absolute paths; they must keep working."""
        root = make_project({"app.py": VIOLATION})
        try:
            parsed, _, _ = run_scan(root)
            legacy = []
            for f in parsed["findings"]:
                f = dict(f)
                f["file"] = os.path.join(root, f["file"])
                legacy.append(f)
            baseline = os.path.join(root, "baseline.json")
            with open(baseline, "w") as fh:
                json.dump(legacy, fh)

            parsed, rc, _ = run_scan(root, "--baseline", baseline)
            assert rc == 0
            assert parsed["findings"] == []
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_severity_config_is_honored(self):
        """[severity] in .fettle.toml is the single source for the scan too."""
        root = make_project({
            "app.py": VIOLATION,
            ".fettle.toml": "[severity]\nerror_rules = []\nwarning_prefixes = []\n",
        })
        try:
            parsed, rc, _ = run_scan(root)
            assert rc == 0
            assert parsed["summary"]["errors"] == 0
        finally:
            shutil.rmtree(root, ignore_errors=True)

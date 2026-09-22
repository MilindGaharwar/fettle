"""Probe sandboxed Chromium with a verified, narrowly extended seccomp profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

PROFILE_SHA256 = "cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849"
BROWSER_IMAGE = "sha256:f0d4499f7a1b579541905b3598db403bc8eb9390dbf24b594df19267a1c6b981"
PROBE = """
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as runtime:
    browser=runtime.chromium.launch(headless=True,chromium_sandbox=True)
    page=browser.new_page()
    page.goto('data:text/html,<title>boundary</title><h1>Sandbox active</h1>')
    print(json.dumps({'title':page.title(),'heading':page.get_by_role('heading').inner_text()}))
    browser.close()
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seccomp-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    content = arguments.seccomp_source.read_bytes()
    if hashlib.sha256(content).hexdigest() != PROFILE_SHA256:
        raise ValueError("upstream Playwright v1.63.0 seccomp profile identity mismatch")
    profile = json.loads(content)
    profile["syscalls"].append({"names": ["chroot"], "action": "SCMP_ACT_ALLOW"})
    with tempfile.TemporaryDirectory(prefix="fettle-browser-boundary-") as temporary:
        profile_path = Path(temporary) / "seccomp.json"
        profile_path.write_text(json.dumps(profile, sort_keys=True))
        command = ["/opt/homebrew/bin/docker", "--context", "colima-fettle-uat", "run",
                   "--rm", "--name", "fettle-browser-boundary-probe", "--network", "none",
                   "--read-only", "--user", "65534:65534", "--cap-drop", "ALL",
                   "--security-opt", "no-new-privileges:true",
                   "--security-opt", "seccomp=" + str(profile_path), "--pids-limit", "128",
                   "--memory", "1g", "--memory-swap", "1g", "--cpus", "1",
                   "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=128m,mode=1777",
                   BROWSER_IMAGE, "-c", PROBE]
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=40)
            observation = {"exit_code": result.returncode, "stdout": result.stdout[:8192],
                           "stderr": result.stderr[:16384]}
        except subprocess.TimeoutExpired:
            observation = {"exit_code": -1, "stdout": "", "stderr": "browser probe timed out"}
            subprocess.run(command[:3] + ["rm", "--force", "fettle-browser-boundary-probe"],
                           text=True, capture_output=True, timeout=20, check=True)
        evidence = {"recorded_at": datetime.now(UTC).isoformat(), "image": BROWSER_IMAGE,
                    "upstream_seccomp_sha256": PROFILE_SHA256,
                    "effective_seccomp_sha256": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
                    "added_syscalls": ["chroot"], "chromium_sandbox": True,
                    "observation": observation,
                    "passed": observation["exit_code"] == 0
                    and observation["stdout"].strip() == '{"title": "boundary", "heading": "Sandbox active"}',
                    "limits": ["offline browser startup only", "not product acceptance"]}
    arguments.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2))
    raise SystemExit(0 if evidence["passed"] else 1)


if __name__ == "__main__":
    main()
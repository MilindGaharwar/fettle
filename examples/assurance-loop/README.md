# Two-Minute Assurance Loop

This disposable example demonstrates one deterministic detect, explain, repair,
and verify loop. The `all` extra includes Ruff.

```bash
pipx install finefettle
git clone https://github.com/MilindGaharwar/fettle.git
cd fettle/examples/assurance-loop
cp broken.py app.py
fettle check --all --json
cp fixed.py app.py
fettle check --all --json
```

The first check reports Ruff `F401` because `os` is imported but unused. The
second check reports no issues. This fixture uses `fettle check --all` because
an uncommitted disposable file is not part of Git's changed-file set.

The violating result includes this stable finding shape (other repository
findings are omitted from this bounded excerpt):

```json
{
  "findings": [
    {
      "file": "examples/assurance-loop/app.py",
      "line": 1,
      "code": "F401",
      "message": "`os` imported but unused",
      "severity": "info",
      "tool": "ruff"
    }
  ]
}
```

After copying `fixed.py`, the bounded excerpt for that same file has no finding:

```json
{
  "findings": []
}
```

The complete output also includes `file_count`; it is intentionally omitted
because it varies as the repository grows.

`fettle explain` reports recent in-session gate decisions when Fettle is wired
to an agent host. The standalone scanner already includes file, line, rule, and
message in its finding, so this CLI-only proof does not manufacture a trace that
does not exist.

Reset at any time:

```bash
cp broken.py app.py
```

Reference version: Fettle v1.11.1. The automated example contract
guards command and expected-state drift on later versions.

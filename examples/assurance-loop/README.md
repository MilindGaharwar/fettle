# Two-Minute Assurance Loop

This disposable example demonstrates one deterministic detect, explain, repair,
and verify loop. It requires Fettle and Ruff; Fettle does not install analyzers
implicitly.

```bash
pipx install finefettle
pipx inject finefettle ruff
git clone [https://github.com/MilindGaharwar/fettle.git](https://github.com/MilindGaharwar/fettle.git)
cd fettle/examples/assurance-loop
cp broken.py app.py
fettle check --all
cp fixed.py app.py
fettle check --all
```

The first check reports Ruff `F401` because `os` is imported but unused. The
second check reports no issues. This fixture uses `fettle check --all` because
an uncommitted disposable file is not part of Git's changed-file set.

## Programmatic JSON Output
Inspect repository quality findings programmatically in standard JSON:

Bash

```
fettle check --all --json
```

### Violations State Example
When checking `app.py` based on `broken.py`, finding records populate with stable schema fields (`file`, `line`, `code`, `message`, `severity`, `tool`):

JSON

```json
{
  "findings": [
    {
      "file": "app.py",
      "line": 1,
      "code": "F401",
      "message": "`os` imported but unused",
      "severity": "info",
      "tool": "ruff"
    }
  ],
  "file_count": 1
}
```

### Clean State Example
When `app.py` is fixed, the JSON output returns a clean findings list:

JSON

```json
{
  "findings": [],
  "file_count": 1
}
```

`fettle explain` reports recent in-session gate decisions when Fettle is wired
to an agent host. The standalone scanner already includes file, line, rule, and
message in its finding, so this CLI-only proof does not manufacture a trace that
does not exist.

Reset at any time:

Bash

```
cp broken.py app.py
```

Reference version: Fettle v1.11.0. The automated example contract
guards command and expected-state drift on later versions.

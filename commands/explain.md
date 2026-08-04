# /fettle:explain

Explain why Fettle blocked or warned about the last edit.

## Usage

When the user invokes `/fettle:explain`:

```bash
fettle explain
```

Shows for each decision:
- Which hook ran (PreToolUse, PostToolUse, Stop)
- Which file was checked
- Which tool found the issue (ruff, semgrep, or infrastructure error)
- The specific violation(s)
- How to fix or suppress

Helps users understand: "Was this a code quality issue or a Fettle bug?"

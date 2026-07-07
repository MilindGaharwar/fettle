# /fettle:review

Run an independent cross-review of a file using a different LLM.

## Usage

When the user invokes `/fettle:review`:

1. Identify the file to review (ask if not obvious from context).
2. Run:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh review.py --file PATH
   ```
3. Present the review findings.

## Configuration

```toml
# .fettle.toml
[review]
provider = "ollama"    # ollama | nexus | openai
endpoint = "http://localhost:11434/v1"
model = "sam860/LFM2:8b"
```

## Purpose

Gets a "second opinion" from a different model. Useful for:
- Critical code paths
- Security-sensitive changes
- Before merging complex PRs

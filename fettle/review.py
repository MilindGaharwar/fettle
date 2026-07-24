#!/usr/bin/env python3
"""Fettle cross-review — provider-agnostic independent code review.

Sends code to an LLM (via Ollama, a local proxy, or any OpenAI-compatible endpoint)
for independent review from a different perspective than the authoring model.

Usage:
    python3 review.py --file path/to/file.py [--diff]
    python3 review.py --stdin  # reads diff from stdin

Configuration in .fettle.toml:
    [review]
    provider = "ollama"           # ollama | proxy | openai
    endpoint = "http://localhost:11434/v1"
    model = "llama3.2"
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
from fettle.config import load_config
from fettle.paths import find_repo_root

REVIEW_SYSTEM_PROMPT = """You are an independent code reviewer. Review the following code for:
1. Bugs and correctness issues
2. Security vulnerabilities
3. Performance problems
4. Error handling gaps
5. Edge cases not covered

Be specific: name the line, the issue, and the fix. Be concise — no filler.
If the code is fine, say "No issues found." Do not invent problems."""


def _call_review_llm(code: str, cfg: dict) -> str | None:
    """Send code to review LLM and get response."""
    review_cfg = cfg.get("review", {})
    provider = review_cfg.get("provider", "ollama")
    endpoint = review_cfg.get("endpoint", "http://localhost:11434/v1")
    model = review_cfg.get("model", "llama3.2")

    if provider == "proxy":
        endpoint = review_cfg.get("endpoint", endpoint)
        model = review_cfg.get("model", "claude-opus-4.6")

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": f"Review this code:\n\n```\n{code[:8000]}\n```"},
        ],
        "temperature": 0.2,
        "max_tokens": 2000,
    }).encode()

    try:
        req = urllib.request.Request(
            f"{endpoint}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        api_key = os.environ.get("REVIEW_API_KEY", "")
        if api_key and provider == "proxy":
            req.add_header("Authorization", f"Bearer {api_key}")

        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError) as e:
        print(f"  Review LLM error: {e}", file=sys.stderr)
        return None


def review_file(file_path: str, cfg: dict) -> dict:
    """Review a single file."""
    path = Path(file_path)
    if not path.exists():
        return {"file": file_path, "status": "error", "message": "File not found"}

    code = path.read_text(encoding="utf-8", errors="replace")
    if len(code.strip()) < 20:
        return {"file": file_path, "status": "skipped", "message": "File too short"}

    review = _call_review_llm(code, cfg)
    if review is None:
        return {"file": file_path, "status": "error", "message": "LLM unavailable"}

    return {
        "file": file_path,
        "status": "reviewed",
        "findings": review,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fettle cross-review")
    parser.add_argument("--file", help="File to review")
    parser.add_argument("--diff", action="store_true", help="Review as a diff (context-aware)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    repo_root = find_repo_root()
    cfg = load_config(str(repo_root) if repo_root else None)

    if not args.file:
        print("Usage: fettle review --file path/to/file.py")
        sys.exit(1)

    result = review_file(args.file, cfg)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"── Fettle Cross-Review: {result['file']} ──\n")
        if result["status"] == "reviewed":
            print(result["findings"])
        else:
            print(f"  {result['status']}: {result.get('message', '')}")


if __name__ == "__main__":
    main()

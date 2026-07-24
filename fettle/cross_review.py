#!/usr/bin/env python3
"""Fettle cross-review utility.

Sends code files to an OpenAI-compatible chat-completions endpoint for an
independent quality review. Endpoint/model come from environment variables;
provider-agnostic rework (claude -p default) is planned for v0.4.0 (WP-11).

Usage:
    python3 cross_review.py --files file1.py file2.py [--model MODEL] [--prompt PROMPT]
"""

import argparse
import os
import json
import sys
import urllib.error
import urllib.request

REVIEW_ENDPOINT = os.environ.get("FETTLE_REVIEW_ENDPOINT", "")
DEFAULT_MODEL = os.environ.get("FETTLE_REVIEW_MODEL", "")
FALLBACK_MODEL = DEFAULT_MODEL
DEFAULT_PROMPT = (
    "Review this code for quality issues, security vulnerabilities, and "
    "potential bugs. Be specific about line numbers and suggest fixes."
)
TIMEOUT = 120


def _read_files(paths: list[str]) -> str:
    parts: list[str] = []
    for path in paths:
        try:
            with open(path) as fh:
                content = fh.read()
            parts.append(f"--- {path} ---\n{content}")
        except OSError as exc:
            print(f"WARNING: cannot read {path}: {exc}", file=sys.stderr)
    return "\n\n".join(parts)


def _call_llm(model: str, prompt: str, code: str) -> str | None:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "user", "content": f"{prompt}\n\n{code}"}
        ],
        "temperature": 0.3,
        "max_tokens": 4000,
    }).encode()

    req = urllib.request.Request(
        REVIEW_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except urllib.error.URLError as exc:
        print(f"ERROR: {model} request failed: {exc}", file=sys.stderr)
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        print(f"ERROR: unexpected response from {model}: {exc}", file=sys.stderr)
        return None
    except TimeoutError:
        print(f"ERROR: {model} request timed out after {TIMEOUT}s", file=sys.stderr)
        return None


def main() -> int:
    if not REVIEW_ENDPOINT:
        print(
            "cross_review: set FETTLE_REVIEW_ENDPOINT (and FETTLE_REVIEW_MODEL) "
            "to enable cross-review. Provider-agnostic rework lands in v0.4.0.",
            file=sys.stderr,
        )
        return 1
    parser = argparse.ArgumentParser(description="Fettle cross-review via an OpenAI-compatible endpoint")
    parser.add_argument("--files", nargs="+", required=True, help="Files to review")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"LLM model (default: {DEFAULT_MODEL})")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Review prompt")
    args = parser.parse_args()

    code = _read_files(args.files)
    if not code.strip():
        print("ERROR: no readable file content", file=sys.stderr)
        return 1

    result = _call_llm(args.model, args.prompt, code)
    if result is None and args.model != FALLBACK_MODEL:
        print(f"Retrying with fallback model: {FALLBACK_MODEL}", file=sys.stderr)
        result = _call_llm(FALLBACK_MODEL, args.prompt, code)

    if result is None:
        print("ERROR: all models failed", file=sys.stderr)
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())

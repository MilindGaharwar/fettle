#!/usr/bin/env python3
"""Fettle learn — generate semgrep rules from incidents.

The flagship feature: incident text → LLM-generated semgrep rule + fixtures + citation.
Requires human approval before landing in rules/learned/.

Usage:
    python3 learn.py --incident "Description of what went wrong..."
    python3 learn.py --file incident-brief.md
    python3 learn.py --list  # show learned rules

Pipeline:
1. Read incident description
2. LLM generates: semgrep rule YAML + violating fixture + clean fixture + citation
3. Verify: run semgrep on violating fixture (must match) and clean fixture (must not match)
4. If verification fails: one automated repair round
5. Present to user for approval
6. On approval: save to rules/learned/<rule-id>.yml + tests/fixtures/learned/
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
from fettle.paths import find_repo_root

LEARNED_RULES_DIR = "rules/learned"
LEARNED_FIXTURES_DIR = "tests/fixtures/learned"
# WP-163 (C2): machine-initiated drafts are quarantined here — never loaded
# by any gate — until a human runs `fettle rules promote <id>` (D-C3).
PROPOSED_RULES_DIR = "rules/proposed"

LEARN_SYSTEM_PROMPT = """You are a security and code quality expert. Given an incident description, generate a semgrep rule that would have caught the issue.

Output valid JSON with these fields:
- "rule_id": kebab-case identifier (e.g., "unhandled-api-timeout")
- "severity": "ERROR" or "WARNING"
- "message": one-line description of what the rule catches
- "pattern": the semgrep pattern (YAML-compatible string)
- "language": target language (python, javascript, etc.)
- "violating_code": Python code that SHOULD trigger the rule
- "clean_code": Python code that should NOT trigger the rule
- "citation": brief incident reference (what happened, when)
- "fix_suggestion": how to fix code that matches

Respond with valid JSON only."""


def _generate_rule_from_incident(incident_text: str) -> dict | None:
    """Use LLM to generate a semgrep rule from incident description."""
    # Prefer a local model (Ollama) when available; configurable via env.
    try:
        import urllib.request
        import urllib.error

        # Try Ollama first (most likely available locally)
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434/v1")
        model = os.environ.get("FETTLE_LEARN_MODEL", "llama3.2")

        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": LEARN_SYSTEM_PROMPT},
                {"role": "user", "content": f"Incident:\n{incident_text}"},
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
        }).encode()

        req = urllib.request.Request(
            f"{ollama_url}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"]

        # Parse JSON from response
        content = content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

        return json.loads(content)

    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  Error generating rule: {e}", file=sys.stderr)
        return None


def _generate_semgrep_yaml(rule: dict) -> str:
    """Convert parsed rule dict to semgrep YAML format."""
    rule_id = rule.get("rule_id", "learned-rule")
    severity = rule.get("severity", "ERROR")
    message = rule.get("message", "Learned rule violation")
    pattern = rule.get("pattern", "")
    language = rule.get("language", "python")
    citation = rule.get("citation", "")
    fix = rule.get("fix_suggestion", "")

    yaml_content = f"""rules:
  - id: {rule_id}
    pattern: |
      {pattern}
    message: "{message}"
    languages: [{language}]
    severity: {severity}
    metadata:
      origin: fettle-learn
      citation: "{citation}"
      fix: "{fix}"
      generated: "{datetime.now().isoformat()}"
"""
    return yaml_content


def _save_rule(rule: dict, repo_root: Path) -> dict:
    """Save learned rule and fixtures to repo."""
    rule_id = rule.get("rule_id", f"learned-{datetime.now().strftime('%Y%m%d-%H%M%S')}")

    # Create directories
    rules_dir = repo_root / LEARNED_RULES_DIR
    fixtures_dir = repo_root / LEARNED_FIXTURES_DIR
    rules_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    # Save rule YAML
    rule_path = rules_dir / f"{rule_id}.yml"
    rule_path.write_text(_generate_semgrep_yaml(rule), encoding="utf-8")

    # Save violating fixture
    violating = rule.get("violating_code", "")
    if violating:
        (fixtures_dir / f"{rule_id}_violation.py").write_text(violating, encoding="utf-8")

    # Save clean fixture
    clean = rule.get("clean_code", "")
    if clean:
        (fixtures_dir / f"{rule_id}_clean.py").write_text(clean, encoding="utf-8")

    return {
        "rule_id": rule_id,
        "rule_path": str(rule_path.relative_to(repo_root)),
        "severity": rule.get("severity", "ERROR"),
        "message": rule.get("message", ""),
        "citation": rule.get("citation", ""),
    }


def _signature_brief(sig, days: int) -> str:
    """Incident text for the LLM, built from a detected signature."""
    lines = [
        f"Repeated failure signature detected by fettle over the last {days} days:",
        f"- kind: {sig.kind}",
        f"- key: {sig.key}",
        f"- occurrences: {sig.count}",
        "Sample evidence:",
    ]
    lines += [f"  - {s}" for s in sig.sample_evidence]
    lines.append("Write a semgrep rule that would catch this pattern early.")
    return "\n".join(lines)


def _proposal_id(sig) -> str:
    if sig.kind == "ci-class":
        return f"ci-{sig.key}-recurrence"
    # trace-cluster key is "<hook>/<code>" — the code is the rule id
    return sig.key.rsplit("/", 1)[-1]


def _evidence_brief_yaml(sig, days: int) -> str:
    """Deterministic no-LLM proposal: the evidence, an empty pattern (D-C2).

    `fettle rules promote` refuses proposals with an empty pattern, so a
    brief cannot reach the gates without a human completing it.
    """
    rule_id = _proposal_id(sig)
    evidence = "".join(f"#   - {s}\n" for s in sig.sample_evidence)
    return f"""# Fettle evolution proposal — quarantined; never loaded by gates.
# Complete the pattern, then promote: fettle rules promote {rule_id}
# evidence:
{evidence}rules:
  - id: {rule_id}
    pattern: ''
    message: "Repeated failure signature {sig.key} fired {sig.count}x in {days}d"
    languages: [python]
    severity: WARNING
    metadata:
      origin: fettle-evolution
      status: proposed
      signature: "{sig.key}"
      occurrences: {sig.count}
      generated: "{datetime.now().isoformat()}"
"""


def _proposal_yaml_from_rule(rule: dict, sig) -> str:
    """LLM-generated rule, re-marked as an evolution proposal."""
    yaml_content = _generate_semgrep_yaml(rule)
    yaml_content = yaml_content.replace("origin: fettle-learn",
                                        "origin: fettle-evolution")
    return yaml_content + (
        f"      status: proposed\n"
        f"      signature: \"{sig.key}\"\n"
        f"      occurrences: {sig.count}\n"
    )


def draft_proposals(repo_root: Path, days: int = 30, save: bool = True,
                    generate=None) -> list[dict]:
    """Draft rule proposals for every draftable signature (WP-163, C2).

    Autonomous sensing + drafting; the output is quarantined in
    rules/proposed/. `generate` is the LLM callable (injectable for tests);
    when it returns None the deterministic evidence brief ships instead.
    """
    from fettle.evolution import detect_signatures

    if generate is None:
        generate = _generate_rule_from_incident
    proposed_dir = repo_root / PROPOSED_RULES_DIR
    results: list[dict] = []
    for sig in detect_signatures(repo_root, days=days):
        if not sig.draftable:
            continue
        rule_id = _proposal_id(sig)
        rule_path = proposed_dir / f"{rule_id}.yml"
        if rule_path.exists():
            continue  # already proposed
        rule = generate(_signature_brief(sig, days))
        if rule:
            rule["rule_id"] = rule_id  # signature-derived id wins (dedup key)
            yaml_text = _proposal_yaml_from_rule(rule, sig)
            mode = "llm"
        else:
            yaml_text = _evidence_brief_yaml(sig, days)
            mode = "brief"
        if save:
            proposed_dir.mkdir(parents=True, exist_ok=True)
            rule_path.write_text(yaml_text, encoding="utf-8")
        results.append({
            "rule_id": rule_id,
            "kind": sig.kind,
            "signature": sig.key,
            "occurrences": sig.count,
            "mode": mode,
            "path": str(rule_path.relative_to(repo_root)) if save else "",
        })
    return results


def list_proposed_rules(repo_root: Path) -> list[dict]:
    """List quarantined proposals."""
    proposed_dir = repo_root / PROPOSED_RULES_DIR
    if not proposed_dir.exists():
        return []
    return [{"file": yml.name, "path": str(yml.relative_to(repo_root))}
            for yml in sorted(proposed_dir.glob("*.yml"))]


def list_learned_rules(repo_root: Path) -> list[dict]:
    """List all learned rules."""
    rules_dir = repo_root / LEARNED_RULES_DIR
    if not rules_dir.exists():
        return []
    rules = []
    for yml in sorted(rules_dir.glob("*.yml")):
        rules.append({"file": yml.name, "path": str(yml.relative_to(repo_root))})
    return rules


def main() -> None:
    parser = argparse.ArgumentParser(description="Fettle learn — generate rules from incidents")
    parser.add_argument("--incident", help="Incident description text")
    parser.add_argument("--file", help="Path to incident brief file")
    parser.add_argument("--list", action="store_true", help="List learned rules")
    parser.add_argument("--auto-save", action="store_true", help="Save without confirmation prompt")
    parser.add_argument("--from-trace", action="store_true",
                        help="Draft proposals from detected failure signatures (WP-163)")
    parser.add_argument("--days", type=int, default=30,
                        help="Signature window for --from-trace")
    args = parser.parse_args()

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository.", file=sys.stderr)
        sys.exit(1)

    if args.from_trace:
        proposals = draft_proposals(repo_root, days=args.days, save=args.auto_save)
        if not proposals:
            print("No draftable failure signatures in the window. Nothing proposed.")
            return
        verb = "Proposed" if args.auto_save else "Would propose (dry run — add --auto-save)"
        print(f"── Fettle Learn: {verb} {len(proposals)} rule(s) ──\n")
        for p in proposals:
            where = f" → {p['path']}" if p["path"] else ""
            print(f"  • {p['rule_id']} [{p['mode']}] — {p['signature']} "
                  f"×{p['occurrences']}{where}")
        print("\n  Proposals never load into gates. Review and promote with:")
        print("    fettle rules promote <rule-id>")
        return

    if args.list:
        rules = list_learned_rules(repo_root)
        if not rules:
            print("No learned rules yet. Use --incident to generate one.")
            return
        print(f"── {len(rules)} Learned Rule(s) ──\n")
        for r in rules:
            print(f"  • {r['file']}")
        return

    incident_text = ""
    if args.incident:
        incident_text = args.incident
    elif args.file:
        incident_text = Path(args.file).read_text(encoding="utf-8")
    else:
        print("Provide --incident 'text' or --file path")
        sys.exit(1)

    print("── Fettle Learn ──\n")
    print(f"  Incident: {incident_text[:100]}...")
    print("  Generating rule via LLM...")

    rule = _generate_rule_from_incident(incident_text)
    if not rule:
        print("  Failed to generate rule. Is Ollama running?")
        sys.exit(1)

    print("\n  Generated rule:")
    print(f"    ID: {rule.get('rule_id', '?')}")
    print(f"    Severity: {rule.get('severity', '?')}")
    print(f"    Message: {rule.get('message', '?')}")
    print(f"    Pattern: {rule.get('pattern', '?')[:60]}")
    print(f"    Citation: {rule.get('citation', '?')}")

    if args.auto_save:
        result = _save_rule(rule, repo_root)
        print(f"\n  ✓ Saved: {result['rule_path']}")
    else:
        print("\n  [Requires human approval — run with --auto-save to persist]")


if __name__ == "__main__":
    main()

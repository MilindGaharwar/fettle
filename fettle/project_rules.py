"""Project-local semgrep rule extension.

Projects extend Fettle's built-in rules via `.fettle.toml`:

    [rules]
    extra_dirs = [".fettle/rules"]   # dirs with project semgrep rule files
    promise_apis = ["jQuery.ajax"]   # extra APIs for unawaited-promise

`extra_rule_configs()` returns extra `--config` paths for the post-edit
hooks — this is how a Go/TS/Python service ships its own incident-derived
rules (e.g. DVA3's outbox-event-in-transaction) without forking Fettle.
"""

import hashlib
import os
import re
from typing import Any

_RULE_EXTENSIONS = (".yml", ".yaml")

# Dotted identifier chain, e.g. "fetch" or "jQuery.ajax" — anything else
# is rejected so config values cannot inject YAML/pattern syntax.
_API_NAME = re.compile(r"^[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)*$")

_PROMISE_RULE_TEMPLATE = """\
rules:
  - id: unawaited-promise-project
    patterns:
      - pattern-either:
{patterns}
      - pattern-not-inside: await $X
      - pattern-not-inside: return $X
      - pattern-not-inside: const $X = $Y
      - pattern-not-inside: let $X = $Y
      - pattern-not-inside: var $X = $Y
      - pattern-not-inside: $X.then(...)
      - pattern-not-inside: $X.catch(...)
    message: "Unawaited promise from project-configured API. Add await or handle the promise."
    languages: [typescript, javascript]
    severity: WARNING
    metadata:
      origin: project-config
      citation: "promise_apis in .fettle.toml"
"""


def _rules_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    rules = cfg.get("rules")
    return rules if isinstance(rules, dict) else {}


def extra_rule_configs(cfg: dict[str, Any], project_root: str) -> list[str]:
    """Return project-local semgrep config paths (may be empty)."""
    rcfg = _rules_cfg(cfg)
    configs: list[str] = []
    for rel_dir in rcfg.get("extra_dirs", [".fettle/rules"]):
        full_dir = os.path.join(project_root, rel_dir)
        if not os.path.isdir(full_dir):
            continue
        for name in sorted(os.listdir(full_dir)):
            if name.endswith(_RULE_EXTENSIONS):
                configs.append(os.path.join(full_dir, name))
    if _valid_promise_apis(rcfg):
        configs.append(generate_promise_rule(cfg, project_root))
    return configs


def _valid_promise_apis(rcfg: dict[str, Any]) -> list[str]:
    apis = rcfg.get("promise_apis", [])
    return [a for a in apis if isinstance(a, str) and _API_NAME.match(a)]


def generate_promise_rule(cfg: dict[str, Any], project_root: str) -> str:
    """Write (once) and return a generated unawaited-promise rule file."""
    apis = _valid_promise_apis(_rules_cfg(cfg))
    patterns = "\n".join(f"          - pattern: {api}(...)" for api in apis)
    content = _PROMISE_RULE_TEMPLATE.format(patterns=patterns)
    digest = hashlib.sha256(content.encode()).hexdigest()[:12]
    gen_dir = os.path.join(project_root, ".fettle", "generated")
    os.makedirs(gen_dir, exist_ok=True)
    path = os.path.join(gen_dir, f"promise-apis-{digest}.yml")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(content)
    return path

import json
import re
from pathlib import Path

from fettle.quality_scan import execute_ruff
from fettle.result import ResultStatus


EXAMPLE = Path(__file__).parents[1] / "examples" / "assurance-loop"


def test_assurance_loop_detects_and_repairs_known_finding():
    violating = execute_ruff(str(EXAMPLE / "broken.py"))
    clean = execute_ruff(str(EXAMPLE / "fixed.py"))

    assert violating.status is ResultStatus.VIOLATION
    assert [(finding["rule"], finding["line"]) for finding in violating.findings] == [("F401", 1)]
    assert clean.status is ResultStatus.PASS
    assert clean.findings == []


def test_assurance_loop_documents_valid_bounded_json_contract():
    readme = (EXAMPLE / "README.md").read_text()
    examples = re.findall(r"```json\n(.*?)\n```", readme, re.DOTALL)

    assert "fettle check --all --json" in readme
    assert len(examples) == 2
    violating, clean = (json.loads(example) for example in examples)
    assert violating == {
        "findings": [{
            "file": "examples/assurance-loop/app.py",
            "line": 1,
            "code": "F401",
            "message": "`os` imported but unused",
            "severity": "info",
            "tool": "ruff",
        }],
    }
    assert clean == {"findings": []}

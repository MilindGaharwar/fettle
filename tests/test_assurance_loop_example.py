import json
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

def test_assurance_loop_example_documentation_contract():
    readme_path = EXAMPLE / "README.md"
    assert readme_path.exists(), "examples/assurance-loop/README.md must exist"

    content = readme_path.read_text(encoding="utf-8")
    assert "fettle check --all --json" in content
    assert '"findings": []' in content
    assert '"code": "F401"' in content

    json_blocks = []
    lines = content.splitlines()
    in_block = False
    current_block = []

    for line in lines:
        if line.strip() == "```json":
            in_block = True
            current_block = []
            continue
        if line.strip() == "```" and in_block:
            in_block = False
            json_blocks.append("\n".join(current_block))
            continue
        if in_block:
            current_block.append(line)

    assert len(json_blocks) >= 2, "Expected at least clean and violating JSON examples"
    for block in json_blocks:
        parsed = json.loads(block)
        assert "findings" in parsed
        assert "file_count" in parsed

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

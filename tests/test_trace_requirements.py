"""WP-X5 — Requirements Traceability tests."""

from fettle.trace_requirements import trace_requirements, _spec_to_key, _test_to_key, format_report


def test_spec_to_key():
    assert _spec_to_key("docs/auth-spec.md") == "auth"
    assert _spec_to_key("docs/user-ux-spec.md") == "user"
    assert _spec_to_key("docs/payment-requirements.md") == "payment"


def test_test_to_key():
    assert _test_to_key("tests/test_auth.py") == "auth"
    assert _test_to_key("tests/test_payment_flow.py") == "paymentflow"


def test_no_specs_found(tmp_path):
    (tmp_path / "src").mkdir()
    report = trace_requirements(str(tmp_path), {"spec_patterns": ["docs/**/*spec*.md"], "test_roots": ["tests/"]})
    assert report["status"] == "no_specs"


def test_no_tests_found(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "auth-spec.md").write_text("# Auth Spec\n")
    report = trace_requirements(str(tmp_path), {"spec_patterns": ["docs/**/*spec*.md"], "test_roots": ["tests/"]})
    assert report["status"] == "no_tests"
    assert "docs/auth-spec.md" in report["uncovered"]


def test_naming_convention_matches(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "auth-spec.md").write_text("# Auth Spec\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_auth.py").write_text("def test_login(): pass\n")

    report = trace_requirements(str(tmp_path), {
        "spec_patterns": ["docs/*spec*.md"],
        "test_roots": ["tests/"],
        "naming_convention": True,
    })
    assert report["status"] == "completed"
    assert report["specs_covered"] == 1
    assert report["coverage_percent"] == 100.0


def test_explicit_marker_matches(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "payment-spec.md").write_text("# Payment\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_checkout.py").write_text("# traces: docs/payment-spec.md\ndef test_pay(): pass\n")

    report = trace_requirements(str(tmp_path), {
        "spec_patterns": ["docs/*spec*.md"],
        "test_roots": ["tests/"],
        "naming_convention": False,
    })
    assert report["specs_covered"] == 1
    assert report["traced"][0]["tests"] == ["tests/test_checkout.py"]


def test_uncovered_spec_reported(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "auth-spec.md").write_text("# Auth\n")
    (docs / "billing-spec.md").write_text("# Billing\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_auth.py").write_text("def test_login(): pass\n")

    report = trace_requirements(str(tmp_path), {
        "spec_patterns": ["docs/*spec*.md"],
        "test_roots": ["tests/"],
        "naming_convention": True,
    })
    assert "docs/billing-spec.md" in report["uncovered"]
    assert report["specs_covered"] == 1


def test_orphan_tests_reported(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "auth-spec.md").write_text("# Auth\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_auth.py").write_text("def test_login(): pass\n")
    (tests / "test_random_utils.py").write_text("def test_rand(): pass\n")

    report = trace_requirements(str(tmp_path), {
        "spec_patterns": ["docs/*spec*.md"],
        "test_roots": ["tests/"],
        "naming_convention": True,
    })
    assert "tests/test_random_utils.py" in report["orphan_tests"]


def test_format_report_completed():
    report = {
        "status": "completed",
        "specs_total": 3,
        "specs_covered": 2,
        "coverage_percent": 66.7,
        "traced": [{"spec": "docs/a-spec.md", "tests": ["tests/test_a.py"]}],
        "uncovered": ["docs/b-spec.md"],
        "orphan_tests": ["tests/test_z.py"],
    }
    output = format_report(report)
    assert "66.7%" in output
    assert "Uncovered" in output
    assert "b-spec.md" in output
    assert "Orphan" in output

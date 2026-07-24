"""Tests for plan_validator.py — structural quality gate for development plans."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from fettle.plan_validator import validate_plan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_wp(name: str, rows: list) -> str:
    lines = [
        f"### {name}",
        "",
        "| # | Task | Method | Verify by |",
        "|---|------|--------|-----------|",
    ]
    for i, (task, method, verify) in enumerate(rows, 1):
        lines.append(f"| {i} | {task} | {method} | {verify} |")
    return "\n".join(lines)


def make_plan(*wps):
    return "# Test Plan\n\n" + "\n\n".join(wps)


# ---------------------------------------------------------------------------
# 1. Valid plan with all four test types
# ---------------------------------------------------------------------------

def test_valid_all_four_types():
    wp = make_wp("WP-1 Auth module", [
        ("Write unit tests for login()", "TDD", "pytest tests/test_auth.py passes"),
        ("Wire login() into request handler", "INTEGRATION", "POST /login returns 200 on running server"),
        ("Guard empty-password bypass — regression for 2026-04-01 incident", "REGRESSION", "pytest test_regression_empty_pw passes"),
        ("Smoke test login on staging", "LIVE", "run `curl -X POST staging/login` returns 200; logs clean"),
    ])
    result = validate_plan(make_plan(wp))
    assert result.passed, result.errors


# ---------------------------------------------------------------------------
# 2. Missing TDD
# ---------------------------------------------------------------------------

def test_missing_tdd_fails():
    wp = make_wp("WP-1 Auth module", [
        ("Wire login() into handler", "INTEGRATION", "POST /login 200"),
        ("Guard empty-password bypass — regression for 2026-04-01 incident", "REGRESSION", "test_reg passes"),
        ("Smoke test on staging", "LIVE", "run `curl staging/login` returns 200"),
    ])
    result = validate_plan(make_plan(wp))
    assert not result.passed
    assert any("TDD" in e for e in result.errors)


# ---------------------------------------------------------------------------
# 3. Missing INTEGRATION
# ---------------------------------------------------------------------------

def test_missing_integration_fails():
    wp = make_wp("WP-1 Auth module", [
        ("Write unit tests for login()", "TDD", "pytest passes"),
        ("Guard empty-password bypass — regression for 2026-04-01 incident", "REGRESSION", "test_reg passes"),
        ("Smoke test on staging", "LIVE", "run `curl staging/login` returns 200"),
    ])
    result = validate_plan(make_plan(wp))
    assert not result.passed
    assert any("INTEGRATION" in e for e in result.errors)


# ---------------------------------------------------------------------------
# 4. Missing REGRESSION
# ---------------------------------------------------------------------------

def test_missing_regression_fails():
    wp = make_wp("WP-1 Auth module", [
        ("Write unit tests for login()", "TDD", "pytest passes"),
        ("Wire login() into handler", "INTEGRATION", "POST /login 200"),
        ("Smoke test on staging", "LIVE", "run `curl staging/login` returns 200"),
    ])
    result = validate_plan(make_plan(wp))
    assert not result.passed
    assert any("REGRESSION" in e for e in result.errors)


# ---------------------------------------------------------------------------
# 5. Missing LIVE
# ---------------------------------------------------------------------------

def test_missing_live_fails():
    wp = make_wp("WP-1 Auth module", [
        ("Write unit tests for login()", "TDD", "pytest passes"),
        ("Wire login() into handler", "INTEGRATION", "POST /login 200"),
        ("Guard empty-password bypass — regression for 2026-04-01 incident", "REGRESSION", "test_reg passes"),
    ])
    result = validate_plan(make_plan(wp))
    assert not result.passed
    assert any("LIVE" in e for e in result.errors)


# ---------------------------------------------------------------------------
# 6. REGRESSION task too generic (no incident reference)
# ---------------------------------------------------------------------------

def test_regression_generic_fails():
    wp = make_wp("WP-1 Auth module", [
        ("Write unit tests for login()", "TDD", "pytest passes"),
        ("Wire login() into handler", "INTEGRATION", "POST /login 200"),
        ("Regression test", "REGRESSION", "passes"),
        ("Smoke test on staging", "LIVE", "run `curl staging/login` returns 200"),
    ])
    result = validate_plan(make_plan(wp))
    assert not result.passed
    assert any("REGRESSION" in e and "generic" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# 7. LIVE task missing command
# ---------------------------------------------------------------------------

def test_live_missing_command_fails():
    wp = make_wp("WP-1 Auth module", [
        ("Write unit tests for login()", "TDD", "pytest passes"),
        ("Wire login() into handler", "INTEGRATION", "POST /login 200"),
        ("Guard empty-password bypass — regression for 2026-04-01 incident", "REGRESSION", "test_reg passes"),
        ("Verify it works on the live system", "LIVE", "confirm it works"),
    ])
    result = validate_plan(make_plan(wp))
    assert not result.passed
    assert any("LIVE" in e and "command" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# 8. INSPECT/VERIFY-only WP — no implementation gate fires
# ---------------------------------------------------------------------------

def test_inspect_only_wp_passes():
    wp = make_wp("WP-2 Config audit", [
        ("Check systemd unit permissions", "INSPECT", "ls -la shows 0640"),
        ("Verify HMAC key is 256-bit", "VERIFY", "wc -c key confirms 32 bytes"),
    ])
    result = validate_plan(make_plan(wp))
    assert result.passed, result.errors


# ---------------------------------------------------------------------------
# 9. No WP sections at all
# ---------------------------------------------------------------------------

def test_no_wps_fails():
    result = validate_plan("# My Plan\n\nSome text with no work packages.")
    assert not result.passed
    assert any("no work packages" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# 10. Missing Method column in task table
# ---------------------------------------------------------------------------

def test_missing_method_column_fails():
    wp = "### WP-1 Auth module\n\n| # | Task | Verify by |\n|---|------|----------|\n| 1 | Build feature | done |\n"
    result = validate_plan(make_plan(wp))
    assert not result.passed
    assert any("method" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# 11. Case-insensitive method matching
# ---------------------------------------------------------------------------

def test_method_case_insensitive():
    wp = make_wp("WP-1 Auth module", [
        ("Write unit tests", "tdd", "pytest passes"),
        ("Integration test against running system", "integration", "system responds"),
        ("Guard login bypass — regression for 2026-04-01 empty-password incident", "regression", "pytest test_reg passes"),
        ("Live smoke test on staging", "live", "run `curl staging/login` confirms 200 response logged"),
    ])
    result = validate_plan(make_plan(wp))
    assert result.passed, result.errors


# ---------------------------------------------------------------------------
# 12. All four missing — reports all simultaneously
# ---------------------------------------------------------------------------

def test_all_four_missing_reported():
    wp = "### WP-1 Auth module\n\n| # | Task | Method | Verify by |\n|---|------|--------|----------|\n| 1 | Implement login | BUILD | code written |\n"
    result = validate_plan(make_plan(wp))
    assert not result.passed
    for method in ("TDD", "INTEGRATION", "REGRESSION", "LIVE"):
        assert any(method in e for e in result.errors), f"Missing error for {method}"


# ---------------------------------------------------------------------------
# 13. Multiple WPs — second WP missing LIVE
# ---------------------------------------------------------------------------

def test_multiple_wps_second_missing_live():
    wp1 = make_wp("WP-1 Auth module", [
        ("Write unit tests for login()", "TDD", "pytest passes"),
        ("Wire login() into handler", "INTEGRATION", "POST /login 200"),
        ("Guard empty-password bypass — regression for 2026-04-01 incident", "REGRESSION", "test_reg passes"),
        ("Smoke test on staging", "LIVE", "run `curl staging/login` returns 200"),
    ])
    wp2 = make_wp("WP-2 Session module", [
        ("Write unit tests for session()", "TDD", "pytest passes"),
        ("Wire session into handler", "INTEGRATION", "GET /session 200"),
        ("Guard session fixation — regression for 2026-04-02 fixation incident", "REGRESSION", "test_fixation passes"),
        # Missing LIVE intentionally
    ])
    result = validate_plan(make_plan(wp1, wp2))
    assert not result.passed
    assert any("WP-2" in e for e in result.errors)
    assert any("LIVE" in e for e in result.errors)


# ---------------------------------------------------------------------------
# 14. REVIEW-only WP passes without test types
# ---------------------------------------------------------------------------

def test_review_only_wp_passes():
    wp = make_wp("WP-3 Security scan", [
        ("Audit all exec() calls in bridge", "REVIEW", "grep confirms no unsafe patterns"),
        ("Check import graph for suspicious deps", "REVIEW", "import_graph.py output reviewed"),
    ])
    result = validate_plan(make_plan(wp))
    assert result.passed, result.errors


# ---------------------------------------------------------------------------
# 15. Pipeline completeness — queue flag without state-transition LIVE fails
# ---------------------------------------------------------------------------

def test_pipeline_completeness_fails_without_transition():
    wp = make_wp("WP-1 Ingestion pipeline", [
        ("Write ingest_episode with processed flag", "TDD", "pytest passes"),
        ("Wire into bridge hooks", "INTEGRATION", "bridge calls ingest_episode"),
        ("Guard incident INC-2026-0501-B", "REGRESSION", "test_pipeline_e2e passes"),
        ("Run ingest_episode on live bridge — verify episode_id returned", "LIVE",
         "run `python3 -c 'from myapp.memory import Memory'` returns without error"),
    ])
    result = validate_plan(make_plan(wp))
    assert not result.passed, "Should fail: LIVE task has no state-transition assertion"
    assert any("state transition" in e.lower() for e in result.errors), result.errors


# ---------------------------------------------------------------------------
# 16. Pipeline completeness — queue flag with state-transition LIVE passes
# ---------------------------------------------------------------------------

def test_pipeline_completeness_passes_with_transition():
    wp = make_wp("WP-1 Ingestion pipeline", [
        ("Write ingest_episode setting processed=0", "TDD", "pytest passes"),  # fettle:queue-consumer-verified consumer=validator-test-data
        ("Wire extraction consumer end-to-end", "INTEGRATION", "facts > 0 after ingest"),
        ("Guard incident INC-2026-0501-B", "REGRESSION", "test_pipeline_e2e passes"),
        ("Run ingest_episode; assert facts > 0 and processed=1 transition confirmed", "LIVE",
         "run `pytest tests/test_pipeline_e2e.py` — facts count > 0, processed=1 verified"),
    ])
    result = validate_plan(make_plan(wp))
    assert result.passed, result.errors


# ---------------------------------------------------------------------------
# 17. Health inversion — health keyword without inversion test fails
# ---------------------------------------------------------------------------

def test_health_inversion_fails_without_inversion_test():
    wp = make_wp("WP-1 KHI health score", [
        ("Implement KHI responsiveness dimension", "TDD", "pytest passes"),
        ("Wire KHI into bridge loop", "INTEGRATION", "khi.json written every 60s"),
        ("Guard KHI score drift — regression for 2026-04-30 incident", "REGRESSION",
         "test_khi_baseline passes"),
        ("Verify KHI composite score returned on live bridge", "LIVE",
         "run `cat .fettle/state/khi.json` — composite score present"),
    ])
    result = validate_plan(make_plan(wp))
    assert not result.passed, "Should fail: no inversion test for health component"
    assert any("inversion" in e.lower() for e in result.errors), result.errors


# ---------------------------------------------------------------------------
# 18. Health inversion — health keyword with inversion test passes
# ---------------------------------------------------------------------------

def test_health_inversion_passes_with_inversion_test():
    wp = make_wp("WP-1 KHI health score", [
        ("Implement KHI responsiveness returning None on no data", "TDD", "pytest passes"),
        ("Wire KHI into bridge loop", "INTEGRATION", "khi.json written every 60s"),
        ("Guard KHI inversion 2026-05-01 — inject empty log, assert status=unknown not 1.0", "REGRESSION",
         "test_khi_bridge_down passes — composite < 0.5 and status=unknown confirmed"),
        ("Stop bridge; verify KHI status=unknown or degraded, not 1.0", "LIVE",
         "run `systemctl stop telegram-bridge && cat state/khi.json` — status=unknown, composite < 0.5"),
    ])
    result = validate_plan(make_plan(wp))
    assert result.passed, result.errors


# ---------------------------------------------------------------------------
# 19. REGRESSION: incident INC-2026-0501-B
# ---------------------------------------------------------------------------

def test_regression_incident_b_as_written_rejected():
    """Exact shape of incident INC-2026-0501-B."""
    wp = make_wp("WP-2 Entity extraction pipeline", [
        ("Implement ingest_episode storing processed=0", "TDD", "pytest: episode_id returned, journal has rows"),  # fettle:queue-consumer-verified consumer=validator-test-data
        ("Wire bridge hooks to call ingest_episode", "INTEGRATION", "bridge calls ingest_episode on every message"),
        ("Guard journal row insertion — regression for missing row test", "REGRESSION",
         "test_journal_append passes: episode row exists in journal.db"),
        ("Run on live bridge — verify episode_id returned", "LIVE",
         "run `python3 -c 'print(memory.ingest_episode(...))'` — episode_id returned without error"),
    ])
    result = validate_plan(make_plan(wp))
    assert not result.passed, "incident INC-2026-0501-B"
    assert any("state transition" in e.lower() for e in result.errors), (
        f"Expected 'state transition' error, got: {result.errors}"
    )


# ---------------------------------------------------------------------------
# 20. REGRESSION: incident INC-2026-0501-A
# ---------------------------------------------------------------------------

def test_regression_incident_a_as_written_rejected():
    """Exact shape of incident INC-2026-0501-A."""
    wp = make_wp("WP-1 Klaus Health Index", [
        ("Implement KHI 5-dimension health score", "TDD", "pytest: composite score returned"),
        ("Wire KHILoop into bridge startup", "INTEGRATION", "khi.json written every 60s on live bridge"),
        ("Guard KHI score computation — regression for prior score drift", "REGRESSION",
         "test_khi_weights passes: composite = weighted average of dimensions"),
        ("Verify KHI composite score on live bridge", "LIVE",
         "run `cat .fettle/state/khi.json` — composite score present and non-zero"),
    ])
    result = validate_plan(make_plan(wp))
    assert not result.passed, "incident INC-2026-0501-A"
    assert any("inversion" in e.lower() for e in result.errors), (
        f"Expected 'inversion' error, got: {result.errors}"
    )

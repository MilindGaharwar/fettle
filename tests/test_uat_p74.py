"""P74 contract tests — web surface drivability and capture contract."""

from __future__ import annotations


from fettle.uat.session import build_prompt, drivable_surfaces


def test_web_is_drivable_when_playwright_importable():
    try:
        import playwright  # noqa: F401
        has_pw = True
    except ImportError:
        has_pw = False

    surfaces = drivable_surfaces()
    if has_pw:
        assert "web" in surfaces
    else:
        assert "web" not in surfaces


def test_charter_prompt_includes_web_browser_discipline():
    prompt = build_prompt("web", [], {"explore": True, "app_url": "http://x"})
    assert "playwright" in prompt.lower()
    assert "Never bypass the UI" in prompt


def test_capture_web_page_contract_without_browser(tmp_path):
    """capture_web_page returns a tool_error envelope when browsers are
    missing rather than raising — session completion is never masked."""
    from fettle.uat.artifacts import capture_web_page

    result = capture_web_page("http://127.0.0.1:9/unreachable", str(tmp_path))

    assert result["status"] in ("completed", "tool_error")
    if result["status"] == "tool_error":
        assert result["message"]

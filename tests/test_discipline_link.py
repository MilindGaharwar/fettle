"""WP-G — Shared discipline_link helper tests."""

from discipline_link import get_reminder, TRIGGER_SKILL_MAP


def _make_config(tmp_path, enabled=True, cooldown=300):
    return {
        "gates": {
            "discipline_link": {
                "enabled": enabled,
                "skills_path": str(tmp_path / "skills"),
                "cooldown_seconds": cooldown,
            },
        },
    }


def _create_skill(tmp_path, skill_name, content):
    skill_dir = tmp_path / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\n---\n# Title\n\n{content}"
    )


def test_all_triggers_have_mappings():
    """Every trigger in the map resolves to a known skill."""
    for _trigger, skill in TRIGGER_SKILL_MAP.items():
        assert skill.startswith("discipline-")


def test_reminder_with_skill_present(tmp_path):
    """When skill exists, returns 2 sentences from it."""
    _create_skill(tmp_path, "discipline-debugging",
                  "First observation sentence. Second hypothesis sentence. Third extra.")
    config = _make_config(tmp_path)
    state_dir = str(tmp_path / "state")

    result = get_reminder(config, "loop_detect", state_dir, "sess1")
    assert "First observation" in result
    assert "Second hypothesis" in result
    assert "Third" not in result


def test_reminder_with_skill_absent(tmp_path):
    """When skill missing, returns fallback."""
    config = _make_config(tmp_path)
    state_dir = str(tmp_path / "state")

    result = get_reminder(config, "loop_detect", state_dir, "sess2")
    assert "Pause and inspect" in result


def test_cooldown_suppresses(tmp_path):
    """Second call within cooldown returns empty."""
    _create_skill(tmp_path, "discipline-debugging", "Sentence one. Sentence two.")
    config = _make_config(tmp_path, cooldown=300)
    state_dir = str(tmp_path / "state")

    r1 = get_reminder(config, "loop_detect", state_dir, "sess3")
    assert r1  # first call gets reminder

    r2 = get_reminder(config, "loop_detect", state_dir, "sess3")
    assert r2 == ""  # within cooldown


def test_disabled_returns_empty(tmp_path):
    """When disabled, returns empty regardless."""
    _create_skill(tmp_path, "discipline-debugging", "Content here. More content.")
    config = _make_config(tmp_path, enabled=False)
    state_dir = str(tmp_path / "state")

    result = get_reminder(config, "loop_detect", state_dir, "sess4")
    assert result == ""


def test_unknown_trigger_returns_empty(tmp_path):
    """Unknown trigger name returns empty."""
    config = _make_config(tmp_path)
    state_dir = str(tmp_path / "state")

    result = get_reminder(config, "nonexistent_check", state_dir, "sess5")
    assert result == ""


def test_each_trigger_has_unique_cooldown(tmp_path):
    """Different triggers have independent cooldowns."""
    _create_skill(tmp_path, "discipline-debugging", "Debug one. Debug two.")
    _create_skill(tmp_path, "discipline-planning", "Plan one. Plan two.")
    config = _make_config(tmp_path, cooldown=300)
    state_dir = str(tmp_path / "state")

    r1 = get_reminder(config, "loop_detect", state_dir, "sess6")
    assert r1  # loop_detect fires

    r2 = get_reminder(config, "scope_creep", state_dir, "sess6")
    assert r2  # scope_creep fires independently

    r3 = get_reminder(config, "loop_detect", state_dir, "sess6")
    assert r3 == ""  # loop_detect still in cooldown

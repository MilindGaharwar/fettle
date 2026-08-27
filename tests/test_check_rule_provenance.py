from pathlib import Path

from scripts.check_rule_provenance import validate


ROOT = Path(__file__).parent.parent


def test_repository_rule_provenance_is_complete():
    assert validate(ROOT / "rules") == []


def test_ci_runs_rule_provenance_check():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "python scripts/check_rule_provenance.py" in workflow


def test_rule_without_provenance_fails_closed(tmp_path):
    rules = tmp_path / "rules"
    (rules / "learned").mkdir(parents=True)
    (rules / "learned" / "new-rule.yml").write_text("rules: []\n", encoding="utf-8")
    (rules / "PROVENANCE.md").write_text(
        "| File | Origin | Upstream | Licence |\n"
        "| --- | --- | --- | --- |\n",
        encoding="utf-8",
    )

    assert validate(rules) == ["missing provenance entry: learned/new-rule.yml"]


def test_stale_duplicate_and_placeholder_entries_fail(tmp_path):
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "known.toml").write_text("line-length = 100\n", encoding="utf-8")
    (rules / "PROVENANCE.md").write_text(
        "| File | Origin | Upstream | Licence |\n"
        "| --- | --- | --- | --- |\n"
        "| `known.toml` | Written here | None | Apache-2.0 |\n"
        "| `known.toml` | Written here | None | Apache-2.0 |\n"
        "| `gone.yml` | TBD | None | Apache-2.0 |\n",
        encoding="utf-8",
    )

    errors = validate(rules)

    assert any("duplicate entry for known.toml" in error for error in errors)
    assert any("placeholder provenance for gone.yml" in error for error in errors)


def test_uppercase_rule_extension_is_rejected(tmp_path):
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "rule.YML").write_text("rules: []\n", encoding="utf-8")
    (rules / "PROVENANCE.md").write_text(
        "| File | Origin | Upstream | Licence |\n"
        "| --- | --- | --- | --- |\n",
        encoding="utf-8",
    )

    assert validate(rules) == ["unsupported rule extension casing: rule.YML"]

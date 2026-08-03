"""Tests for fettle.migration_safety — database migration risk detection."""

from fettle.migration_safety import check_migration_safety


class TestCheckMigrationSafety:
    def test_drop_table_flagged(self, tmp_path):
        f = tmp_path / "001.sql"
        f.write_text("DROP TABLE sessions;\n")
        findings = check_migration_safety([str(f)])
        assert len(findings) == 1
        assert "DROP TABLE" in findings[0].message

    def test_drop_column_flagged(self, tmp_path):
        f = tmp_path / "002.sql"
        f.write_text("ALTER TABLE users DROP COLUMN email;\n")
        findings = check_migration_safety([str(f)])
        assert len(findings) == 1
        assert "DROP COLUMN" in findings[0].message

    def test_not_null_without_default_flagged(self, tmp_path):
        f = tmp_path / "003.sql"
        f.write_text("ALTER TABLE users ADD COLUMN age INTEGER NOT NULL;\n")
        findings = check_migration_safety([str(f)])
        assert len(findings) >= 1
        assert any("NOT NULL" in fi.message for fi in findings)

    def test_not_null_with_default_ok(self, tmp_path):
        f = tmp_path / "004.sql"
        f.write_text("ALTER TABLE users ADD COLUMN age INTEGER NOT NULL DEFAULT 0;\n")
        findings = check_migration_safety([str(f)])
        not_null_findings = [fi for fi in findings if "NOT NULL" in fi.message]
        assert len(not_null_findings) == 0

    def test_safe_migration_no_findings(self, tmp_path):
        f = tmp_path / "005.sql"
        f.write_text("ALTER TABLE users ADD COLUMN nickname TEXT;\nCREATE INDEX idx ON users(email);\n")
        findings = check_migration_safety([str(f)])
        assert findings == []

    def test_missing_file_skipped(self):
        findings = check_migration_safety(["/nonexistent/migration.sql"])
        assert findings == []

    def test_multiple_risks_in_one_file(self, tmp_path):
        f = tmp_path / "006.sql"
        f.write_text("DROP TABLE old;\nTRUNCATE TABLE cache;\n")
        findings = check_migration_safety([str(f)])
        assert len(findings) == 2

    def test_rename_table_flagged(self, tmp_path):
        f = tmp_path / "007.sql"
        f.write_text("RENAME TABLE users TO members;\n")
        findings = check_migration_safety([str(f)])
        assert len(findings) == 1
        assert "RENAME" in findings[0].message

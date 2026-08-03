"""Tests for fettle.schema_drift — generated code / schema drift detection."""

import time

from fettle.schema_drift import check_schema_drift


class TestCheckSchemaDrift:
    def test_source_missing_no_finding(self, tmp_path):
        config = [{"source": "schema.graphql", "output": "types.ts"}]
        findings = check_schema_drift(str(tmp_path), config)
        assert findings == []

    def test_output_missing_when_source_exists(self, tmp_path):
        (tmp_path / "schema.graphql").write_text("type Query { hello: String }")
        config = [{"source": "schema.graphql", "output": "types.ts",
                   "command": "codegen"}]
        findings = check_schema_drift(str(tmp_path), config)
        assert len(findings) == 1
        assert "missing" in findings[0].message.lower()
        assert findings[0].suggested_fix == "Run: codegen"

    def test_no_drift_when_output_is_newer(self, tmp_path):
        src = tmp_path / "schema.graphql"
        out = tmp_path / "types.ts"
        src.write_text("type Query { hello: String }")
        time.sleep(0.01)
        out.write_text("// generated")
        config = [{"source": "schema.graphql", "output": "types.ts"}]
        findings = check_schema_drift(str(tmp_path), config)
        assert findings == []

    def test_drift_detected_when_source_is_newer(self, tmp_path):
        out = tmp_path / "types.ts"
        out.write_text("// generated")
        time.sleep(0.01)
        src = tmp_path / "schema.graphql"
        src.write_text("type Query { hello: String, world: String }")
        config = [{"source": "schema.graphql", "output": "types.ts",
                   "command": "npm run codegen"}]
        findings = check_schema_drift(str(tmp_path), config)
        assert len(findings) == 1
        assert "drift" in findings[0].message.lower()
        assert "npm run codegen" in findings[0].suggested_fix

    def test_multiple_entries(self, tmp_path):
        (tmp_path / "a.proto").write_text("syntax = 'proto3';")
        (tmp_path / "b.proto").write_text("syntax = 'proto3';")
        config = [
            {"source": "a.proto", "output": "a_pb2.py"},
            {"source": "b.proto", "output": "b_pb2.py"},
        ]
        findings = check_schema_drift(str(tmp_path), config)
        assert len(findings) == 2

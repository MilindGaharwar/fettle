"""WP-Q — Threat Model Command tests."""

import textwrap

from fettle.threat_model import generate_threat_model, _find_entry_points, _find_data_stores


def test_generates_stride_template(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    model = generate_threat_model(str(tmp_path), "test-service")
    assert "# Threat Model: test-service" in model
    assert "Spoofing" in model
    assert "Tampering" in model
    assert "Information Disclosure" in model
    assert "Denial of Service" in model
    assert "Elevation of Privilege" in model


def test_detects_flask_routes(tmp_path):
    (tmp_path / "app.py").write_text(textwrap.dedent("""
        from flask import Flask
        app = Flask(__name__)

        @app.get("/users")
        def list_users():
            return []

        @app.post("/users")
        def create_user():
            return {}
    """))
    entry_points = _find_entry_points(str(tmp_path))
    assert len(entry_points) >= 2


def test_detects_database_connections(tmp_path):
    (tmp_path / "db.py").write_text(textwrap.dedent("""
        from sqlalchemy import create_engine
        engine = create_engine("postgresql://localhost/mydb")
    """))
    stores = _find_data_stores(str(tmp_path))
    assert len(stores) >= 1
    assert any("create_engine" in s for s in stores)


def test_empty_project_no_crash(tmp_path):
    (tmp_path / "empty.py").write_text("")
    model = generate_threat_model(str(tmp_path), "empty")
    assert "None detected" in model


def test_model_contains_auto_detected_sections(tmp_path):
    (tmp_path / "app.py").write_text('@app.get("/api/health")\ndef health(): pass\n')
    model = generate_threat_model(str(tmp_path), "svc")
    assert "Entry Points (auto-detected)" in model
    assert "Data Stores (auto-detected)" in model
    assert "Authentication Mechanisms (auto-detected)" in model

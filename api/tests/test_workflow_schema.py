"""Tests for workflow schema migration v9."""
import sqlite3
import pytest
from db.schema import ensure_schema, SCHEMA_VERSION


def test_schema_version_is_9():
    assert SCHEMA_VERSION == 9


def test_workflows_table_exists(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)

    # Verify all three tables exist
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "workflows" in tables
    assert "workflow_runs" in tables
    assert "workflow_run_steps" in tables
    conn.close()


def test_workflows_table_columns(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(workflows)").fetchall()}
    assert cols == {
        "id", "name", "description", "project_path",
        "graph", "steps", "inputs",
        "created_at", "updated_at",
    }
    conn.close()


def test_workflow_runs_table_columns(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(workflow_runs)").fetchall()}
    assert cols == {
        "id", "workflow_id", "status", "input_values",
        "started_at", "completed_at", "error",
    }
    conn.close()


def test_workflow_run_steps_table_columns(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(workflow_run_steps)").fetchall()}
    assert cols == {
        "id", "run_id", "step_id", "status",
        "session_id", "prompt", "output",
        "started_at", "completed_at", "error",
    }
    conn.close()


def test_migration_from_v8(tmp_path):
    """Test incremental migration from v8 to v9."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Simulate v8 state
    conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT)")
    conn.execute("INSERT INTO schema_version (version) VALUES (8)")
    conn.commit()

    # Run migration
    ensure_schema(conn)

    # Check version updated
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    assert row[0] == 9

    # Check tables created
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "workflows" in tables
    assert "workflow_runs" in tables
    assert "workflow_run_steps" in tables
    conn.close()

"""Integration test: create workflow, verify it's retrievable, delete it."""
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Set up paths before any imports from the project
_tests_dir = Path(__file__).parent
_api_dir = _tests_dir.parent.parent
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))


@pytest.fixture
def client(tmp_path):
    """Create a test client with a real SQLite DB."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    from db.schema import ensure_schema

    ensure_schema(conn)
    conn.close()

    with (
        patch("db.connection.get_db_path", return_value=db_path),
        patch("config.settings.use_sqlite", True),
    ):
        from main import app

        yield TestClient(app)


def test_workflow_crud_lifecycle(client):
    """Full CRUD lifecycle for a workflow."""
    # Create
    payload = {
        "name": "e2e-test",
        "graph": {"nodes": [{"id": "s1", "position": {"x": 0, "y": 0}}], "edges": []},
        "steps": [{"id": "s1", "prompt_template": "Say hello"}],
        "inputs": [],
    }
    resp = client.post("/workflows", json=payload)
    assert resp.status_code == 201
    wf_id = resp.json()["id"]

    # Read
    resp = client.get(f"/workflows/{wf_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "e2e-test"

    # Update
    payload["name"] = "e2e-updated"
    resp = client.put(f"/workflows/{wf_id}", json=payload)
    assert resp.status_code == 200
    assert resp.json()["name"] == "e2e-updated"

    # List
    resp = client.get("/workflows")
    assert any(w["id"] == wf_id for w in resp.json())

    # Runs (empty)
    resp = client.get(f"/workflows/{wf_id}/runs")
    assert resp.status_code == 200
    assert resp.json() == []

    # Delete
    resp = client.delete(f"/workflows/{wf_id}")
    assert resp.status_code == 204

    # Verify deleted
    resp = client.get(f"/workflows/{wf_id}")
    assert resp.status_code == 404

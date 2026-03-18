"""Tests for sync_teams v4 router."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import sqlite3
from unittest.mock import MagicMock, AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from db.schema import ensure_schema
from domain.team import Team, TeamStatus, AuthorizationError
from domain.member import Member, MemberStatus
from services.sync.pairing_service import PairingInfo


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    ensure_schema(c)
    return c


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.user_id = "jayant"
    config.machine_tag = "macbook"
    config.member_tag = "jayant.macbook"
    config.syncthing = MagicMock()
    config.syncthing.device_id = "DEV-SELF"
    config.syncthing.api_key = "test-key"
    return config


@pytest.fixture
def mock_team_svc():
    svc = MagicMock()
    svc.create_team = AsyncMock()
    svc.add_member = AsyncMock()
    svc.remove_member = AsyncMock()
    svc.dissolve_team = AsyncMock()
    return svc


@pytest.fixture
def mock_pairing_svc():
    svc = MagicMock()
    svc.validate_code = MagicMock()
    svc.generate_code = MagicMock()
    return svc


@pytest.fixture
def client(conn, mock_config, mock_team_svc, mock_pairing_svc):
    from routers.sync_teams import router, get_team_svc, get_pairing_svc
    from routers.sync_deps import get_conn, require_config

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[require_config] = lambda: mock_config
    app.dependency_overrides[get_team_svc] = lambda: mock_team_svc
    app.dependency_overrides[get_pairing_svc] = lambda: mock_pairing_svc
    return TestClient(app)


class TestCreateTeam:
    def test_returns_201(self, client, mock_team_svc):
        mock_team_svc.create_team.return_value = Team(
            name="karma",
            leader_device_id="DEV-SELF",
            leader_member_tag="jayant.macbook",
        )
        resp = client.post("/sync/teams", json={"name": "karma"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "karma"
        assert data["leader_member_tag"] == "jayant.macbook"
        assert data["status"] == "active"
        mock_team_svc.create_team.assert_called_once()

    def test_missing_name_returns_422(self, client):
        resp = client.post("/sync/teams", json={})
        assert resp.status_code == 422

    def test_invalid_name_returns_400(self, client):
        resp = client.post("/sync/teams", json={"name": "a"})
        assert resp.status_code == 400

    def test_service_error_returns_400(self, client, mock_team_svc):
        mock_team_svc.create_team.side_effect = ValueError("already exists")
        resp = client.post("/sync/teams", json={"name": "karma"})
        assert resp.status_code == 400


class TestListTeams:
    def test_empty_list(self, client):
        resp = client.get("/sync/teams")
        assert resp.status_code == 200
        assert resp.json()["teams"] == []

    def test_returns_teams(self, client, conn):
        from repositories.team_repo import TeamRepository

        TeamRepository().save(
            conn,
            Team(name="alpha", leader_device_id="D1", leader_member_tag="a.mac"),
        )
        resp = client.get("/sync/teams")
        assert resp.status_code == 200
        teams = resp.json()["teams"]
        assert len(teams) == 1
        assert teams[0]["name"] == "alpha"


class TestGetTeam:
    def test_returns_detail(self, client, conn):
        from repositories.team_repo import TeamRepository

        TeamRepository().save(
            conn,
            Team(name="beta", leader_device_id="D2", leader_member_tag="b.mac"),
        )
        resp = client.get("/sync/teams/beta")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "beta"
        assert "members" in data
        assert "projects" in data
        assert "subscriptions" in data

    def test_not_found_returns_404(self, client):
        resp = client.get("/sync/teams/nonexistent")
        assert resp.status_code == 404


class TestAddMember:
    def test_with_pairing_code(self, client, mock_team_svc, mock_pairing_svc):
        mock_pairing_svc.validate_code.return_value = PairingInfo(
            member_tag="ayush.laptop", device_id="DEV-A",
        )
        mock_team_svc.add_member.return_value = Member(
            member_tag="ayush.laptop",
            team_name="karma",
            device_id="DEV-A",
            user_id="ayush",
            machine_tag="laptop",
            status=MemberStatus.ADDED,
        )
        resp = client.post(
            "/sync/teams/karma/members",
            json={"pairing_code": "ABCD-1234"},
        )
        assert resp.status_code == 201
        assert resp.json()["member_tag"] == "ayush.laptop"
        assert resp.json()["status"] == "added"

    def test_invalid_code_returns_400(self, client, mock_pairing_svc):
        mock_pairing_svc.validate_code.side_effect = ValueError("bad code")
        resp = client.post(
            "/sync/teams/karma/members",
            json={"pairing_code": "BAD"},
        )
        assert resp.status_code == 400

    def test_auth_error_returns_403(self, client, mock_team_svc, mock_pairing_svc):
        mock_pairing_svc.validate_code.return_value = PairingInfo(
            member_tag="x.y", device_id="D",
        )
        mock_team_svc.add_member.side_effect = AuthorizationError("not leader")
        resp = client.post(
            "/sync/teams/karma/members",
            json={"pairing_code": "ABCD-1234"},
        )
        assert resp.status_code == 403


class TestRemoveMember:
    def test_returns_200(self, client, mock_team_svc):
        mock_team_svc.remove_member.return_value = Member(
            member_tag="ayush.laptop",
            team_name="karma",
            device_id="DEV-A",
            user_id="ayush",
            machine_tag="laptop",
            status=MemberStatus.REMOVED,
        )
        resp = client.delete("/sync/teams/karma/members/ayush.laptop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"

    def test_auth_error_returns_403(self, client, mock_team_svc):
        mock_team_svc.remove_member.side_effect = AuthorizationError("not leader")
        resp = client.delete("/sync/teams/karma/members/x.y")
        assert resp.status_code == 403


class TestDissolveTeam:
    def test_returns_200(self, client, mock_team_svc):
        mock_team_svc.dissolve_team.return_value = Team(
            name="karma",
            leader_device_id="DEV-SELF",
            leader_member_tag="jayant.macbook",
            status=TeamStatus.DISSOLVED,
        )
        resp = client.delete("/sync/teams/karma")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert resp.json()["status"] == "dissolved"

    def test_auth_error_returns_403(self, client, mock_team_svc):
        mock_team_svc.dissolve_team.side_effect = AuthorizationError("not leader")
        resp = client.delete("/sync/teams/karma")
        assert resp.status_code == 403


class TestListMembers:
    def test_team_not_found(self, client):
        resp = client.get("/sync/teams/nonexistent/members")
        assert resp.status_code == 404

    def test_returns_members(self, client, conn):
        from repositories.team_repo import TeamRepository
        from repositories.member_repo import MemberRepository

        TeamRepository().save(
            conn,
            Team(name="gamma", leader_device_id="D3", leader_member_tag="c.mac"),
        )
        MemberRepository().save(
            conn,
            Member(
                member_tag="c.mac",
                team_name="gamma",
                device_id="D3",
                user_id="c",
                machine_tag="mac",
                status=MemberStatus.ACTIVE,
            ),
        )
        resp = client.get("/sync/teams/gamma/members")
        assert resp.status_code == 200
        members = resp.json()["members"]
        assert len(members) == 1
        assert members[0]["member_tag"] == "c.mac"

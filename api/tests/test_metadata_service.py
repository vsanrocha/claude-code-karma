# api/tests/test_metadata_service.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest
from domain.team import Team
from domain.member import Member, MemberStatus
from domain.project import SharedProject
from domain.subscription import Subscription, SubscriptionStatus, SyncDirection
from services.sync.metadata_service import MetadataService


@pytest.fixture
def meta_base(tmp_path):
    return tmp_path / "karma-metadata"


@pytest.fixture
def service(meta_base):
    return MetadataService(meta_base=meta_base)


@pytest.fixture
def team():
    return Team(name="karma-team", leader_device_id="DEV-L", leader_member_tag="jayant.macbook")


@pytest.fixture
def leader():
    return Member(
        member_tag="jayant.macbook", team_name="karma-team",
        device_id="DEV-L", user_id="jayant", machine_tag="macbook",
        status=MemberStatus.ACTIVE,
    )


@pytest.fixture
def member():
    return Member(
        member_tag="ayush.laptop", team_name="karma-team",
        device_id="DEV-A", user_id="ayush", machine_tag="laptop",
        status=MemberStatus.ACTIVE,
    )


class TestWriteTeamState:
    def test_creates_team_json(self, service, team, leader):
        service.write_team_state(team, [leader])
        team_file = service._team_dir(team.name) / "team.json"
        assert team_file.exists()
        data = json.loads(team_file.read_text())
        assert data["name"] == "karma-team"
        assert data["created_by"] == "jayant.macbook"
        assert data["leader_device_id"] == "DEV-L"

    def test_creates_member_state_file(self, service, team, leader):
        service.write_team_state(team, [leader])
        member_file = service._team_dir(team.name) / "members" / "jayant.macbook.json"
        assert member_file.exists()
        data = json.loads(member_file.read_text())
        assert data["member_tag"] == "jayant.macbook"
        assert data["device_id"] == "DEV-L"


class TestWriteOwnState:
    def test_writes_projects_and_subscriptions(self, service, member):
        projects = [SharedProject(
            team_name="karma-team", git_identity="o/r", folder_suffix="o-r",
        )]
        subs = [Subscription(
            member_tag="ayush.laptop", team_name="karma-team",
            project_git_identity="o/r",
            status=SubscriptionStatus.ACCEPTED, direction=SyncDirection.BOTH,
        )]
        service.write_own_state("karma-team", "ayush.laptop", projects, subs)
        state_file = service._team_dir("karma-team") / "members" / "ayush.laptop.json"
        data = json.loads(state_file.read_text())
        assert len(data["projects"]) == 1
        assert data["projects"][0]["git_identity"] == "o/r"
        assert data["subscriptions"]["o/r"]["status"] == "accepted"
        assert data["subscriptions"]["o/r"]["direction"] == "both"


class TestWriteRemovalSignal:
    def test_creates_removal_file(self, service):
        service.write_removal_signal("karma-team", "ayush.laptop", removed_by="jayant.macbook")
        removal_file = service._team_dir("karma-team") / "removed" / "ayush.laptop.json"
        assert removal_file.exists()
        data = json.loads(removal_file.read_text())
        assert data["member_tag"] == "ayush.laptop"
        assert data["removed_by"] == "jayant.macbook"


class TestReadTeamMetadata:
    def test_reads_all_member_states(self, service, team, leader, member):
        service.write_team_state(team, [leader, member])
        states = service.read_team_metadata("karma-team")
        assert "jayant.macbook" in states
        assert "ayush.laptop" in states
        assert states["jayant.macbook"]["device_id"] == "DEV-L"

    def test_reads_removal_signals(self, service, team, leader):
        service.write_team_state(team, [leader])
        service.write_removal_signal("karma-team", "ayush.laptop", removed_by="jayant.macbook")
        states = service.read_team_metadata("karma-team")
        assert states.get("__removals", {}).get("ayush.laptop") is not None

    def test_empty_team_returns_empty(self, service):
        states = service.read_team_metadata("nonexistent")
        assert states == {}

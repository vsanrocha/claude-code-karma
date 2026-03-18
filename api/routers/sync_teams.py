"""Sync Teams + Members router — v4, thin delegation to TeamService."""
from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from domain.team import AuthorizationError
from routers.sync_deps import (
    get_conn,
    make_repos,
    make_team_service,
    require_config,
    validate_name,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync-teams"])


# --- Request schemas -------------------------------------------------------

class CreateTeamRequest(BaseModel):
    name: str


class AddMemberRequest(BaseModel):
    pairing_code: str


# --- Dependencies (overridable in tests) -----------------------------------

async def get_team_svc(config=Depends(require_config)):
    return make_team_service(config)


def get_pairing_svc():
    from services.sync.pairing_service import PairingService

    return PairingService()


# --- Team endpoints --------------------------------------------------------

@router.post("/teams", status_code=201)
async def create_team(
    req: CreateTeamRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    config=Depends(require_config),
    svc=Depends(get_team_svc),
):
    """Create a new team. Caller becomes the leader."""
    validate_name(req.name, "team name")
    device_id = config.syncthing.device_id if config.syncthing else ""
    try:
        team = await svc.create_team(
            conn,
            name=req.name,
            leader_member_tag=config.member_tag,
            leader_device_id=device_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _team_dict(team)


@router.get("/teams")
async def list_teams(conn: sqlite3.Connection = Depends(get_conn)):
    """List all teams."""
    repos = make_repos()
    teams = repos["teams"].list_all(conn)
    return {"teams": [_team_dict(t) for t in teams]}


@router.get("/teams/{name}")
async def get_team(name: str, conn: sqlite3.Connection = Depends(get_conn)):
    """Team detail with members, projects, and subscriptions."""
    repos = make_repos()
    team = repos["teams"].get(conn, name)
    if team is None:
        raise HTTPException(404, f"Team '{name}' not found")
    members = repos["members"].list_for_team(conn, name)
    projects = repos["projects"].list_for_team(conn, name)
    subs_list = []
    for m in members:
        subs_list.extend(repos["subs"].list_for_member(conn, m.member_tag))
    return {
        **_team_dict(team),
        "members": [_member_dict(m) for m in members],
        "projects": [
            {
                "git_identity": p.git_identity,
                "encoded_name": p.encoded_name,
                "folder_suffix": p.folder_suffix,
                "status": p.status.value,
            }
            for p in projects
        ],
        "subscriptions": [
            {
                "member_tag": s.member_tag,
                "project": s.project_git_identity,
                "status": s.status.value,
                "direction": s.direction.value,
            }
            for s in subs_list
        ],
    }


@router.delete("/teams/{name}")
async def dissolve_team(
    name: str,
    conn: sqlite3.Connection = Depends(get_conn),
    config=Depends(require_config),
    svc=Depends(get_team_svc),
):
    """Dissolve a team. Leader only."""
    device_id = config.syncthing.device_id if config.syncthing else ""
    try:
        team = await svc.dissolve_team(conn, team_name=name, by_device=device_id)
    except AuthorizationError:
        raise HTTPException(403, "Only the team leader can dissolve the team")
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True, "name": team.name, "status": team.status.value}


# --- Member endpoints ------------------------------------------------------

@router.post("/teams/{name}/members", status_code=201)
async def add_member(
    name: str,
    req: AddMemberRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    config=Depends(require_config),
    svc=Depends(get_team_svc),
    pairing=Depends(get_pairing_svc),
):
    """Add member via pairing code. Leader only."""
    try:
        info = pairing.validate_code(req.pairing_code)
    except ValueError as e:
        raise HTTPException(400, f"Invalid pairing code: {e}")
    device_id = config.syncthing.device_id if config.syncthing else ""
    try:
        member = await svc.add_member(
            conn,
            team_name=name,
            by_device=device_id,
            new_member_tag=info.member_tag,
            new_device_id=info.device_id,
        )
    except AuthorizationError:
        raise HTTPException(403, "Only the team leader can add members")
    except ValueError as e:
        raise HTTPException(404, str(e))
    return _member_dict(member)


@router.delete("/teams/{name}/members/{tag}")
async def remove_member(
    name: str,
    tag: str,
    conn: sqlite3.Connection = Depends(get_conn),
    config=Depends(require_config),
    svc=Depends(get_team_svc),
):
    """Remove a member. Leader only."""
    device_id = config.syncthing.device_id if config.syncthing else ""
    try:
        member = await svc.remove_member(
            conn, team_name=name, by_device=device_id, member_tag=tag,
        )
    except AuthorizationError:
        raise HTTPException(403, "Only the team leader can remove members")
    except ValueError as e:
        raise HTTPException(404, str(e))
    return _member_dict(member)


@router.get("/teams/{name}/members")
async def list_members(name: str, conn: sqlite3.Connection = Depends(get_conn)):
    """List team members."""
    repos = make_repos()
    team = repos["teams"].get(conn, name)
    if team is None:
        raise HTTPException(404, f"Team '{name}' not found")
    members = repos["members"].list_for_team(conn, name)
    return {"members": [_member_dict(m) for m in members]}


# --- Helpers ---------------------------------------------------------------

def _team_dict(team) -> dict:
    return {
        "name": team.name,
        "leader_member_tag": team.leader_member_tag,
        "status": team.status.value,
        "created_at": team.created_at.isoformat(),
    }


def _member_dict(member) -> dict:
    return {
        "member_tag": member.member_tag,
        "device_id": member.device_id,
        "user_id": member.user_id,
        "machine_tag": member.machine_tag,
        "status": member.status.value,
    }

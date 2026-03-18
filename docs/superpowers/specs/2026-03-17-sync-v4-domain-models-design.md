# Sync v4: Domain Models & Clean Slate Architecture

**Date:** 2026-03-17
**Status:** Approved
**Scope:** Full rewrite of sync feature — domain models, repositories, services, routers, schema

## Problem Statement

The sync feature has evolved through v1→v3, each version fixing symptoms (folder ID collisions, cross-team leaks, missing cleanup) rather than root causes. The result: ~5,000 LOC spread across 7 routers, 9 services, and 7 DB tables with no formal domain model. Business rules are scattered — "only leader can remove a member" is enforced in router code, not in a central authority.

v4 introduces proper domain modeling with Pydantic classes and state machines, a repository pattern for persistence, and a simplified architecture that eliminates handshake folders, join codes, and the policy/settings system in favor of explicit subscriptions.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Modeling approach | Pydantic models + state machines | Centralize invariants, make transitions explicit and testable |
| Persistence | Repository pattern | Pure models (no DB coupling) → testable without SQLite |
| P2P conflict resolution | Optimistic + leader authority | Leader's state wins. Members converge via metadata folder |
| Membership flow | Leader adds member | Eliminates join codes, handshake folders, bidirectional negotiation |
| Device ID exchange | Permanent pairing code | Member generates once, shares out-of-band. Leader is the gatekeeper |
| Leader failure | Catastrophic (alpha) | Team freezes if leader's machine dies. Succession planned for future |
| Project constraint | Git-only | `git_identity` (owner/repo) is the universal cross-machine key |
| Project sharing | Opt-in with direction | Leader shares → member accepts with receive/send/both |
| Branch info | Set from JSONL | `gitBranch` field on messages already collected as `Set[str]` per session |
| Migration | Clean slate | Drop all sync_* tables, recreate as v19. Alpha — breaking is acceptable |
| Reconciliation | 3 phases (from 6) | No handshakes (phase 2), no auto-accept peers (phase 3), subscription-driven folders (phase 5) |
| Network discovery | Future (v4.1) | Pairing code is primary. LAN discovery layers on top later |

## Domain Models

Four entities with explicit states and transitions. All models are frozen (immutable) — methods return new instances.

### Team

The authority boundary. Only the leader can mutate team membership and project sharing.

```python
class TeamStatus(str, Enum):
    ACTIVE = "active"
    DISSOLVED = "dissolved"

class Team(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    leader_device_id: str
    leader_member_tag: str
    status: TeamStatus = TeamStatus.ACTIVE
    created_at: datetime
```

**State machine:**
```
ACTIVE ──dissolve(by_device=leader)──→ DISSOLVED
```

**Methods:**
- `is_leader(device_id) -> bool`
- `dissolve(*, by_device) -> Team` — only leader, returns DISSOLVED
- `add_member(member, *, by_device) -> Member` — only leader, validates no duplicate member_tag
- `remove_member(member, *, by_device) -> Member` — only leader, returns member with REMOVED status

**Key invariant:** Authorization checks live on Team, not on Member/Project. Team is the single authority checkpoint.

### Member

A person + machine. Identity is `member_tag = "{user_id}.{machine_tag}"`.

```python
class MemberStatus(str, Enum):
    ADDED = "added"       # leader added, device hasn't acknowledged
    ACTIVE = "active"     # device acknowledged via metadata sync
    REMOVED = "removed"   # leader removed

class Member(BaseModel):
    model_config = ConfigDict(frozen=True)

    member_tag: str        # "user_id.machine_tag"
    team_name: str
    device_id: str
    user_id: str           # parsed from member_tag
    machine_tag: str       # parsed from member_tag
    status: MemberStatus = MemberStatus.ADDED
```

**State machine:**
```
ADDED ──activate()──→ ACTIVE ──remove()──→ REMOVED
```

**Methods:**
- `activate() -> Member` — ADDED → ACTIVE (device acknowledged)
- `remove() -> Member` — ACTIVE → REMOVED (authorization checked by Team, not here)
- `is_active -> bool` — property

### SharedProject

A project shared with a team. Git-only — `git_identity` is required.

```python
class SharedProjectStatus(str, Enum):
    SHARED = "shared"
    REMOVED = "removed"

class SharedProject(BaseModel):
    model_config = ConfigDict(frozen=True)

    team_name: str
    encoded_name: str       # local path encoding (optional — set if member has repo cloned)
    git_identity: str       # REQUIRED — "owner/repo", the universal key
    folder_suffix: str      # derived from git_identity (owner-repo)
    status: SharedProjectStatus = SharedProjectStatus.SHARED
```

**State machine:**
```
SHARED ──remove()──→ REMOVED
```

### Subscription

The member-project relationship. Controls what a member receives and sends for a specific project.

```python
class SubscriptionStatus(str, Enum):
    OFFERED = "offered"     # project shared, member hasn't responded
    ACCEPTED = "accepted"   # member accepted
    PAUSED = "paused"       # member temporarily stopped syncing
    DECLINED = "declined"   # member declined

class SyncDirection(str, Enum):
    RECEIVE = "receive"     # see teammates' sessions
    SEND = "send"           # share own sessions
    BOTH = "both"           # bidirectional

class Subscription(BaseModel):
    model_config = ConfigDict(frozen=True)

    member_tag: str
    team_name: str
    project_encoded_name: str
    status: SubscriptionStatus = SubscriptionStatus.OFFERED
    direction: SyncDirection = SyncDirection.BOTH
```

**State machine:**
```
OFFERED ──accept(direction)──→ ACCEPTED ──pause()──→ PAUSED
   │                              │                     │
   │                              │    resume()─────────┘
   │                              │
   └──decline()──→ DECLINED ←──decline()
```

**Methods:**
- `accept(direction) -> Subscription` — OFFERED → ACCEPTED
- `pause() -> Subscription` — ACCEPTED → PAUSED
- `resume() -> Subscription` — PAUSED → ACCEPTED
- `decline() -> Subscription` — any → DECLINED
- `change_direction(direction) -> Subscription` — while ACCEPTED

**Replaces three v3 concepts:** `sync_settings` (scope-based policies), `sync_rejected_folders` (persistent rejection), and the implicit "everyone gets everything" default.

## Packaged Session Metadata

When sessions are packaged for sync, they include:

```python
class PackagedSessionMeta:
    session_uuid: str
    git_identity: str        # "owner/repo" — universal project key
    branches: set[str]       # from session.get_git_branches() — already extracted from JSONL
    member_tag: str          # who created the session
    created_at: datetime
```

**Branch handling:** Each message in a Claude Code JSONL has an optional `gitBranch` field. The parser already collects these into a `Set[str]` per session via `session.get_git_branches()`. A session that spans `main` and `feature-x` shows up when filtering for either branch.

**Project mapping on receiver:** Git identity is the join key. If the receiver has the repo cloned, sessions map to their local project path. If not, sessions are shown under the git identity and auto-map when the repo is eventually cloned.

## Pairing Codes

Members generate a permanent pairing code that encodes their identity:

```python
class PairingInfo:
    member_tag: str      # "user_id.machine_tag"
    device_id: str       # Syncthing device ID

class PairingService:
    def generate_code(self, member_tag: str, device_id: str) -> str:
        """Encode to short shareable code, e.g., 'KXRM-4HPQ-ANVY'."""

    def validate_code(self, code: str) -> PairingInfo:
        """Decode pairing code back to identity."""
```

**Properties:**
- Permanent — generate once, share with any team leader
- Encodes `member_tag + device_id` (set during Syncthing setup)
- Leader is the gatekeeper — possessing a code doesn't grant access, the leader must explicitly add the member
- Displayed in member's UI with copy button for out-of-band sharing (Slack, text, etc.)

## Database Schema (v19)

Clean break. All existing sync_* tables dropped and recreated.

```sql
CREATE TABLE sync_teams (
    name             TEXT PRIMARY KEY,
    leader_device_id TEXT NOT NULL,
    leader_member_tag TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'active'
                     CHECK(status IN ('active', 'dissolved')),
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE sync_members (
    team_name        TEXT NOT NULL REFERENCES sync_teams(name) ON DELETE CASCADE,
    member_tag       TEXT NOT NULL,
    device_id        TEXT NOT NULL,
    user_id          TEXT NOT NULL,
    machine_tag      TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'added'
                     CHECK(status IN ('added', 'active', 'removed')),
    added_at         TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (team_name, member_tag)
);

CREATE TABLE sync_projects (
    team_name        TEXT NOT NULL REFERENCES sync_teams(name) ON DELETE CASCADE,
    encoded_name     TEXT NOT NULL,
    git_identity     TEXT NOT NULL,
    folder_suffix    TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'shared'
                     CHECK(status IN ('shared', 'removed')),
    shared_at        TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (team_name, encoded_name)
);

CREATE TABLE sync_subscriptions (
    member_tag       TEXT NOT NULL,
    team_name        TEXT NOT NULL,
    project_encoded_name TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'offered'
                     CHECK(status IN ('offered', 'accepted', 'paused', 'declined')),
    direction        TEXT NOT NULL DEFAULT 'both'
                     CHECK(direction IN ('receive', 'send', 'both')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (member_tag, team_name, project_encoded_name),
    FOREIGN KEY (team_name, member_tag)
        REFERENCES sync_members(team_name, member_tag) ON DELETE CASCADE,
    FOREIGN KEY (team_name, project_encoded_name)
        REFERENCES sync_projects(team_name, encoded_name) ON DELETE CASCADE
);

CREATE TABLE sync_events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type       TEXT NOT NULL,
    team_name        TEXT,
    member_tag       TEXT,
    project_encoded_name TEXT,
    session_uuid     TEXT,
    detail           TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE sync_removed_members (
    team_name        TEXT NOT NULL REFERENCES sync_teams(name) ON DELETE CASCADE,
    device_id        TEXT NOT NULL,
    member_tag       TEXT,
    removed_at       TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (team_name, device_id)
);

-- Indexes
CREATE INDEX idx_members_device ON sync_members(device_id);
CREATE INDEX idx_members_status ON sync_members(team_name, status);
CREATE INDEX idx_projects_suffix ON sync_projects(folder_suffix);
CREATE INDEX idx_subs_member ON sync_subscriptions(member_tag);
CREATE INDEX idx_subs_status ON sync_subscriptions(status);
CREATE INDEX idx_events_type ON sync_events(event_type);
CREATE INDEX idx_events_team ON sync_events(team_name);
CREATE INDEX idx_events_time ON sync_events(created_at);
```

**Migration strategy:** v19 migration drops all sync_* tables and recreates from scratch. No data migration. Users re-create teams after update.

**Changes from v18:**
- `sync_settings` → deleted (replaced by `sync_subscriptions.direction`)
- `sync_rejected_folders` → deleted (replaced by `sync_subscriptions.status='declined'`)
- `sync_members` PK changed from `(team_name, device_id)` to `(team_name, member_tag)`
- `sync_team_projects` → renamed to `sync_projects`, added `status` column
- `sync_teams` simplified — removed `join_code`, `backend`, `sync_session_limit`, `pending_leave`
- `sync_subscriptions` → new table

## Repositories

Thin persistence layer. Models never touch the DB.

```python
class TeamRepository:
    def get(self, conn, name: str) -> Team | None
    def get_by_leader(self, conn, device_id: str) -> list[Team]
    def save(self, conn, team: Team) -> None
    def delete(self, conn, name: str) -> None
    def list_all(self, conn) -> list[Team]

class MemberRepository:
    def get(self, conn, team_name: str, member_tag: str) -> Member | None
    def get_by_device(self, conn, device_id: str) -> list[Member]
    def save(self, conn, member: Member) -> None
    def list_for_team(self, conn, team_name: str) -> list[Member]
    def was_removed(self, conn, team_name: str, device_id: str) -> bool
    def record_removal(self, conn, team_name: str, device_id: str) -> None

class ProjectRepository:
    def get(self, conn, team_name: str, encoded_name: str) -> SharedProject | None
    def save(self, conn, project: SharedProject) -> None
    def list_for_team(self, conn, team_name: str) -> list[SharedProject]
    def find_by_suffix(self, conn, suffix: str) -> list[SharedProject]

class SubscriptionRepository:
    def get(self, conn, member_tag: str, team_name: str, project: str) -> Subscription | None
    def save(self, conn, sub: Subscription) -> None
    def list_for_member(self, conn, member_tag: str) -> list[Subscription]
    def list_for_project(self, conn, team_name: str, project: str) -> list[Subscription]
    def list_accepted_for_suffix(self, conn, suffix: str) -> list[Subscription]

class EventRepository:
    def log(self, conn, event: SyncEvent) -> int
    def query(self, conn, *, team: str = None, event_type: str = None, limit: int = 50) -> list[SyncEvent]
```

## Service Layer

Services orchestrate domain models, repositories, and Syncthing.

### TeamService

```python
class TeamService:
    def __init__(self, teams: TeamRepository, members: MemberRepository,
                 subs: SubscriptionRepository, events: EventRepository,
                 devices: DeviceManager, metadata: MetadataService,
                 projects: ProjectRepository): ...

    def create_team(self, conn, *, name, leader_member_tag, leader_device_id) -> Team
    def add_member(self, conn, *, team_name, by_device, new_member_tag, new_device_id) -> Member
    def remove_member(self, conn, *, team_name, by_device, member_tag) -> Member
    def dissolve_team(self, conn, *, team_name, by_device) -> Team
```

**`create_team` flow:**
1. Create Team (ACTIVE) + leader as Member (ACTIVE)
2. Save to repos
3. Write metadata folder (team.json + own member state)
4. Log TeamCreated event

**`add_member` flow:**
1. `team.add_member()` — validates leader authorization
2. Create Member (ADDED)
3. `DeviceManager.pair(device_id)` — Syncthing pairing
4. Write updated metadata
5. Create OFFERED subscription for each shared project
6. Log MemberAdded event

**`remove_member` flow:**
1. `team.remove_member()` — validates leader authorization
2. Member → REMOVED, record removal
3. Write removal signal to metadata folder
4. Remove device from all team folder device lists
5. Log MemberRemoved event

### ProjectService

```python
class ProjectService:
    def __init__(self, projects: ProjectRepository, subs: SubscriptionRepository,
                 members: MemberRepository, teams: TeamRepository,
                 folders: FolderManager, metadata: MetadataService,
                 events: EventRepository): ...

    def share_project(self, conn, *, team_name, by_device, encoded_name, git_identity) -> SharedProject
    def remove_project(self, conn, *, team_name, by_device, encoded_name) -> SharedProject
    def accept_subscription(self, conn, *, member_tag, team_name, project, direction) -> Subscription
    def pause_subscription(self, conn, *, member_tag, team_name, project) -> Subscription
    def resume_subscription(self, conn, *, member_tag, team_name, project) -> Subscription
    def decline_subscription(self, conn, *, member_tag, team_name, project) -> Subscription
    def change_direction(self, conn, *, member_tag, team_name, project, direction) -> Subscription
```

**`share_project` flow:**
1. Validate leader authorization
2. Validate git_identity is present (git-only constraint)
3. Create SharedProject (SHARED)
4. Create OFFERED subscription for each active member
5. Create leader's outbox folder in Syncthing
6. Update metadata with project list
7. Log ProjectShared event

**`accept_subscription` flow:**
1. `sub.accept(direction)` — OFFERED → ACCEPTED
2. Apply sync direction:
   - `receive` or `both` → `FolderManager.ensure_inbox_folders()`
   - `send` or `both` → `FolderManager.ensure_outbox_folder()`
3. Update metadata with subscription state
4. Log SubscriptionAccepted event

### ReconciliationService

Simplified from 6 phases to 3. Runs every 60s.

```python
class ReconciliationService:
    def run_cycle(self, conn) -> None:
        for team in self.teams.list_all(conn):
            self.phase_metadata(conn, team)
            self.phase_mesh_pair(conn, team)
            self.phase_device_lists(conn, team)
```

**Phase 1 — Metadata Reconciliation:**
- Read team metadata folder
- Detect removal signals → auto-leave if own member_tag is removed
- Discover new members → register as ADDED, transition to ACTIVE
- Discover new projects → create OFFERED subscriptions

**Phase 2 — Mesh Pairing:**
- For each active team member, ensure Syncthing device is paired
- Idempotent — skips already-paired devices

**Phase 3 — Device List Sync:**
- For each project suffix, query accepted subscriptions across all teams
- Compute desired device set
- `FolderManager.set_folder_devices()` — declarative, replaces entire device list

**Eliminated phases (from v3):**
- Phase 2 (reconcile pending handshakes) — no handshake folders in v4
- Phase 3 (auto-accept pending peers) — leader adds explicitly
- Phase 5 (auto-accept pending folders) — subscription-driven acceptance

### Syncthing Abstraction

Three focused classes replacing the monolithic `syncthing_proxy.py`:

```python
class SyncthingClient:
    """Pure HTTP wrapper. No business logic. 1:1 with Syncthing REST API."""
    def get_config(self) -> dict
    def post_config(self, config: dict) -> None
    def get_system_status(self) -> dict
    def get_connections(self) -> dict
    def get_pending_devices(self) -> list[dict]
    def get_pending_folders(self) -> list[dict]

class DeviceManager:
    """Device pairing operations."""
    def pair(self, device_id: str) -> None
    def unpair(self, device_id: str) -> None
    def ensure_paired(self, device_id: str) -> None
    def is_connected(self, device_id: str) -> bool
    def list_connected(self) -> list[str]

class FolderManager:
    """Folder lifecycle tied to subscriptions."""
    def ensure_outbox_folder(self, conn, sub: Subscription) -> None
    def ensure_inbox_folders(self, conn, sub: Subscription) -> None
    def set_folder_devices(self, suffix: str, device_ids: set[str]) -> None
    def remove_device_from_team_folders(self, conn, team: str, device_id: str) -> None
    def cleanup_team_folders(self, conn, team: str) -> None
```

### MetadataService

```python
class MetadataService:
    def write_team_state(self, team: Team, members: list[Member]) -> None
    def write_removal_signal(self, team_name: str, member_tag: str) -> None
    def read_team_metadata(self, team_name: str) -> dict[str, dict]
    def write_own_state(self, team_name: str, member_tag: str,
                       subscriptions: list[Subscription]) -> None
```

### PairingService

```python
class PairingService:
    def generate_code(self, member_tag: str, device_id: str) -> str
    def validate_code(self, code: str) -> PairingInfo
```

## API Endpoints

4 routers (down from 7):

### sync_teams.py — Team + Member Management

| Method | Endpoint | Description |
|---|---|---|
| POST | `/sync/teams` | Create team |
| GET | `/sync/teams` | List all teams |
| GET | `/sync/teams/{name}` | Team detail (members, projects, subscriptions) |
| DELETE | `/sync/teams/{name}` | Dissolve team |
| POST | `/sync/teams/{name}/members` | Add member (leader pastes pairing code) |
| DELETE | `/sync/teams/{name}/members/{tag}` | Remove member |
| GET | `/sync/teams/{name}/members` | List members with connection status |

### sync_projects.py — Project Sharing + Subscriptions

| Method | Endpoint | Description |
|---|---|---|
| POST | `/sync/teams/{name}/projects` | Share project (git-only) |
| DELETE | `/sync/teams/{name}/projects/{encoded_name}` | Remove project |
| GET | `/sync/teams/{name}/projects` | List team projects |
| POST | `/sync/subscriptions/{team}/{project}/accept` | Accept with direction |
| POST | `/sync/subscriptions/{team}/{project}/pause` | Pause subscription |
| POST | `/sync/subscriptions/{team}/{project}/resume` | Resume subscription |
| POST | `/sync/subscriptions/{team}/{project}/decline` | Decline subscription |
| PATCH | `/sync/subscriptions/{team}/{project}/direction` | Change sync direction |
| GET | `/sync/subscriptions` | List all my subscriptions |

### sync_pairing.py — Pairing + Devices

| Method | Endpoint | Description |
|---|---|---|
| GET | `/sync/pairing/code` | Generate my pairing code |
| POST | `/sync/pairing/validate` | Validate a pairing code (preview) |
| GET | `/sync/devices` | Connected devices with status |

### sync_system.py — System Status

| Method | Endpoint | Description |
|---|---|---|
| GET | `/sync/status` | Syncthing running, version, device_id |
| POST | `/sync/initialize` | First-time setup |
| POST | `/sync/reconcile` | Trigger manual reconciliation |

## File Layout

```
api/
├── domain/                              # Pure domain models
│   ├── __init__.py
│   ├── team.py                          # Team + TeamStatus
│   ├── member.py                        # Member + MemberStatus
│   ├── project.py                       # SharedProject + SharedProjectStatus
│   ├── subscription.py                  # Subscription + SubscriptionStatus + SyncDirection
│   └── events.py                        # Typed event classes
│
├── repositories/                        # SQLite persistence
│   ├── __init__.py
│   ├── team_repo.py
│   ├── member_repo.py
│   ├── project_repo.py
│   ├── subscription_repo.py
│   └── event_repo.py
│
├── services/
│   ├── sync/                            # Business operations
│   │   ├── __init__.py
│   │   ├── team_service.py
│   │   ├── project_service.py
│   │   ├── reconciliation_service.py
│   │   ├── metadata_service.py
│   │   └── pairing_service.py
│   │
│   ├── syncthing/                       # Syncthing abstraction
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── device_manager.py
│   │   └── folder_manager.py
│   │
│   ├── watcher_manager.py              # Rewritten — uses ReconciliationService
│   └── remote_sessions.py             # Unchanged — session discovery
│
├── routers/
│   ├── sync_teams.py                   # Rewritten
│   ├── sync_projects.py                # Rewritten
│   ├── sync_pairing.py                 # New
│   └── sync_system.py                  # Simplified
│
└── db/
    └── schema.py                        # v19 migration added
```

### Deleted Files

```
DELETED (v3 → v4):
api/routers/sync_members.py             → merged into sync_teams.py
api/routers/sync_pending.py             → eliminated
api/routers/sync_devices.py             → merged into sync_pairing.py
api/routers/sync_operations.py          → absorbed

api/services/sync_queries.py            → replaced by repositories/
api/services/sync_reconciliation.py     → replaced by sync/reconciliation_service.py
api/services/sync_folders.py            → replaced by syncthing/folder_manager.py
api/services/sync_metadata_reconciler.py → replaced by sync/metadata_service.py
api/services/sync_metadata_writer.py    → replaced by sync/metadata_service.py
api/services/sync_identity.py           → replaced by domain models + pairing_service
api/services/sync_policy.py             → eliminated (subscription model replaces policies)
api/services/syncthing_proxy.py         → replaced by syncthing/ package
api/db/sync_queries.py                  → replaced by repositories/

DELETED DB TABLES:
sync_settings                            → replaced by sync_subscriptions.direction
sync_rejected_folders                    → replaced by sync_subscriptions.status='declined'
```

## End-to-End Flows

### Flow 1: Leader Creates Team + Shares Project

```
Leader → POST /sync/teams { name: "karma-team" }
  → TeamService.create_team()
    → Team(ACTIVE) + leader Member(ACTIVE)
    → MetadataService.write_team_state()
      → creates karma-meta--karma-team/ folder
      → writes team.json + leader's member state

Leader → POST /sync/teams/karma-team/projects { git_identity: "owner/repo" }
  → ProjectService.share_project()
    → SharedProject(SHARED) with folder_suffix derived from git_identity
    → FolderManager.ensure_outbox_folder()
      → creates karma-out--leader.machine--owner-repo
    → MetadataService.write_own_state() (includes project list)
```

### Flow 2: Leader Adds Member via Pairing Code

```
Member's UI → GET /sync/pairing/code → "KXRM-4HPQ-ANVY"
Member shares code out-of-band (Slack, text)

Leader → POST /sync/teams/karma-team/members { pairing_code: "KXRM-4HPQ-ANVY" }
  → PairingService.validate_code() → PairingInfo(member_tag, device_id)
  → TeamService.add_member()
    → team.add_member() validates leader authorization
    → Member(ADDED)
    → DeviceManager.pair(device_id)
    → MetadataService.write_team_state() (includes new member)
    → For each shared project: Subscription(OFFERED)

═══ Syncthing syncs metadata folder ═══

Member's ReconciliationService.phase_metadata()
  → Reads metadata, finds own member_tag
  → Member ADDED → ACTIVE
  → DeviceManager.ensure_paired(leader)
  → MetadataService.write_own_state()
  → UI shows: "Added to karma-team" + offered projects
```

### Flow 3: Member Accepts Project

```
Member → POST /sync/subscriptions/karma-team/project/accept { direction: "both" }
  → ProjectService.accept_subscription()
    → sub.accept(BOTH) → OFFERED → ACCEPTED
    → FolderManager.ensure_inbox_folders() (receive)
    → FolderManager.ensure_outbox_folder() (send)
    → MetadataService.write_own_state()

Next reconciliation cycle:
  → phase_device_lists() computes union of accepted devices
  → FolderManager.set_folder_devices() applies declaratively

═══ SYNCING ═══
```

### Flow 4: Leader Removes Member

```
Leader → DELETE /sync/teams/karma-team/members/ayush.laptop
  → TeamService.remove_member()
    → team.remove_member() validates leader authorization
    → Member → REMOVED
    → record_removal() prevents re-add from stale data
    → MetadataService.write_removal_signal()
    → FolderManager.remove_device_from_team_folders()

═══ Syncthing syncs metadata folder ═══

Member's ReconciliationService.phase_metadata()
  → Reads removal signal for own member_tag
  → auto_leave(): cleanup folders, delete local team data, unpair devices
  → UI shows: "Removed from karma-team"
```

### Flow 5: Member Changes Sync Direction

```
Member → PATCH /sync/subscriptions/karma-team/project/direction { direction: "receive" }
  → ProjectService.change_direction()
    → sub.change_direction(RECEIVE)
    → FolderManager.remove_outbox_folder() (stops sending)
    → Inbox folders remain (still receiving)
    → MetadataService.write_own_state()
```

## Conflict Resolution

| Conflict | Resolution |
|---|---|
| Leader removes member, member hasn't seen it yet | Member keeps syncing until metadata arrives, then auto-leaves. Leader wins. |
| Member declines project, leader re-shares | New subscription created as OFFERED. Member can decline again. |
| Two teams share same project | Separate subscriptions per team. Device lists are union across teams. |
| Leader dissolves team while member is offline | Reconciler reads dissolution from metadata, auto-leaves. |
| Member's machine dies and comes back | Reconciler re-reads metadata, re-establishes state. |

## Metrics

| Metric | v3 | v4 |
|---|---|---|
| Router files | 7 | 4 |
| Service files | 9 | 8 (in packages) |
| DB tables | 7 | 6 |
| Reconciliation phases | 6 | 3 |
| Domain model files | 0 | 5 |
| Repository files | 0 | 5 |
| Estimated sync LOC | ~5,000 | ~3,000 |

## Future Work (Not in v4)

- **Leadership transfer** — `team.transfer_leadership(new_device_id)` method + metadata write
- **Automatic succession** — promote longest-active member after leader offline for X days
- **Network discovery (v4.1)** — LAN-based Karma user discovery via UDP broadcast or Syncthing's local discovery, layered on top of pairing codes
- **Session limit per subscription** — replace removed `sync_session_limit` at subscription level

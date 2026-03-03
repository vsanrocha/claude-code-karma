# OpenCode Integration Design

**Date:** 2026-03-03
**Status:** Approved
**Goal:** Add OpenCode session support to claude-karma with full feature parity, unified views, and source badges.

## Context

OpenCode (anomalyco/opencode, 115k+ stars) is a popular open-source AI coding agent. It stores session data in a SQLite database (`opencode.db`) via Drizzle ORM, unlike Claude Code's JSONL file-per-session approach. This design adds OpenCode as a second data source in claude-karma.

## Approach: Abstraction Layer (SessionSource Protocol)

A common `SessionSource` protocol that both Claude Code (JSONL) and OpenCode (SQLite) parsers conform to. All models gain a `source` discriminator field. Routers merge results from both sources.

## OpenCode Storage Locations

| Purpose | Path |
|---------|------|
| SQLite DB | `~/.local/share/opencode/opencode.db` (or `$XDG_DATA_HOME/opencode/opencode.db`) |
| Global config | `~/.config/opencode/opencode.json` |
| Project config | `<project>/opencode.json` + `<project>/.opencode/` |
| Auth | `~/.local/share/opencode/auth.json` |
| Logs | `~/.local/share/opencode/log/` |
| Cache | `~/.cache/opencode/` |

## OpenCode SQLite Schema (4 tables)

### SessionTable
- id, title, description, projectID, directory, agent, model
- shareURL, shareToken, revertTo
- createdAt, updatedAt

### MessageTable
- id, sessionID (FK), role (user/assistant), parentID
- model, agent, tokens, cost
- createdAt, updatedAt

### PartTable
- id, messageID (FK), type, content, metadata, status, ordering
- Types: text, tool, file, reasoning, snapshot, command, subtask

### ProjectTable
- id, path, createdAt, lastAccessed

## Data Model Mapping

| OpenCode | Claude-Karma | Notes |
|----------|--------------|-------|
| ProjectTable (path) | Project (encoded-path) | Path-encode OC paths, add `source` field |
| SessionTable | Session | Direct map. OC extras: shareURL, revertTo |
| MessageTable (role=user) | UserMessage | OC has tokens/cost on message level |
| MessageTable (role=assistant) | AssistantMessage | OC has tokens/cost on message level |
| PartTable (type=text) | TextBlock in content | Direct map |
| PartTable (type=tool) | ToolUse / ToolResult | Split: OC merges invocation+result as one part with state field |
| PartTable (type=file) | FileHistorySnapshot / file activity | Map via MIME + path metadata |
| PartTable (type=reasoning) | thinking block | Direct map to extended thinking |
| PartTable (type=snapshot) | SummaryMessage | OC compaction = our compaction detection |
| PartTable (type=subtask) | Agent (subagent) | OC subtask parts = our subagent sessions |
| PartTable (type=command) | Skill/command invocation | Map to skill tracking |

## New Files & Module Structure

### API

```
api/
├── models/
│   ├── source.py              # NEW — SessionSource protocol + SourceEnum
│   ├── opencode/              # NEW — OpenCode-specific parsers
│   │   ├── __init__.py
│   │   ├── database.py        # SQLite reader for opencode.db
│   │   ├── session.py         # SessionTable → our Session model
│   │   ├── message.py         # MessageTable+PartTable → our Message models
│   │   ├── project.py         # ProjectTable → our Project model
│   │   └── tools.py           # tool-type parts → our ToolUse model
│   ├── project.py             # MODIFIED — add source field, use SessionSource
│   ├── session.py             # MODIFIED — add source field
│   └── message.py             # MODIFIED — add source field
├── routers/
│   ├── projects.py            # MODIFIED — merge results from both sources
│   ├── sessions.py            # MODIFIED — merge results from both sources
│   ├── analytics.py           # MODIFIED — aggregate across sources
│   └── opencode.py            # NEW — OpenCode-specific endpoints (if needed)
└── utils.py                   # MODIFIED — add opencode DB path discovery
```

### Frontend

```
frontend/src/
├── lib/
│   ├── types.ts               # MODIFIED — add source field to interfaces
│   ├── api.ts                 # MODIFIED — add source filter params
│   └── components/
│       ├── SourceBadge.svelte # NEW — "Claude Code" / "OpenCode" badge
│       └── SourceFilter.svelte# NEW — filter toggle component
├── routes/
│   ├── projects/              # MODIFIED — show source badges
│   ├── sessions/              # MODIFIED — show source badges + filter
│   └── settings/              # MODIFIED — OpenCode DB path config
```

## SessionSource Protocol

```python
from typing import Protocol, Iterator, Literal

SourceType = Literal["claude_code", "opencode"]

class SessionSource(Protocol):
    source_name: SourceType

    def list_projects(self) -> list[Project]: ...
    def get_project(self, identifier: str) -> Project | None: ...
    def list_sessions(self, project: str) -> list[Session]: ...
    def get_session(self, session_id: str) -> Session | None: ...
    def iter_messages(self, session_id: str) -> Iterator[Message]: ...
    def get_tool_usage(self, session_id: str) -> list[ToolUse]: ...
    def get_file_activity(self, session_id: str) -> list[FileActivity]: ...
    def get_subagents(self, session_id: str) -> list[Agent]: ...
    def get_analytics(self, project: str) -> dict: ...
```

Both `ClaudeCodeSource` (wrapping existing parsers) and `OpenCodeSource` (new SQLite reader) implement this.

## Router Merge Pattern

```python
sources: list[SessionSource] = [claude_code_source, opencode_source]

@router.get("/projects")
async def list_projects(source: SourceType | None = None):
    all_projects = []
    for s in sources:
        if source and s.source_name != source:
            continue
        all_projects.extend(s.list_projects())
    return sorted(all_projects, key=lambda p: p.name)
```

## Frontend Source Filter

- Every list endpoint gains `?source=claude_code|opencode|all` (default `all`)
- Persisted in URL state like existing filters
- `SourceBadge.svelte` shows colored badge: blue for Claude Code, green for OpenCode
- `SourceFilter.svelte` provides toggle in list headers

## Key Design Decisions

1. **Read OpenCode's DB directly** — `sqlite3` stdlib, no SDK dependency
2. **Read-only access** — never write to opencode.db
3. **Lazy loading** — only connect when OpenCode sessions requested
4. **Graceful degradation** — if opencode.db missing, OpenCode features silently disabled
5. **Path discovery** — `$XDG_DATA_HOME/opencode/opencode.db` → `~/.local/share/opencode/opencode.db`
6. **Backward compatible** — existing models default to `source="claude_code"`

## References

- [OpenCode Docs - Config](https://opencode.ai/docs/config/)
- [OpenCode Docs - CLI](https://opencode.ai/docs/cli/)
- [OpenCode GitHub](https://github.com/anomalyco/opencode)
- [DeepWiki - Session Management](https://deepwiki.com/anomalyco/opencode/3.1-session-management)
- [OCMonitor](https://github.com/Shlomob/ocmonitor-share)

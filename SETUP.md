# Claude Karma Setup

> Step-by-step guide for setting up Claude Karma — a dashboard for monitoring and analyzing Claude Code sessions. Designed to be followed by both humans and AI agents (Claude Code, etc.).

---

## Table of Contents

- [What Gets Set Up](#what-gets-set-up)
- [Prerequisites](#prerequisites)
- [Step 1: Clone & Initialize Submodules](#step-1-clone--initialize-submodules)
- [Step 2: Start the API (Required)](#step-2-start-the-api-required)
- [Step 3: Start the Frontend (Required)](#step-3-start-the-frontend-required)
- [Step 4: Verify Core Dashboard](#step-4-verify-core-dashboard)
- [Step 5: Live Session Tracking (Optional)](#step-5-live-session-tracking-optional)
- [Step 6: Session Title Generator (Optional)](#step-6-session-title-generator-optional)
- [Step 7: Plan Approval Hook (Optional)](#step-7-plan-approval-hook-optional)
- [Hook Registration in settings.json](#hook-registration-in-settingsjson)
- [Environment Variables Reference](#environment-variables-reference)
- [Feature Matrix](#feature-matrix)
- [Directory Structure Reference](#directory-structure-reference)
- [Verification Checklist](#verification-checklist)
- [Troubleshooting](#troubleshooting)

---

## What Gets Set Up

| Component | Type | What It Does |
|-----------|------|-------------|
| **FastAPI Backend** | Required | Parses `~/.claude/` session data, serves REST API on port 8000 |
| **SvelteKit Frontend** | Required | Web dashboard on port 5173, consumes the API |
| **SQLite Index** | Auto (opt-out) | Metadata cache at `~/.claude_karma/metadata.db` for fast queries |
| **Live Session Tracker** | Optional hook | Real-time session monitoring on the dashboard |
| **Session Title Generator** | Optional hook | Human-readable titles for sessions (instead of UUIDs/slugs) |
| **Plan Approval Hook** | Optional hook | Gate Claude's plan mode exit via dashboard approval UI |

---

## Prerequisites

Run these checks before starting:

```bash
# Required
python3 --version    # 3.10+
node --version       # 18+
npm --version        # 7+

# Required (must have Claude Code sessions to display)
ls ~/.claude/projects/    # Should contain encoded project directories

# Optional (for session title generation via LLM)
claude --version     # Claude CLI, any version (for Haiku title generation)
```

| Tool | Minimum Version | Required? | Check Command |
|------|----------------|-----------|---------------|
| Python | 3.10+ | Yes | `python3 --version` |
| Node.js | 18+ | Yes | `node --version` |
| npm | 7+ | Yes | `npm --version` |
| Git | Any | Yes | `git --version` |
| Claude Code | 2.1.19+ | For subagent hooks | `claude --version` |
| Claude CLI | Any | For title generation | `which claude` |

---

## Step 1: Clone & Initialize Submodules

```bash
# Fresh clone (includes submodules)
git clone --recursive https://github.com/JayantDevkar/claude-karma.git
cd claude-karma
```

If already cloned without `--recursive`:

```bash
git submodule update --init --recursive
```

**Verify:** Three submodule directories should exist:

```bash
ls api/main.py frontend/package.json captain-hook/pyproject.toml
```

All three files must exist. If any are missing, run `git submodule update --init --recursive` again.

---

## Step 2: Start the API (Required)

```bash
cd api

# Install Python dependencies
pip install -r requirements.txt

# Start the API server
uvicorn main:app --reload --port 8000
```

**What happens on first startup:**
1. Creates `~/.claude_karma/` directory automatically
2. Creates `~/.claude_karma/metadata.db` (SQLite metadata index)
3. Starts background thread to index all JSONL sessions from `~/.claude/projects/`
4. API becomes available at `http://localhost:8000`

**Verify:**

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy", "sqlite": {"ready": true, "session_count": <number>}}
```

**To disable SQLite** (slower but functional — falls back to direct JSONL parsing):
```bash
CLAUDE_KARMA_USE_SQLITE=false uvicorn main:app --reload --port 8000
```

---

## Step 3: Start the Frontend (Required)

Open a **second terminal**:

```bash
cd frontend

# Install Node.js dependencies
npm install

# Start the dev server
npm run dev
```

The frontend starts at **http://localhost:5173** and connects to the API at `http://localhost:8000` by default.

**Custom API URL** (if API runs on a different host/port):
```bash
PUBLIC_API_URL=http://your-api-host:8000 npm run dev
```

Or create `frontend/.env`:
```
PUBLIC_API_URL=http://localhost:8000
```

---

## Step 4: Verify Core Dashboard

Open **http://localhost:5173** in your browser.

**What should work at this point (no hooks needed):**

| Feature | Route | Status |
|---------|-------|--------|
| Home page with navigation grid | `/` | Works |
| Projects list | `/projects` | Works (shows all `~/.claude/projects/`) |
| Project detail (sessions, stats) | `/projects/[name]` | Works |
| Session detail (conversation, timeline, tools) | `/projects/[name]/[session]` | Works |
| Analytics dashboard | `/analytics` | Works |
| Agent usage analytics | `/agents` | Works |
| Skill usage analytics | `/skills` | Works |
| Plans browser | `/plans` | Works |
| Settings management | `/settings` | Works |
| Archived sessions | `/archived` | Works |

**What does NOT work yet (requires hooks):**

| Feature | Missing Component |
|---------|-------------------|
| Live session monitoring (green pulsing indicators) | Needs Step 5 |
| "Recently Ended" sessions section | Needs Step 5 |
| Human-readable session titles | Needs Step 6 |
| Plan approval gate in UI | Needs Step 7 |

> **If the core dashboard works, you can stop here.** Steps 5-7 are optional enhancements. Each can be installed independently.

---

## Step 5: Live Session Tracking (Optional)

**What it adds:** Real-time session monitoring — see which Claude Code sessions are active, waiting, idle, or recently ended. The home page live sessions terminal and all "Live Sessions" sections come alive.

**Dependencies:** Python 3.10+ standard library only (no pip packages).

**Does NOT require the API to be running.** Writes directly to `~/.claude_karma/live-sessions/`.

### 5a. Install the Hook Script

Choose ONE method:

**Symlink (recommended for development):**
```bash
mkdir -p ~/.claude/hooks
ln -sf "$(cd hooks && pwd)/live_session_tracker.py" ~/.claude/hooks/live_session_tracker.py
chmod +x hooks/live_session_tracker.py
```

**Copy (for standalone installation):**
```bash
mkdir -p ~/.claude/hooks
cp hooks/live_session_tracker.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/live_session_tracker.py
```

### 5b. Register Hook Events

The live session tracker must be registered for **8 hook events** in `~/.claude/settings.json`. See the [Hook Registration](#hook-registration-in-settingsjson) section below for the complete JSON configuration.

The 8 events and what they track:

| Hook Event | Session State Set | Purpose |
|------------|------------------|---------|
| `SessionStart` | `STARTING` | New or resumed session detected |
| `UserPromptSubmit` | `LIVE` | User submitted a prompt, actively processing |
| `PostToolUse` | `LIVE` | Tool completed, session actively working |
| `Notification` | `WAITING` or `STALE` | Needs user input, or user idle 60+ seconds |
| `Stop` | `STOPPED` | Agent finished but session still open |
| `SubagentStart` | _(adds subagent)_ | Subagent spawned |
| `SubagentStop` | _(completes subagent)_ | Subagent finished |
| `SessionEnd` | `ENDED` | Session terminated |

### 5c. Verify

```bash
# Check the script is accessible
ls -la ~/.claude/hooks/live_session_tracker.py

# Test it manually
echo '{"hook_event_name":"SessionStart","session_id":"test-123","cwd":"/tmp","transcript_path":"/tmp/test.jsonl"}' \
  | python3 ~/.claude/hooks/live_session_tracker.py

# Check state file was written
ls ~/.claude_karma/live-sessions/
```

> **Note:** `SubagentStart` and `SubagentStop` events require Claude Code 2.1.19+. On older versions, subagent tracking is unavailable but everything else works.

---

## Step 6: Session Title Generator (Optional)

**What it adds:** When a Claude Code session ends, this hook generates a human-readable title (e.g., "Refactor auth middleware" instead of "serene-meandering-scott"). Titles appear throughout the dashboard on session cards.

**Dependencies:** Python 3.10+ standard library. Optionally, the `claude` CLI for Haiku-powered title generation.

**Requires the API to be running** (POSTs the title to the API).

**Title generation priority:**
1. Most recent git commit message during the session (free, no LLM)
2. Claude Haiku via `claude -p` CLI (requires Claude CLI installed)
3. Truncated initial user prompt (fallback)

### 6a. Install the Hook Script

**Symlink:**
```bash
ln -sf "$(cd hooks && pwd)/session_title_generator.py" ~/.claude/hooks/session_title_generator.py
chmod +x hooks/session_title_generator.py
```

**Copy:**
```bash
cp hooks/session_title_generator.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/session_title_generator.py
```

### 6b. Register Hook Event

This hook registers for `SessionEnd` only. See the [Hook Registration](#hook-registration-in-settingsjson) section below.

### 6c. Verify

```bash
# Check the API is running (required for this hook)
curl http://localhost:8000/health

# After ending a Claude Code session, check for a title:
curl http://localhost:8000/projects | python3 -c "import sys,json; [print(s.get('title','NO TITLE'), s['slug']) for p in json.load(sys.stdin)['projects'] for s in p.get('recent_sessions',[])]" 2>/dev/null
```

### 6d. Backfill Existing Session Titles

To generate titles for sessions that existed before installing this hook:

```bash
cd api
python3 scripts/backfill_titles.py
```

This requires the API to be running and `claude` CLI to be installed.

---

## Step 7: Plan Approval Hook (Optional)

**What it adds:** When Claude enters plan mode and tries to exit (start implementing), this hook checks the plan's approval status in the Claude Karma dashboard. If the plan hasn't been approved in the UI, Claude is blocked and shown feedback.

**Dependencies:** Python 3.10+ standard library only.

**Requires the API to be running** (queries plan approval status).

### 7a. Install the Hook Script

**Symlink:**
```bash
ln -sf "$(cd hooks && pwd)/plan_approval.py" ~/.claude/hooks/plan_approval.py
chmod +x hooks/plan_approval.py
```

**Copy:**
```bash
cp hooks/plan_approval.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/plan_approval.py
```

### 7b. Register Hook Event

This hook registers for `PermissionRequest` with matcher `ExitPlanMode`. See the [Hook Registration](#hook-registration-in-settingsjson) section below.

### 7c. How It Works

| Plan Status in Dashboard | Hook Response | What Claude Sees |
|--------------------------|---------------|-----------------|
| `approved` | Allow | Claude proceeds with implementation |
| `changes_requested` | Deny + feedback | Claude sees reviewer annotations |
| `pending` | Deny | Claude told to wait for review |
| API unreachable | Deny | Claude told to start the API |

### 7d. Verify

```bash
# Test the hook script manually
echo '{"tool_name":"ExitPlanMode","tool_input":{}}' | python3 ~/.claude/hooks/plan_approval.py

# Should output JSON with a decision (deny if no plan found)
```

---

## Hook Registration in settings.json

Add the following to `~/.claude/settings.json`. This is the **complete configuration** for all three hooks. Remove sections you don't want.

> **Important:** If you already have a `"hooks"` key in your settings.json, merge the entries below into it rather than overwriting.

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/live_session_tracker.py",
            "timeout": 5000
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/live_session_tracker.py",
            "timeout": 5000
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/live_session_tracker.py",
            "timeout": 5000
          }
        ]
      }
    ],
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/live_session_tracker.py",
            "timeout": 5000
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/live_session_tracker.py",
            "timeout": 5000
          }
        ]
      }
    ],
    "SubagentStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/live_session_tracker.py",
            "timeout": 5000
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/live_session_tracker.py",
            "timeout": 5000
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/live_session_tracker.py",
            "timeout": 5000
          }
        ]
      },
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/session_title_generator.py",
            "timeout": 15000
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "matcher": "ExitPlanMode",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/plan_approval.py",
            "timeout": 30000
          }
        ]
      }
    ]
  }
}
```

### Minimal Configuration (Live Tracking Only)

If you only want live session tracking (Step 5) without title generation or plan approval, use only the first entry in `SessionEnd` (omit the `session_title_generator.py` entry) and omit the `PermissionRequest` block entirely.

### Removing a Hook

To opt out of a specific hook after installation:

| Hook to Remove | Action |
|---------------|--------|
| Live session tracker | Remove all `live_session_tracker.py` entries from settings.json |
| Title generator | Remove the `session_title_generator.py` entry from `SessionEnd` |
| Plan approval | Remove the entire `PermissionRequest` block |

Then optionally clean up the script:
```bash
rm ~/.claude/hooks/<script_name>.py
```

---

## Environment Variables Reference

### API (Python/FastAPI)

All API environment variables use the `CLAUDE_KARMA_` prefix. Set via shell environment, `.env` file in the `api/` directory, or export.

**Core:**

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_KARMA_CLAUDE_BASE` | `~/.claude` | Base directory for Claude Code data |
| `CLAUDE_KARMA_USE_SQLITE` | `true` | Enable SQLite metadata index. Set `false` to use JSONL-only mode |
| `CLAUDE_KARMA_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

**Cache Durations (seconds):**

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_KARMA_CACHE_PROJECTS_LIST` | `30` | Projects list |
| `CLAUDE_KARMA_CACHE_PROJECT_DETAIL` | `60` | Project details |
| `CLAUDE_KARMA_CACHE_SESSION_DETAIL` | `60` | Session details |
| `CLAUDE_KARMA_CACHE_LIVE_SESSIONS` | `5` | Live sessions (short for real-time) |
| `CLAUDE_KARMA_CACHE_ANALYTICS` | `120` | Analytics data |
| `CLAUDE_KARMA_CACHE_AGENT_USAGE` | `300` | Agent usage analytics |
| `CLAUDE_KARMA_CACHE_FILE_ACTIVITY` | `300` | File activity |

**File Size Limits:**

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_KARMA_MAX_AGENT_SIZE` | `100000` (100KB) | Max agent markdown file size |
| `CLAUDE_KARMA_MAX_SKILL_SIZE` | `1000000` (1MB) | Max skill file size |

**In-Memory Cache:**

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_KARMA_CACHE_MAX_SIZE` | `1000` | Max entries in bounded caches |
| `CLAUDE_KARMA_CACHE_TTL` | `3600` | TTL for bounded cache entries (seconds) |

### Frontend (SvelteKit)

| Variable | Default | Description |
|----------|---------|-------------|
| `PUBLIC_API_URL` | `http://localhost:8000` | FastAPI backend URL |

### Hook Scripts

| Variable | Default | Used By | Description |
|----------|---------|---------|-------------|
| `CLAUDE_KARMA_API` | `http://localhost:8000` | Title generator | API base URL for posting titles |

### Production Deployment

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `3000` | Frontend production server port |
| `HOST` | `0.0.0.0` | Frontend production server host |
| `ORIGIN` | _(required)_ | Full origin URL for CSRF protection |
| `CLAUDE_KARMA_CORS_ORIGINS` | `["http://localhost:5173"]` | CORS allowed origins (JSON array) |

---

## Feature Matrix

Quick reference for what each setup step enables:

| Dashboard Feature | Core (Steps 1-3) | + Live Tracker (Step 5) | + Title Gen (Step 6) | + Plan Approval (Step 7) |
|-------------------|:-:|:-:|:-:|:-:|
| Browse projects | Yes | | | |
| View sessions & conversations | Yes | | | |
| Session timeline & file activity | Yes | | | |
| Tool usage analytics | Yes | | | |
| Agent usage analytics | Yes | | | |
| Skill usage analytics | Yes | | | |
| Plans browser | Yes | | | |
| Global analytics dashboard | Yes | | | |
| Settings management | Yes | | | |
| Archived sessions | Yes | | | |
| Command palette (Ctrl+K) | Yes | | | |
| **Live session indicators** | | Yes | | |
| **Recently ended sessions** | | Yes | | |
| **Subagent tracking (live)** | | Yes | | |
| **Session state (LIVE/WAITING/IDLE)** | | Yes | | |
| **Human-readable session titles** | | | Yes | |
| **Git commit-based titles** | | | Yes | |
| **Plan approval/rejection in UI** | | | | Yes |
| **Plan annotation feedback** | | | | Yes |

### Choosing Your Setup Level

| Profile | Steps | What You Get |
|---------|-------|-------------|
| **Minimal** | 1-3 | Full historical dashboard. All past sessions viewable. No real-time features. |
| **Recommended** | 1-5 | Historical + live monitoring. See sessions as they happen. |
| **Full** | 1-7 | Everything. Live monitoring + smart titles + plan approval workflow. |

---

## Directory Structure Reference

### What Claude Karma Creates

```
~/.claude_karma/                    # Claude Karma data root (auto-created)
  metadata.db                       # SQLite metadata index (auto-created by API)
  metadata.db-wal                   # SQLite WAL journal (auto-managed)
  metadata.db-shm                   # SQLite shared memory (auto-managed)
  live-sessions/                    # Live session state files (created by hook)
    {slug}.json                     # Per-session state (one per active session)
  cache/
    titles/
      {encoded_project_name}.json   # Per-project title cache (created by API)
```

### What Claude Karma Reads (owned by Claude Code)

```
~/.claude/                          # Claude Code's data root
  projects/                         # Encoded project directories
    {encoded-path}/                 # One per project (e.g., -Users-me-repo)
      {uuid}.jsonl                  # Session transcripts
      {uuid}/
        subagents/                  # Subagent session files
          agent-{id}.jsonl
        tool-results/               # Tool output files
          toolu_{id}.txt
  agents/                           # Agent markdown definitions
  skills/                           # Skill definitions
  commands/                         # Command definitions
  todos/                            # Todo JSON files
    {uuid}-*.json
  debug/                            # Debug logs
    {uuid}.txt
  plans/                            # Plan markdown files
    {slug}.md
  hooks/                            # Hook scripts (installed in Steps 5-7)
    live_session_tracker.py
    session_title_generator.py
    plan_approval.py
  settings.json                     # Claude Code settings (hooks registered here)
```

### Repository Structure

```
claude-karma/
  api/                              # FastAPI backend (Python) - git submodule
  frontend/                         # SvelteKit frontend (Svelte 5) - git submodule
  captain-hook/                     # Hook models library (Python) - git submodule
  hooks/                            # Hook scripts (source of truth)
    live_session_tracker.py         # Real-time session tracking
    session_title_generator.py      # Session title generation
    plan_approval.py                # Plan approval gate
  SETUP.md                          # This file
  CLAUDE.md                         # Agent guidance
  FEATURES.md                       # Feature documentation
  navigation.md                     # Navigation/routing guide
```

---

## Verification Checklist

Run through this after setup to confirm everything works.

### Core (Required)

- [ ] `curl http://localhost:8000/health` returns `{"status": "healthy", ...}`
- [ ] `curl http://localhost:8000/projects` returns a JSON list of projects
- [ ] Browser at `http://localhost:5173` shows the home page with navigation cards
- [ ] Clicking "Projects" shows your Claude Code projects
- [ ] Clicking a project shows sessions with stats
- [ ] Clicking a session shows the conversation

### Live Session Tracking (Step 5)

- [ ] `ls ~/.claude/hooks/live_session_tracker.py` — script exists
- [ ] Start a new Claude Code session, then check: `ls ~/.claude_karma/live-sessions/` — a `.json` file appears
- [ ] Dashboard home page shows "Live Sessions" section with active sessions
- [ ] Session shows live status badge (green = LIVE, blue = WAITING)

### Title Generation (Step 6)

- [ ] `ls ~/.claude/hooks/session_title_generator.py` — script exists
- [ ] After ending a Claude Code session, the session card shows a descriptive title
- [ ] `curl http://localhost:8000/health` returns healthy (API must be running for this hook)

### Plan Approval (Step 7)

- [ ] `ls ~/.claude/hooks/plan_approval.py` — script exists
- [ ] When Claude exits plan mode, the hook queries the API for approval status
- [ ] Plans page at `/plans` shows plan cards with approval status

---

## Troubleshooting

### API Won't Start

```bash
# Check Python version (must be 3.10+)
python3 --version

# Reinstall dependencies
cd api && pip install -r requirements.txt

# Check if port 8000 is already in use
lsof -ti:8000
# Kill if needed: lsof -ti:8000 | xargs kill -9
```

### Frontend Won't Start

```bash
# Check Node version (must be 18+)
node --version

# Clear cache and reinstall
cd frontend && rm -rf node_modules && npm install

# Check if port 5173 is already in use
lsof -ti:5173
```

### Empty Projects List

```bash
# Verify Claude Code has been used on this machine
ls ~/.claude/projects/

# Check sessions exist within a project
ls ~/.claude/projects/-Users-*/
```

If `~/.claude/projects/` is empty, you need to use Claude Code at least once first.

### CORS Errors in Browser Console

The API allows requests from `http://localhost:5173` by default. If the frontend runs on a different port:

```bash
# Override CORS origins
CLAUDE_KARMA_CORS_ORIGINS='["http://localhost:5173","http://localhost:3000"]' \
  uvicorn main:app --reload --port 8000
```

### Live Sessions Not Appearing

```bash
# 1. Check hook script exists and is executable
ls -la ~/.claude/hooks/live_session_tracker.py

# 2. Check hooks are registered in settings
python3 -c "import json; d=json.load(open('$HOME/.claude/settings.json')); print('SessionStart' in d.get('hooks',{}))"

# 3. Check state files are being written
ls ~/.claude_karma/live-sessions/

# 4. Test the hook manually
echo '{"hook_event_name":"SessionStart","session_id":"test","cwd":"/tmp","transcript_path":"/tmp/t.jsonl"}' \
  | python3 ~/.claude/hooks/live_session_tracker.py

# 5. Watch for changes in real-time
watch -n1 'ls -la ~/.claude_karma/live-sessions/'
```

### Session Titles Not Generating

```bash
# Check the title generator script exists
ls -la ~/.claude/hooks/session_title_generator.py

# Check API is running (required)
curl http://localhost:8000/health

# Check Claude CLI is available (optional, for Haiku titles)
which claude

# Run backfill for existing sessions
cd api && python3 scripts/backfill_titles.py
```

### SQLite Database Issues

```bash
# Check database exists
ls -la ~/.claude_karma/metadata.db

# Force reindex (API must be running)
curl -X POST http://localhost:8000/admin/reindex

# Rebuild full-text search index
curl -X POST http://localhost:8000/admin/rebuild-fts

# Nuclear option: delete and restart (auto-recreates on next API start)
rm ~/.claude_karma/metadata.db*
# Then restart the API
```

### Subagent Tracking Not Working

```bash
# Requires Claude Code 2.1.19+
claude --version

# Check SubagentStart/SubagentStop hooks are registered
python3 -c "
import json
with open('$HOME/.claude/settings.json') as f:
    hooks = json.load(f).get('hooks', {})
print('SubagentStart:', 'SubagentStart' in hooks)
print('SubagentStop:', 'SubagentStop' in hooks)
"
```

---

## Updating

### Update All Submodules to Latest

```bash
git submodule update --remote
```

### Update a Specific Submodule

```bash
git submodule update --remote api       # API only
git submodule update --remote frontend  # Frontend only
```

### After Updating

```bash
# Reinstall API deps (if requirements changed)
cd api && pip install -r requirements.txt

# Reinstall frontend deps (if package.json changed)
cd frontend && npm install

# Reindex SQLite (if schema changed)
curl -X POST http://localhost:8000/admin/reindex
```

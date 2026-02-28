# Claude Code Karma API

FastAPI backend for monitoring and analyzing Claude Code sessions. Parses Claude Code's local storage (`~/.claude/`) and exposes REST endpoints for the SvelteKit frontend dashboard.

## Features

- **📊 Session Analytics** — Token usage, cache hit rates, duration tracking
- **🔧 Tool Usage Analysis** — Track which tools are used and how often
- **💬 Message Parsing** — Access user messages, assistant responses, and content blocks
- **🤖 Subagent Support** — Parse spawned subagents and their conversations
- **📝 Todo Tracking** — Access session task lists and their statuses
- **📁 File Operations** — Discover which files were read, written, or deleted

## Installation

Requires Python 3.9+ and Pydantic v2:

```bash
# From the monorepo root
git clone https://github.com/JayantDevkar/claude-code-karma.git
cd claude-code-karma/api
pip install -e ".[dev]"
pip install -r requirements.txt
```

## Quick Start

```python
from models import Project, Session

# Load a project by its original path
project = Project.from_path("/Users/me/my-project")

# Get the latest session
sessions = project.list_sessions()
session = sessions[-1] if sessions else None

if session:
    print(f"Session: {session.uuid[:12]}...")
    print(f"Messages: {session.message_count}")
    print(f"Duration: {session.duration_seconds}s")
    
    # Token usage
    usage = session.get_usage_summary()
    print(f"Tokens: {usage.total_tokens:,}")
    print(f"Cache hit rate: {usage.cache_hit_rate:.1%}")
    
    # Top tools used
    for tool, count in session.get_tools_used().most_common(5):
        print(f"  {tool}: {count}x")
```

## Example: Session Story Generator

The included `session_story.py` script generates a narrative activity report for any session:

```bash
# Generate story for the last session
python session_story.py /path/to/your/project

# Generate story for a specific session
python session_story.py /path/to/project --session-uuid abc123...

# Output as JSON
python session_story.py /path/to/project --json
```

Sample output:

```
======================================================================
📖 SESSION ACTIVITY STORY
======================================================================

🔹 SESSION OVERVIEW
----------------------------------------
   Session ID: a1b2c3d4e5f6...
   Started:    January 09, 2026 at 02:30 PM
   Duration:   45m 12s
   Messages:   28

🔹 TOOLS USED
----------------------------------------
   Total tool calls: 87
   
   Read                  32x  ████████████████████+
   StrReplace            18x  ██████████████████
   Shell                 12x  ████████████
   ...
```

## Model Hierarchy

```
Project
├── Session (UUID.jsonl)
│   ├── Message
│   │   ├── UserMessage
│   │   ├── AssistantMessage
│   │   │   └── ContentBlock (TextBlock, ThinkingBlock, ToolUseBlock)
│   │   └── FileHistorySnapshot
│   ├── Agent (subagents/)
│   ├── ToolResult (tool-results/)
│   └── TodoItem
└── Agent (standalone agents)
```

## API Reference

For detailed API documentation, see the [Models README](models/README.md).

### Key Classes

| Class | Description |
|-------|-------------|
| `Project` | Entry point — represents a Claude Code project directory |
| `Session` | A conversation session with messages and analytics |
| `Agent` | Standalone agents or subagents spawned during a session |
| `UserMessage` | User input messages |
| `AssistantMessage` | Claude's responses with content blocks |
| `TokenUsage` | Token statistics with aggregation support |
| `ToolResult` | Large tool outputs stored on disk |
| `TodoItem` | Session task list items |

## File Structure Reference

Claude Code stores data in `~/.claude/`:

```
~/.claude/
├── projects/{encoded-path}/
│   ├── {session-uuid}.jsonl          # Main session
│   ├── {session-uuid}/
│   │   ├── tool-results/toolu_*.txt  # Large tool outputs
│   │   └── subagents/agent-*.jsonl   # Subagent sessions
│   └── agent-{id}.jsonl              # Standalone agents
├── debug/{session-uuid}.txt          # Debug logs
├── file-history/{session-uuid}/      # File backups
└── todos/{session-uuid}-*.json       # Todo lists
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=models

# Lint
ruff check .
ruff format .
```

## License

Apache-2.0 License — see [LICENSE](LICENSE) for details.

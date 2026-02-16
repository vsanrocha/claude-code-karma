# Navigation Guide

> How users move through Claude Karma, starting from the home screen.

---

## Home Screen (`/`)

The home screen is the central hub. It offers two navigation mechanisms:

1. **Navigation Grid** — 9 cards linking to top-level sections
2. **Live Sessions Panel** — quick access to active sessions

| Card | Route | Purpose |
|------|-------|---------|
| Projects | `/projects` | Browse all projects |
| Sessions | `/sessions` | View all sessions across projects |
| Analytics | `/analytics` | Global analytics dashboard |
| Plans | `/plans` | Browse work plans |
| Skills | `/skills` | Global skill/tool usage |
| Agents | `/agents` | Global agent usage |
| Plugins | `/plugins` | Plugin management |
| Settings | `/settings` | User configuration |
| Archived | `/archived` | Archived sessions |

---

## Persistent Navigation Bar

Present on **all pages except home**. Sticky top header with:

- **Desktop**: Inline links — Projects, Sessions, Plans, Agents, Skills, Plugins, Analytics, Archived
- **Mobile**: Hamburger menu with same links
- **Settings**: Gear icon (top-right, always visible)
- **Brand**: "Claude Karma" links back to `/`

---

## Section Flows

### Projects

```
/projects                              List all projects (search, sort, filter)
  └── /projects/[project_slug]         Project detail (tabbed via ?tab= param)
        ├── Overview (default)         Stats, live sessions, recent sessions
        │     └── [session card]  ───► /projects/[project_slug]/[session_slug]
        ├── Agents tab (?tab=agents)   Agent usage for this project (inline)
        ├── Skills tab (?tab=skills)   Skill usage for this project (inline)
        ├── Analytics tab (?tab=analytics)  Inline charts
        └── Archived tab (?tab=archived)    Archived sessions for this project
```

### Sessions

```
/sessions                              All sessions across projects (token search, filter, paginate)
  └── [session card]              ───► /projects/[project_slug]/[session_slug]
```

**Session detail** (`/projects/[project_slug]/[session_slug]`) shows:
- Conversation messages, timeline, file activity, tools, tasks, plan details
- Subagent links → subagent detail page

**Subagent detail** (`/projects/[project_slug]/[session_slug]/agents/[agent_id]`) shows:
- Individual subagent conversation and activity

### Agents

```
/agents                                All agents (search, category filter)
  └── [agent card]                ───► /agents/[name]
```

### Skills

```
/skills                                Two tabs:
  ├── Usage Analytics (default)        Skill stats, category filter
  │     └── [skill]               ───► /skills/[skill_name]
  └── Browse Files                     File explorer
        └── [path]                ───► /skills/[...path]
```

### Plans

```
/plans                                 All plans (filter by project, branch)
  └── [plan card]                 ───► /plans/[slug]
```

### Analytics

```
/analytics                             Time-filtered dashboard (no sub-routes)
```

### Plugins

```
/plugins                               Plugin list
  └── [plugin]                    ───► /plugins/[plugin_name]
        └── Skills                ───► /plugins/[plugin_id]/skills
              └── [skill file]    ───► /plugins/[plugin_id]/skills/[...path]
```

### Settings

```
/settings                              Sections: General, Permissions, Plugins, Advanced
```

### Archived

```
/archived                              Archived sessions list (client-side search/filter)
```

---

## Cross-Cutting Patterns

### Breadcrumbs

Interior pages show a breadcrumb trail:

```
Dashboard > Projects > [Project Name] > Agents
Dashboard > Plans > [Plan Name]
Dashboard > Plugins > [Plugin Name] > Skills > [Skill Path]
Dashboard > Settings
```

### URL State

Filters persist via URL search params for shareability and back-button support:

| Param | Used On | Example |
|-------|---------|---------|
| `search` | Projects, Sessions, Agents, Archived | `?search=karma` |
| `tab` | Project detail | `?tab=agents` |
| `filter` | Analytics | `?filter=7days` |
| `project` | Sessions, Plans | `?project=project_slug` |
| `branch` | Plans | `?branch=main` |
| `page`, `per_page` | Sessions, Plans, Agents | `?page=2&per_page=24` |
| `path` | Skills | `?path=hooks/` |

### Token Search (Sessions)

Sessions page uses a token-based search input with keyboard navigation (arrow keys between tokens, backspace to delete).

### Command Palette

Global keyboard shortcut opens a search overlay for quick navigation to any page or entity.

### Skeleton Loaders

Each section has a dedicated skeleton displayed during navigation transitions (e.g., `ProjectsPageSkeleton`, `SessionDetailSkeleton`).

---

## Key Components

| Component | File | Role |
|-----------|------|------|
| Header | `src/lib/components/Header.svelte` | Top nav bar |
| NavigationCard | `src/lib/components/NavigationCard.svelte` | Home grid cards |
| PageHeader | `src/lib/components/layout/PageHeader.svelte` | Breadcrumbs + title |
| CommandPalette | `src/lib/components/command-palette/CommandPalette.svelte` | Global search |
| CommandFooter | `src/lib/components/CommandFooter.svelte` | Keyboard shortcuts help |

---

## Full Journey Map

```
/ (Home)
├─► /projects ─► /projects/[slug] ─┬─► Overview ─► /projects/[slug]/[session]
│                                   │                  └─► /projects/[slug]/[session]/agents/[id]
│                                   ├─► Agents (?tab=agents, inline)
│                                   ├─► Skills (?tab=skills, inline)
│                                   ├─► Analytics (?tab=analytics, inline)
│                                   └─► Archived (?tab=archived, inline)
├─► /sessions ─► /projects/[slug]/[session]
├─► /agents ──► /agents/[name]
├─► /skills ──┬► /skills/[name]
│             └► /skills/[...path]
├─► /plans ───► /plans/[slug]
├─► /plugins ─► /plugins/[name] ─► /plugins/[id]/skills ─► /plugins/[id]/skills/[...path]
├─► /analytics
├─► /archived
└─► /settings
```

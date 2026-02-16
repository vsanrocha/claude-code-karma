# Hooks Page - UI Design Specification

> **Date:** 2026-02-16
> **Matches patterns from:** Agents page, Skills page

## Design Philosophy

Hooks are not like agents or skills. Users don't "use" hooks — hooks happen _to_ them. The UI value is **awareness and control**, not analytics:

- "What's intercepting my tool calls?"
- "Why does my session start feel slow?" (30+ hooks fire on SessionStart)
- "Which plugin added that `<system-reminder>` I keep seeing?"
- "How do my hooks layer with plugin hooks?"

---

## Color System

Hooks get an **amber palette** — they're interceptors, gatekeepers, warning tape. This differentiates from purple (agents) and blue (skills).

```css
/* Hero gradient */
--hook-amber: oklch(0.75 0.15 75);
--hook-amber-subtle: oklch(0.75 0.15 75 / 0.1);

/* Blocking hooks get red-amber accent */
--hook-blocking: oklch(0.7 0.2 30);
--hook-blocking-subtle: oklch(0.7 0.2 30 / 0.1);

/* Non-blocking hooks */
--hook-readonly: var(--text-muted);

/* Source colors */
/* "Your Hooks" → dedicated warm yellow: oklch(0.8 0.12 85) */
/* Plugin hooks → use existing getPluginColorVars(pluginName) */
```

---

## Navigation Integration

### Home Grid

Add 10th card (or restructure to accommodate):

| Card | Route | Icon | Color |
|------|-------|------|-------|
| Hooks | `/hooks` | `Webhook` (lucide) | `--nav-amber` |

### Persistent Nav Bar

Insert between Skills and Plugins:

```
Projects, Sessions, Plans, Agents, Skills, [Hooks], Plugins, Analytics, Archived
```

### Breadcrumbs

```
Dashboard > Hooks
Dashboard > Hooks > PreToolUse
Dashboard > Hooks > Sources > claude-karma
```

### Command Palette

Add hooks page and hook event types to search index.

---

## Page: `/hooks` (Main Overview)

### Layout

```
+====================================================================+
| PageHeader                                                          |
|   icon: Webhook (lucide)                                            |
|   iconColor: --nav-amber                                            |
|   title: "Hooks"                                                    |
|   breadcrumbs: Dashboard > Hooks                                    |
|   subtitle: "Hook scripts intercepting your Claude Code sessions"   |
+====================================================================+
|                                                                      |
| Hero Stats (amber gradient background + blur decorations)            |
| +------------------+---------------------+-------------------+       |
| | 4 Hook Sources   | 38 Registrations    | 8 Can Block       |       |
| | (Webhook icon)   | (Link icon)         | (ShieldAlert icon)|       |
| +------------------+---------------------+-------------------+       |
|                                                                      |
+----------------------------------------------------------------------+
| View Toggle                                                          |
| [Event Timeline] [By Source]                                         |
+----------------------------------------------------------------------+
|                                                                      |
| (Content area — depends on selected view)                            |
|                                                                      |
+----------------------------------------------------------------------+
```

### Hero Stats

Uses `StatsGrid` component with `columns={3}`:

| Stat | Icon | Color | Value | Label |
|------|------|-------|-------|-------|
| Hook Sources | `Webhook` | amber | `4` | "Active sources (global + plugins)" |
| Registrations | `Link` | amber | `38` | "Total hook-to-event bindings" |
| Can Block | `ShieldAlert` | red-amber | `8` | "Hooks that can deny/block actions" |

---

### View 1: Event Timeline (Default)

The signature view. A vertical timeline showing hook events in **session lifecycle order**, grouped by phase.

#### Phase Groups

| Phase | Events | Visual Separator |
|-------|--------|-----------------|
| Session Lifecycle | SessionStart | Phase header with muted label |
| User Input | UserPromptSubmit | |
| Tool Lifecycle | PreToolUse, PostToolUse | |
| Agent Lifecycle | SubagentStart, SubagentStop, Stop | |
| Context & Permissions | PreCompact, PermissionRequest, Notification | |
| Session End | SessionEnd | |

#### Event Node Design

Each event type is a **collapsible node** on the timeline:

```
 │
 ├── ● SessionStart ─────────────────────── 4 hooks
 │   │
 │   │  Expanded content (CollapsibleGroup pattern):
 │   │
 │   │  ┌─────────────────────────────────────────────────┐
 │   │  │ 🟡 claude-karma                                  │
 │   │  │    live_session_tracker.py          Python  5s   │
 │   │  │    matcher: *                                     │
 │   │  ├─────────────────────────────────────────────────┤
 │   │  │ 🔵 oh-my-claudecode                              │
 │   │  │    session-start.mjs               Node.js  5ms │
 │   │  │    matcher: *                                     │
 │   │  ├─────────────────────────────────────────────────┤
 │   │  │ 🔵 oh-my-claudecode                              │
 │   │  │    setup-init.mjs                  Node.js  30ms│
 │   │  │    matcher: init                                  │
 │   │  ├─────────────────────────────────────────────────┤
 │   │  │ 🟣 everything-claude-code                        │
 │   │  │    session-start.js                Node.js  --  │
 │   │  │    matcher: *                                     │
 │   │  └─────────────────────────────────────────────────┘
 │
 ├── ● UserPromptSubmit  ⚡ CAN BLOCK ──── 3 hooks
 │   │  ...
```

#### Event Node Header

```
┌─────────────────────────────────────────────────────────┐
│  ●  SessionStart                         4 hooks        │
│     └ Session Lifecycle                                  │
└─────────────────────────────────────────────────────────┘

Blocking events get a red-amber accent:

┌─────────────────────────────────────────────────────────┐
│  ●  PreToolUse    ⚡ CAN BLOCK           5 hooks        │
│     └ Tool Lifecycle                                     │
└─────────────────────────────────────────────────────────┘
```

**Elements:**
- Colored timeline dot (amber, or red-amber for blocking)
- Event type name (clickable → `/hooks/[event_type]`)
- "CAN BLOCK" badge (red-amber `Badge` variant) for blocking events
- Registration count (right-aligned)
- Phase label (muted, below name)

#### Hook Registration Entry (Within Event)

```
┌───────────────────────────────────────────────────────────┐
│ 🟡 │ claude-karma                                         │
│    │ live_session_tracker.py              Python │ 5000ms │
│    │ matcher: *                                           │
└───────────────────────────────────────────────────────────┘
```

**Elements:**
- Source color dot (left, uses `getPluginColorVars` or dedicated color for "Your Hooks")
- Source name (bold)
- Script filename
- Language badge: `Python` / `Node.js` / `Shell` (small, muted)
- Timeout badge (right-aligned)
- Matcher value (if not `*`, show with emphasis)
- Left border accent (4px, source color)

---

### View 2: By Source

Uses `CollapsibleGroup` pattern (identical to agents/skills group layout).

#### Group Structure

```
┌─ CollapsibleGroup ──────────────────────────────────────┐
│  🟡 Your Hooks (Global)                                  │
│     10 registrations · 3 scripts · 7 event types         │
│                                                          │
│  ┌─ HookScriptCard ────────────────────────────────────┐ │
│  │ 📄 live_session_tracker.py                           │ │
│  │                                                      │ │
│  │ Events: [SessionStart] [PostToolUse] [Notification]  │ │
│  │         [Stop] [SessionEnd] [UserPromptSubmit]       │ │
│  │         [SubagentStart] [SubagentStop]               │ │
│  │                                                      │ │
│  │ Python · timeout: 5000ms · symlink → hooks/...       │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ HookScriptCard ────────────────────────────────────┐ │
│  │ 📄 session_title_generator.py                        │ │
│  │                                                      │ │
│  │ Events: [SessionEnd]                                 │ │
│  │                                                      │ │
│  │ Python · timeout: 15000ms · symlink → hooks/...      │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─ HookScriptCard ────────────────────────────────────┐ │
│  │ 📄 plan_approval.py                                  │ │
│  │                                                      │ │
│  │ Events: [PermissionRequest]                          │ │
│  │ Matcher: ExitPlanMode                                │ │
│  │                                                      │ │
│  │ Python · timeout: 30000ms · symlink → hooks/...      │ │
│  └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘

┌─ CollapsibleGroup ──────────────────────────────────────┐
│  🔵 oh-my-claudecode (Plugin)                            │
│     13 registrations · 10 scripts · 10 event types       │
│                                                          │
│  (script cards...)                                       │
└──────────────────────────────────────────────────────────┘
```

#### CollapsibleGroup Header

Uses same pattern as agents/skills:

```svelte
<CollapsibleGroup
  title="oh-my-claudecode"
  open={expandedGroups.has('omc')}
  onOpenChange={() => toggleGroup('omc')}
  accentColor={getPluginColorVars('oh-my-claudecode').color}
>
  {#snippet icon()}
    <Package size={16} />  <!-- or Webhook for "Your Hooks" -->
  {/snippet}
  {#snippet metadata()}
    <span>13 registrations · 10 scripts</span>
  {/snippet}
</CollapsibleGroup>
```

#### HookScriptCard Design

```
┌──────────────────────────────────────────────────────────┐
│ ┌──────┐                                                  │
│ │  📄  │  live_session_tracker.py           [Python]      │
│ │      │                                                  │
│ └──────┘  Events:                                         │
│           [SessionStart] [PostToolUse] [Stop] [SessionEnd]│
│           [UserPromptSubmit] [SubagentStart] [SubagentStop│
│           [Notification]                                  │
│                                                          │
│           timeout: 5000ms                                │
│           symlink → ~/Documents/GitHub/claude-karma/hooks/│
│                                                  4px left │
│                                                  border   │
└──────────────────────────────────────────────────────────┘
```

**Elements:**
- File icon with colored background (source color)
- Script filename (bold, clickable if source detail page exists)
- Language badge: `Python` / `Node.js` / `Shell`
- Event type pills (small colored badges, each clickable → `/hooks/[event_type]`)
- Timeout value
- Symlink target (if applicable, muted text)
- Matcher (if specific, not `*`)
- Left border accent (4px, source color)

**Event type pill colors:**
- Blocking events: red-amber background
- Non-blocking events: gray/muted background

---

## Page: `/hooks/[event_type]` (Event Detail)

### Layout

```
+====================================================================+
| PageHeader                                                          |
|   title: "PreToolUse"                                               |
|   breadcrumbs: Dashboard > Hooks > PreToolUse                       |
|   badges: [⚡ Can Block] [Tool Lifecycle]                           |
+====================================================================+
|                                                                      |
| Description Card                                                     |
| "Fires before every tool execution. Receives the tool name and      |
|  input. Can inspect, modify context, or block the tool call."        |
|                                                                      |
+----------------------------------------------------------------------+
|                                                                      |
| Active Registrations (5)                          [Expand All]       |
|                                                                      |
| ┌─ Registration Card ──────────────────────────────────────────────┐ |
| │ 🔵 oh-my-claudecode                                              │ |
| │    pre-tool-enforcer.mjs · Node.js · 3ms                         │ |
| │    matcher: * (all tools)                                        │ |
| │    "Injects Sisyphus task reminders and enforces delegation"     │ |
| │                                                                  │ |
| │    Command: node ${CLAUDE_PLUGIN_ROOT}/scripts/pre-tool-...      │ |
| └──────────────────────────────────────────────────────────────────┘ |
|                                                                      |
| ┌─ Registration Card ──────────────────────────────────────────────┐ |
| │ 🟣 everything-claude-code                                        │ |
| │    (inline) · 3ms                                                │ |
| │    matcher: Bash && "npm run dev|yarn dev|pnpm dev"              │ |
| │    "Block dev servers outside tmux"                              │ |
| └──────────────────────────────────────────────────────────────────┘ |
|                                                                      |
| ... more registration cards ...                                      |
|                                                                      |
+----------------------------------------------------------------------+
|                                                                      |
| Event Schema (collapsible)                                           |
| ┌──────────────────────────────────────────────────────────────────┐ |
| │ Input Fields                                                      │ |
| │ ┌──────────────┬──────────┬────────────────────────────────────┐ │ |
| │ │ Field        │ Type     │ Description                        │ │ |
| │ ├──────────────┼──────────┼────────────────────────────────────┤ │ |
| │ │ session_id   │ string   │ Current session UUID               │ │ |
| │ │ tool_name    │ string   │ Name of the tool being called      │ │ |
| │ │ tool_input   │ object   │ Tool's input parameters            │ │ |
| │ │ tool_use_id  │ string   │ Unique ID for this tool invocation │ │ |
| │ │ cwd          │ string   │ Current working directory          │ │ |
| │ └──────────────┴──────────┴────────────────────────────────────┘ │ |
| │                                                                  │ |
| │ Output Format                                                    │ |
| │ ┌──────────────────────────────────────────────────────────────┐ │ |
| │ │ // Allow (continue execution)                                │ │ |
| │ │ { "continue": true }                                         │ │ |
| │ │                                                              │ │ |
| │ │ // Block (deny tool execution)                               │ │ |
| │ │ {                                                            │ │ |
| │ │   "hookSpecificOutput": {                                    │ │ |
| │ │     "decision": {                                            │ │ |
| │ │       "behavior": "deny",                                    │ │ |
| │ │       "message": "Reason for blocking"                       │ │ |
| │ │     }                                                        │ │ |
| │ │   }                                                          │ │ |
| │ │ }                                                            │ │ |
| │ └──────────────────────────────────────────────────────────────┘ │ |
| └──────────────────────────────────────────────────────────────────┘ |
|                                                                      |
| Related Events                                                       |
| [← UserPromptSubmit]  [PostToolUse →]                               |
|                                                                      |
+----------------------------------------------------------------------+
```

---

## Page: `/hooks/sources/[source_id]` (Source Detail)

For **plugin** sources → redirect to `/plugins/[name]` (existing page, could add hooks tab)
For **global/project** sources → dedicated page:

### Layout

```
+====================================================================+
| PageHeader                                                          |
|   title: "Your Hooks (Global)"                                      |
|   breadcrumbs: Dashboard > Hooks > Sources > Global                 |
|   badges: [10 Registrations] [3 Scripts]                            |
+====================================================================+
|                                                                      |
| Event Coverage Matrix                                                |
| ┌─────────────────────────────────────────────────────────────────┐ |
| │ ● SessionStart  ● UserPromptSubmit  ○ PreToolUse               │ |
| │ ● PostToolUse   ● SubagentStart     ● SubagentStop             │ |
| │ ● Stop          ○ PreCompact        ● PermissionRequest        │ |
| │ ● Notification  ● SessionEnd                                   │ |
| │                                                                 │ |
| │ ● = covered (8/11)   ○ = not covered                          │ |
| └─────────────────────────────────────────────────────────────────┘ |
|                                                                      |
| Scripts                                                              |
| (HookScriptCard for each script — same as By Source view)           |
|                                                                      |
+----------------------------------------------------------------------+
```

**Coverage matrix:**
- 11 dots in a grid (4x3 or inline)
- Filled (colored) = this source has hooks for this event
- Empty (outlined) = no hooks
- Each dot clickable → `/hooks/[event_type]`
- Shows "8/11 events covered" summary

---

## Skeleton Loader: `HooksPageSkeleton`

Matches the `AgentsPageSkeleton` pattern:

```
+====================================================================+
| [████████████████] (PageHeader skeleton)                            |
+====================================================================+
| [██████] [██████] [██████] (StatsGrid skeleton — 3 cards)          |
+----------------------------------------------------------------------+
| [████████] [████████] (SegmentedControl skeleton)                   |
+----------------------------------------------------------------------+
| [████████████████████████████████████] (Timeline node skeleton)     |
| [████████████████████████████████████]                              |
| [████████████████████████████████████]                              |
| [████████████████████████████████████]                              |
+----------------------------------------------------------------------+
```

---

## Empty States

### No Hooks Configured

```
┌──────────────────────────────────────────────┐
│            (Webhook icon, 48px)               │
│                                               │
│        No hooks configured                    │
│                                               │
│   Hooks let you intercept and augment         │
│   Claude Code sessions. Add hooks in          │
│   ~/.claude/settings.json or install a        │
│   plugin that provides hooks.                 │
└──────────────────────────────────────────────┘
```

### No Hooks for Event Type

```
┌──────────────────────────────────────────────┐
│       No hooks registered for PreCompact      │
│                                               │
│   No global, project, or plugin hooks fire    │
│   for this event type.                        │
└──────────────────────────────────────────────┘
```

---

## Component Inventory

### New Components

| Component | Purpose | Based On |
|-----------|---------|----------|
| `HookTimeline.svelte` | Vertical lifecycle timeline | New (no equivalent) |
| `HookEventNode.svelte` | Single event node in timeline | `CollapsibleGroup` behavior |
| `HookRegistrationCard.svelte` | Individual hook binding | `AgentUsageCard` layout |
| `HookScriptCard.svelte` | Script file card | `SkillUsageCard` layout |
| `HookEventBadge.svelte` | Event type pill/badge | `Badge` component |
| `HookSchemaDocs.svelte` | Event schema viewer | Skill definition collapsible |
| `EventCoverageMatrix.svelte` | Dot matrix of event coverage | New |
| `HooksPageSkeleton.svelte` | Loading skeleton | `AgentsPageSkeleton` |

### Reused Components (No Changes)

| Component | Usage in Hooks Page |
|-----------|-------------------|
| `PageHeader` | Page title, breadcrumbs, icon |
| `StatsGrid` | Hero stats row |
| `SegmentedControl` | View toggle (Timeline / By Source) |
| `CollapsibleGroup` | Source groups in By Source view |
| `Badge` | Language, timeout, blocking badges |
| `EmptyState` | No hooks configured state |

### Utility Functions

```typescript
// New: hooks color utilities
function getHookSourceColorVars(source: HookSource): { color: string; subtle: string } {
  if (source.source_type === 'plugin') {
    return getPluginColorVars(source.source_name);
  }
  if (source.source_type === 'project') {
    return { color: 'var(--scope-project)', subtle: 'var(--scope-project-subtle)' };
  }
  // Global/"Your Hooks" → warm yellow
  return { color: 'oklch(0.8 0.12 85)', subtle: 'oklch(0.8 0.12 85 / 0.1)' };
}

function getEventPhase(eventType: string): string {
  const phases: Record<string, string> = {
    SessionStart: 'Session Lifecycle',
    SessionEnd: 'Session End',
    UserPromptSubmit: 'User Input',
    PreToolUse: 'Tool Lifecycle',
    PostToolUse: 'Tool Lifecycle',
    SubagentStart: 'Agent Lifecycle',
    SubagentStop: 'Agent Lifecycle',
    Stop: 'Agent Lifecycle',
    PreCompact: 'Context & Permissions',
    PermissionRequest: 'Context & Permissions',
    Notification: 'System',
  };
  return phases[eventType] ?? 'Unknown';
}

function canBlock(eventType: string): boolean {
  return ['PreToolUse', 'UserPromptSubmit', 'PermissionRequest', 'Stop'].includes(eventType);
}

function detectLanguage(command: string): 'python' | 'node' | 'shell' | 'unknown' {
  if (command.startsWith('python') || command.endsWith('.py')) return 'python';
  if (command.startsWith('node') || command.endsWith('.mjs') || command.endsWith('.js') || command.endsWith('.cjs')) return 'node';
  if (command.endsWith('.sh')) return 'shell';
  return 'unknown';
}
```

---

## Responsive Design

### Desktop (>1024px)
- Full timeline with expanded registration cards
- 3-column stats grid
- Script cards in 2-3 column grid (By Source view)

### Tablet (768-1024px)
- Timeline collapses to compact mode (click to expand)
- 3-column stats grid (smaller)
- Script cards in 2-column grid

### Mobile (<768px)
- Timeline as stacked cards (no visual line)
- Stats stack vertically
- Script cards single column
- Hamburger menu includes Hooks link

---

## Accessibility

- Timeline nodes are focusable and keyboard-navigable (up/down arrows)
- `aria-expanded` on collapsible event nodes
- Color is never the only differentiator (source names always visible alongside dots)
- "CAN BLOCK" badge uses both color and text
- Screen reader: "PreToolUse, Tool Lifecycle, can block execution, 5 hooks registered"

"""
Workflow execution engine.

Orchestrates multi-step Claude Code workflows by:
1. Topologically sorting steps based on graph edges
2. Resolving prompt templates with step outputs
3. Spawning `claude -p` subprocesses for each step
4. Tracking execution state in SQLite
"""

import asyncio
import json
import logging
import re
import sqlite3
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Template variable pattern: {{ inputs.name }} or {{ steps.id.field }}
TEMPLATE_PATTERN = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def resolve_template(template: str, context: dict[str, Any]) -> str:
    """
    Replace {{ var.path }} placeholders with values from context.

    Context structure:
        {
            "inputs": {"feature": "auth"},
            "steps": {"extract": {"output": "...", "session_id": "..."}},
            "workflow": {"name": "...", "project_path": "..."},
            "run": {"id": "..."},
        }
    """

    def replacer(match: re.Match) -> str:
        path = match.group(1)
        parts = path.split(".")
        obj: Any = context
        for part in parts:
            if isinstance(obj, dict):
                obj = obj.get(part, "")
            else:
                return ""
            if obj is None:
                return ""
        return str(obj) if obj != "" else ""

    return TEMPLATE_PATTERN.sub(replacer, template)


def topological_sort(step_ids: list[str], edges: list[dict]) -> list[str]:
    """
    Topologically sort step IDs based on edges.

    Each edge is {"source": "step_a", "target": "step_b"} meaning
    step_a must run before step_b.

    Returns ordered list of step IDs.
    """
    in_degree: dict[str, int] = {sid: 0 for sid in step_ids}
    adjacency: dict[str, list[str]] = defaultdict(list)

    for edge in edges:
        src = edge.get("source", "")
        tgt = edge.get("target", "")
        if src in in_degree and tgt in in_degree:
            adjacency[src].append(tgt)
            in_degree[tgt] += 1

    queue = deque(sid for sid in step_ids if in_degree[sid] == 0)
    result: list[str] = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return result


def evaluate_condition(condition: Optional[str], context: dict[str, Any]) -> bool:
    """
    Evaluate a simple condition string.

    Supports: "{{ var }} == value" and "{{ var }} != value"
    Returns True if condition is None (no condition = always run).
    """
    if condition is None:
        return True

    # Resolve template variables first
    resolved = resolve_template(condition, context)

    # Simple equality/inequality check
    if "!=" in resolved:
        left, right = resolved.split("!=", 1)
        return left.strip() != right.strip()
    elif "==" in resolved:
        left, right = resolved.split("==", 1)
        return left.strip() == right.strip()

    # If just a value, treat truthy
    val = resolved.strip().lower()
    return val not in ("", "false", "none", "0", "null")


async def run_claude_step(
    prompt: str,
    *,
    model: str = "sonnet",
    tools: list[str] | None = None,
    max_turns: int = 10,
    cwd: str | None = None,
) -> dict[str, Any]:
    """
    Run a single Claude Code step via `claude -p` subprocess.

    Returns dict with:
        - result: str (Claude's response)
        - session_id: str (session UUID from JSON output)
        - exit_code: int
    """
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--model",
        model,
        "--max-turns",
        str(max_turns),
    ]

    if tools:
        cmd.extend(["--allowedTools", ",".join(tools)])

    logger.info("Running claude step: model=%s, cwd=%s", model, cwd)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )

    stdout, stderr = await proc.communicate()
    exit_code = proc.returncode or 0

    result_text = ""
    session_id = None

    if stdout:
        try:
            data = json.loads(stdout.decode())
            result_text = data.get("result", "")
            session_id = data.get("session_id", None)
        except json.JSONDecodeError:
            result_text = stdout.decode()

    if exit_code != 0 and stderr:
        logger.warning("Claude step stderr: %s", stderr.decode()[:500])

    return {
        "result": result_text,
        "session_id": session_id,
        "exit_code": exit_code,
    }


def _get_write_conn() -> sqlite3.Connection:
    """Get a write connection for workflow state updates."""
    from db.connection import get_db_path

    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _update_step_status(
    run_id: str,
    step_id: str,
    status: str,
    *,
    session_id: str | None = None,
    prompt: str | None = None,
    output: str | None = None,
    error: str | None = None,
) -> None:
    """Update a workflow run step's status in SQLite."""
    conn = _get_write_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        if status == "running":
            conn.execute(
                "UPDATE workflow_run_steps SET status=?, started_at=?, prompt=? WHERE run_id=? AND step_id=?",
                (status, now, prompt, run_id, step_id),
            )
        elif status in ("completed", "failed", "skipped"):
            conn.execute(
                "UPDATE workflow_run_steps SET status=?, completed_at=?, session_id=?, output=?, error=? WHERE run_id=? AND step_id=?",
                (status, now, session_id, output, error, run_id, step_id),
            )
        conn.commit()
    finally:
        conn.close()


def _update_run_status(run_id: str, status: str, error: str | None = None) -> None:
    """Update a workflow run's status in SQLite."""
    conn = _get_write_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        if status == "running":
            conn.execute(
                "UPDATE workflow_runs SET status=?, started_at=? WHERE id=?",
                (status, now, run_id),
            )
        else:
            conn.execute(
                "UPDATE workflow_runs SET status=?, completed_at=?, error=? WHERE id=?",
                (status, now, error, run_id),
            )
        conn.commit()
    finally:
        conn.close()


async def execute_workflow(
    run_id: str,
    workflow_id: str,
    steps: list[dict],
    edges: list[dict],
    input_values: dict[str, Any],
    project_path: str | None = None,
    workflow_name: str = "",
) -> None:
    """
    Execute a full workflow run.

    Called as an asyncio background task from the API endpoint.
    Updates SQLite with step-by-step progress.
    """
    _update_run_status(run_id, "running")

    # Build step lookup
    step_map = {s["id"]: s for s in steps}
    step_ids = [s["id"] for s in steps]
    ordered = topological_sort(step_ids, edges)

    # Execution context for template resolution
    context: dict[str, Any] = {
        "inputs": input_values or {},
        "steps": {},
        "workflow": {"name": workflow_name, "project_path": project_path or ""},
        "run": {"id": run_id},
    }

    try:
        for step_id in ordered:
            step_def = step_map.get(step_id)
            if not step_def:
                continue

            # Check condition
            if not evaluate_condition(step_def.get("condition"), context):
                _update_step_status(run_id, step_id, "skipped")
                context["steps"][step_id] = {"output": "", "session_id": ""}
                continue

            # Resolve prompt template
            prompt = resolve_template(step_def["prompt_template"], context)
            _update_step_status(run_id, step_id, "running", prompt=prompt)

            # Execute
            result = await run_claude_step(
                prompt,
                model=step_def.get("model", "sonnet"),
                tools=step_def.get("tools"),
                max_turns=step_def.get("max_turns", 10),
                cwd=project_path,
            )

            if result["exit_code"] != 0:
                _update_step_status(
                    run_id,
                    step_id,
                    "failed",
                    session_id=result.get("session_id"),
                    output=result.get("result"),
                    error=f"Exit code {result['exit_code']}",
                )
                _update_run_status(
                    run_id, "failed", f"Step '{step_id}' failed with exit code {result['exit_code']}"
                )
                return

            # Success
            _update_step_status(
                run_id,
                step_id,
                "completed",
                session_id=result.get("session_id"),
                output=result.get("result"),
            )

            # Update context for downstream steps
            context["steps"][step_id] = {
                "output": result.get("result", ""),
                "session_id": result.get("session_id", ""),
            }

        _update_run_status(run_id, "completed")

    except Exception as e:
        logger.exception("Workflow run %s failed", run_id)
        _update_run_status(run_id, "failed", str(e))

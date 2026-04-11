#!/usr/bin/env python3
"""
Session title generator hook for Claude Code Karma.

Fires on SessionEnd, reads the session JSONL, extracts context,
and generates a concise title. Prefers git commit messages when
available (free, no LLM). Falls back to Claude Haiku via
`claude -p --no-session-persistence` to avoid creating bloat sessions.

"""

import fcntl
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

API_BASE = os.environ.get("CLAUDE_KARMA_API", "http://localhost:8000")
TITLE_MODEL = os.environ.get("CLAUDE_KARMA_TITLE_MODEL", "minimax/minimax-m2.5-pro-free")

# Logging setup
LOG_DIR = Path(os.path.expanduser("~/.claude_karma"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / "title-generator.log"),
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("title-gen")

# Lock and queue
KARMA_BASE = Path(os.path.expanduser("~/.claude_karma"))
WORKER_LOCK = KARMA_BASE / ".title-worker.lock"
MAX_PROMPT_LENGTH = 500
MAX_RESPONSE_LENGTH = 300
TITLE_MAX_WORDS = 10


def _strip_system_tags(text: str) -> str:
    """Remove XML system/skill tags, keeping any real user text around them."""
    cleaned = re.sub(
        r"<(?:command-message|system-reminder|command-name|user-prompt-submit-hook)[^>]*>.*?</(?:command-message|system-reminder|command-name|user-prompt-submit-hook)>",
        "",
        text,
        flags=re.DOTALL,
    )
    # Also strip self-closing variants
    cleaned = re.sub(r"<(?:command-message|system-reminder|command-name|user-prompt-submit-hook)[^/]*/?>", "", cleaned)
    return cleaned.strip()


def _extract_text(msg: dict) -> str:
    """Extract plain text from a message's content (handles string and list forms)."""
    content = msg.get("content", "")
    if isinstance(content, list):
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        content = " ".join(texts)
    return content.strip() if isinstance(content, str) else ""


def _get_session_start_iso(transcript_path: str) -> Optional[str]:
    """Extract the ISO timestamp of the first entry in a JSONL transcript."""
    try:
        with open(transcript_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp")
                    if ts:
                        return ts
                except json.JSONDecodeError:
                    continue
    except (OSError, IOError):
        pass
    return None


def _acquire_worker_lock():
    """Return lock file handle if acquired, None if another worker is running."""
    try:
        fh = open(WORKER_LOCK, "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError:
        fh.close() if 'fh' in locals() else None
        return None


def _drain_retry_queue() -> None:
    """Process all pending retries in ~/.claude_karma/title-retry/."""
    retry_dir = KARMA_BASE / "title-retry"
    if not retry_dir.exists():
        return
    for path in sorted(retry_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            path.unlink(missing_ok=True)
            continue

        session_id = data.get("session_id", "")
        title, source = generate_title(
            data.get("initial_prompt", ""),
            data.get("first_response"),
            data.get("git_context"),
        )
        if title:
            if post_title(session_id, title):
                path.unlink(missing_ok=True)
                log.info("Drained retry: session=%s source=%s", session_id[:12], source)
        elif source in ("rate_limited", "timeout"):
            log.warning("Retry still failing (%s), leaving in queue", source)
            break


def main():
    # Background mode: called from detached subprocess with context file
    if len(sys.argv) > 1 and sys.argv[1] == "--background":
        if len(sys.argv) < 3:
            log.warning("Background: missing context file arg")
            return

        context_file = Path(sys.argv[2])
        if not context_file.exists():
            log.warning("Background: context file not found: %s", context_file)
            return

        try:
            data = json.loads(context_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            log.error("Background: failed to read context file: %s", e)
            return
        finally:
            context_file.unlink(missing_ok=True)

        # Try to acquire lock (non-blocking)
        lock_fh = _acquire_worker_lock()
        if not lock_fh:
            log.info("Background: lock busy, enqueuing for later retry")
            # Enqueue this session for retry
            enqueue_title_retry(
                data.get("session_id", ""),
                data.get("transcript_path", ""),
                data.get("initial_prompt", ""),
                data.get("first_response"),
                data.get("cwd", ""),
            )
            return

        try:
            # Generate title for this session
            title, source = generate_title(
                data.get("initial_prompt", ""),
                data.get("first_response"),
                data.get("git_context"),
            )
            if title:
                post_title(data.get("session_id", ""), title)
            elif source in ("rate_limited", "timeout"):
                enqueue_title_retry(
                    data.get("session_id", ""),
                    data.get("transcript_path", ""),
                    data.get("initial_prompt", ""),
                    data.get("first_response"),
                    data.get("cwd", ""),
                )

            # Drain the full retry queue before releasing lock
            log.info("Background: draining retry queue")
            _drain_retry_queue()
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
            lock_fh.close()
        return

    # Normal hook mode: called with stdin JSON
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        log.warning("Failed to parse stdin JSON")
        return

    session_id = data.get("session_id", "")
    transcript_path = data.get("transcript_path", "")
    cwd = data.get("cwd", "")
    reason = data.get("reason", "")

    log.info("SessionEnd hook fired — session=%s reason=%s", session_id[:12], reason)

    # Skip if no transcript or if cleared (not meaningful sessions)
    if not transcript_path or not Path(transcript_path).exists():
        log.info("Skipped — no transcript found")
        return
    if reason in ("clear", "resume"):
        log.info("Skipped — reason is %r", reason)
        return

    # Extract context from JSONL (fast, no network)
    initial_prompt, first_response = extract_session_context(transcript_path)
    if not initial_prompt:
        log.info("Skipped — no initial prompt extracted")
        return

    # Get git commits during session (fast, local)
    git_context = get_git_context(cwd, transcript_path)

    # Spawn background process to generate title (non-blocking)
    context_payload = json.dumps({
        "session_id": session_id,
        "transcript_path": transcript_path,
        "initial_prompt": initial_prompt,
        "first_response": first_response,
        "cwd": cwd,
        "git_context": git_context,
    })

    context_file = Path(f"/tmp/session_title_{session_id}.json")
    context_file.write_text(context_payload, encoding="utf-8")

    log.info("Spawning background process for title generation")

    subprocess.Popen(
        [sys.executable, __file__, "--background", str(context_file)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def extract_session_context(transcript_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract initial prompt and first assistant response from JSONL."""
    initial_prompt = None
    first_response = None

    try:
        with open(transcript_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = entry.get("message", {})
                role = msg.get("role", "")

                # Skip sidechain messages (subagents)
                if entry.get("isSidechain"):
                    continue

                if role == "user" and initial_prompt is None:
                    text = _strip_system_tags(_extract_text(msg))
                    if text:
                        initial_prompt = text[:MAX_PROMPT_LENGTH]

                elif role == "assistant" and initial_prompt and first_response is None:
                    text = _extract_text(msg)
                    if text:
                        first_response = text[:MAX_RESPONSE_LENGTH]
                        break
    except (OSError, IOError):
        pass

    return initial_prompt, first_response


def get_git_context(cwd: str, transcript_path: str) -> Optional[str]:
    """Get git commits made during the session timeframe.

    Uses the JSONL transcript's first timestamp to scope the git log to
    the actual session duration rather than an arbitrary fixed window.
    Falls back to 1 hour if the timestamp can't be extracted.
    """
    if not cwd or not Path(cwd).exists():
        return None

    since_arg = "1 hour ago"
    start_ts = _get_session_start_iso(transcript_path)
    if start_ts:
        since_arg = start_ts

    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"--since={since_arg}", "--no-merges", "-10"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()[:300]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return None


def generate_title(
    initial_prompt: str,
    first_response: Optional[str],
    git_context: Optional[str],
) -> Tuple[Optional[str], str]:
    """Generate a concise session title.

    Priority:
    1. Git commit messages (if available) — free, no LLM needed
    2. Claude Haiku via `claude -p` with --no-session-persistence to avoid bloat
    3. Fallback: truncated initial prompt

    Returns (title, source) where source is 'git', 'haiku', or 'fallback'.
    """
    # 1. Use most recent git commit message as title if available
    if git_context:
        # git_context is "hash msg\nhash msg\n..." — take the first (most recent) line
        first_commit = git_context.split("\n")[0].strip()
        if first_commit:
            # Strip the short hash prefix (e.g. "a1b2c3d fix: something" → "fix: something")
            parts = first_commit.split(" ", 1)
            title = parts[1] if len(parts) > 1 else parts[0]
            words = title.split()
            if len(words) > TITLE_MAX_WORDS:
                title = " ".join(words[:TITLE_MAX_WORDS])
            return title, "git"

    # 2. Fall back to opencode with free model
    parts = [f"User asked: {initial_prompt}"]
    if first_response:
        parts.append(f"Assistant did: {first_response}")
    context = "\n".join(parts)

    prompt = f"""Generate a concise 5-{TITLE_MAX_WORDS} word title for this coding session.
The title should describe what was accomplished or attempted.
Return ONLY the title, no quotes, no explanation.

{context}

Title:"""

    try:
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)

        result = subprocess.run(
            ["opencode", "run", prompt, "--model", TITLE_MODEL],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

        if result.returncode == 0 and result.stdout.strip():
            title = result.stdout.strip()
            title = title.strip('"\'')
            words = title.split()
            if len(words) > TITLE_MAX_WORDS:
                title = " ".join(words[:TITLE_MAX_WORDS])
            return title, "opencode"

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # 3. Fallback: truncated initial prompt
    fallback = initial_prompt[:60]
    if len(initial_prompt) > 60:
        fallback += "..."
    return fallback, "fallback"


def enqueue_title_retry(
    session_id: str,
    transcript_path: str,
    initial_prompt: str,
    first_response: Optional[str],
    cwd: str,
) -> None:
    """Save session context to the retry queue for later processing."""
    try:
        retry_dir = KARMA_BASE / "title-retry"
        retry_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "session_id": session_id,
            "transcript_path": transcript_path,
            "initial_prompt": initial_prompt,
            "first_response": first_response,
            "cwd": cwd,
            "git_context": get_git_context(cwd, transcript_path),
        }
        (retry_dir / f"{session_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        log.info("Enqueued retry for session=%s", session_id[:12])
    except OSError as e:
        log.error("Failed to enqueue retry: %s", e)


def post_title(session_id: str, title: str) -> bool:
    """POST the generated title to the Claude Code Karma API. Returns True on success."""
    import urllib.request
    import urllib.error

    url = f"{API_BASE}/sessions/{session_id}/title"
    data = json.dumps({"title": title}).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except (urllib.error.URLError, OSError):
        return False


if __name__ == "__main__":
    main()

# dev.py — single-command dev launcher for claude-code-karma
# Usage: python dev.py
# Requirements: Python 3.9+ (already required), Node 18+, npm 7+

import json, os, signal, socket, subprocess, sys, threading

# ── Colors (ANSI) ────────────────────────────────────────────────────────────
def _enable_windows_ansi():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        h = ctypes.windll.kernel32.GetStdHandle(-11)
        m = ctypes.c_ulong()
        ctypes.windll.kernel32.GetConsoleMode(h, ctypes.byref(m))
        ctypes.windll.kernel32.SetConsoleMode(h, m.value | 0x0004)
    except Exception:
        pass

BLUE, GREEN, YELLOW, BOLD, RESET = "\033[94m", "\033[92m", "\033[93m", "\033[1m", "\033[0m"

# ── Port discovery ────────────────────────────────────────────────────────────
def find_free_port(start: int) -> int:
    port = start
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if s.connect_ex(("localhost", port)) != 0:
                return port
        port += 1

# ── Log streaming ─────────────────────────────────────────────────────────────
def stream(proc, prefix, color):
    try:
        for line in proc.stdout:
            stripped = line.rstrip()
            if stripped:
                print(f"{color}{BOLD}[{prefix}]{RESET} {stripped}", flush=True)
    except ValueError:
        pass

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    _enable_windows_ansi()

    api_port = find_free_port(8000)
    web_port = find_free_port(5173)

    if api_port != 8000:
        print(f"{YELLOW}⚠  Port 8000 in use → using {api_port} for API{RESET}")
    if web_port != 5173:
        print(f"{YELLOW}⚠  Port 5173 in use → using {web_port} for frontend{RESET}")

    print(f"\n{BOLD}Claude Code Karma — dev{RESET}")
    print(f"  {BLUE}{BOLD}[API]{RESET} http://localhost:{api_port}")
    print(f"  {GREEN}{BOLD}[WEB]{RESET} http://localhost:{web_port}\n")

    # API env: allow a window of ports around web_port to absorb any minor
    # Vite port shift (e.g. race condition where chosen port gets taken).
    cors_ports = range(web_port, web_port + 4)
    api_env = os.environ.copy()
    api_env["PYTHONUNBUFFERED"] = "1"
    api_env["FORCE_COLOR"] = "1"
    api_env["CLAUDE_KARMA_CORS_ORIGINS"] = json.dumps(
        [f"http://localhost:{p}" for p in cors_ports] +
        [f"http://127.0.0.1:{p}" for p in cors_ports]
    )

    # Frontend env: $env/dynamic/public reads PUBLIC_API_URL from process.env
    # at request time — no .env file needed, works across multiple instances.
    web_env = os.environ.copy()
    web_env["FORCE_COLOR"] = "1"
    web_env["PUBLIC_API_URL"] = f"http://localhost:{api_port}"

    is_win = sys.platform == "win32"

    api_proc = subprocess.Popen(
        ["uvicorn", "main:app", "--reload", "--port", str(api_port)],
        cwd="api",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, env=api_env,
    )
    web_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(web_port)],
        cwd="frontend",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, env=web_env,
        shell=is_win,
    )

    threading.Thread(target=stream, args=(api_proc, "API", BLUE),  daemon=True).start()
    threading.Thread(target=stream, args=(web_proc, "WEB", GREEN), daemon=True).start()

    def shutdown(sig=None, frame=None):
        print(f"\n{YELLOW}⏹  Shutting down...{RESET}")
        api_proc.terminate()
        web_proc.terminate()
        try:
            api_proc.wait(timeout=5)
            web_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_proc.kill()
            web_proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    api_proc.wait()
    web_proc.wait()

if __name__ == "__main__":
    main()

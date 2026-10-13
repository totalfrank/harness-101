"""Diagnose why the SDK can't start the claude CLI.  Run:  python -m harness.doctor

Starts the CLI in progressively more SDK-like ways and reports where it breaks.
Makes at most one tiny model call (step 4).
"""

import os
import platform
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import claude_agent_sdk


def run(label, cmd, **kw):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60, **kw)
        out = (p.stdout.strip() or p.stderr.strip()).splitlines()
        print(f"  {label}: exit {p.returncode}  {out[-1][:100] if out else ''}")
        if p.returncode != 0 and p.stderr.strip():
            print("    stderr:", p.stderr.strip()[-400:])
        return p.returncode
    except Exception as e:  # noqa: BLE001
        print(f"  {label}: {type(e).__name__}: {e}")
        return None


def main():
    bundled = Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"
    candidates = {"HARNESS_CLI_PATH": os.environ.get("HARNESS_CLI_PATH"),
                  "PATH claude": shutil.which("claude"),
                  "bundled": str(bundled) if bundled.exists() else None}

    print("1. Environment")
    print(f"  python {sys.version.split()[0]} at {sys.executable}")
    print(f"  python arch: {platform.machine()}  os: {platform.platform()}")
    print(f"  claude-agent-sdk {version('claude-agent-sdk')}")
    print(f"  ANTHROPIC_API_KEY set: {bool(os.environ.get('ANTHROPIC_API_KEY'))}")
    for name, path in candidates.items():
        if path and shutil.which("file"):
            arch = subprocess.run(["file", "-b", path], capture_output=True, text=True).stdout.strip()
            print(f"  {name}: {path}\n    {arch[:110]}")
        else:
            print(f"  {name}: {path}")

    print("\n2. `claude --version` started from Python")
    for name, path in candidates.items():
        if path:
            run(name, [path, "--version"])

    cli = candidates["HARNESS_CLI_PATH"] or candidates["PATH claude"] or candidates["bundled"]
    print(f"\n3. One-shot `-p` with SDK-style flags, no model call ({cli})")
    run("--help", [cli, "-p", "--output-format", "stream-json", "--verbose", "--help"])

    print("\n4. Tiny real model call (stdin closed, like a pipe)")
    model = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("WEAK_MODEL", "")
    cmd = [cli, "-p", "Reply with just: ok", "--output-format", "text", "--max-turns", "1"]
    if model:
        cmd += ["--model", model]
    run("prompt", cmd, stdin=subprocess.DEVNULL)

    print("\nA negative exit code is a signal: -9 = SIGKILL from outside the process.")
    if sys.platform == "darwin":
        print("On macOS, check who killed it (run right after a failure):\n"
              "  log show --last 2m --predicate 'eventMessage CONTAINS[c] \"claude\"' "
              "--style compact | grep -iE 'kill|sign|deny|jetsam' | tail -20")


if __name__ == "__main__":
    main()

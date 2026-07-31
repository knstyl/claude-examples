#!/usr/bin/env python3
"""PostToolUse hook (matcher: Edit|Write): deterministic KB hygiene.

For any file written under a `.knowledge` directory:
  1. warn (exit 2) if the write targeted a generated file (INDEX.md / MANIFEST.yaml)
  2. regenerate MANIFEST.yaml + INDEX.md for that tier
  3. validate the tier; feed errors back to the agent (exit 2)

Non-KB writes and unexpected failures exit 0 silently — this hook must never
break a session. Registered in ~/.claude/settings.json.
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
GLOBAL_ROOT = SCRIPTS.parent
GENERATED = {"INDEX.md", "MANIFEST.yaml"}


def find_kb_root(path: Path):
    parts = path.parts
    if ".knowledge" not in parts:
        return None
    idx = parts.index(".knowledge")
    return Path(*parts[: idx + 1])


def main() -> int:
    payload = json.load(sys.stdin)
    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return 0
    path = Path(file_path)
    root = find_kb_root(path)
    if root is None or not root.is_dir():
        return 0

    if path.name in GENERATED:
        print(f"{path.name} is generated -- edit entries instead, then run "
              f"python {SCRIPTS / 'build_manifest.py'} --root {root} --index",
              file=sys.stderr)
        return 2

    py = sys.executable or "python"
    subprocess.run([py, str(SCRIPTS / "build_manifest.py"),
                    "--root", str(root), "--index"],
                   capture_output=True, text=True, timeout=60)

    cmd = [py, str(SCRIPTS / "validate.py"), "--root", str(root)]
    if root.resolve() != GLOBAL_ROOT.resolve():
        cmd += ["--extra-root", str(GLOBAL_ROOT)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        sys.stderr.write("KB validation failed after this write -- fix before "
                         "continuing (see _meta/PROTOCOL.md):\n"
                         + result.stdout[-2000:])
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # hygiene hook: fail open, never break the session

#!/usr/bin/env python3
"""SessionStart hook: one-line nag when KB entries are overdue for review.

Checks the global tier and (when the session's cwd is inside a project with a
`.knowledge/` directory) the project tier. Prints a single line when overdue
entries exist, stays silent otherwise. Always exits 0 — this hook must never
break a session. Registered in ~/.claude/settings.json.
"""
import json
import sys
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
GLOBAL_ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))


def count_overdue(root: Path) -> int:
    from validate import as_date, iter_entries, parse_frontmatter
    overdue = 0
    for path in iter_entries(root):
        fm, _, err = parse_frontmatter(path)
        if err or not isinstance(fm, dict):
            continue
        if fm.get("status") in ("deprecated", "superseded"):
            continue
        review_by = as_date(fm.get("review_by"))
        if review_by and review_by < date.today():
            overdue += 1
    return overdue


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    cwd = Path(payload.get("cwd") or Path.cwd())

    tiers = {GLOBAL_ROOT.resolve()}
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".knowledge"
        if candidate.is_dir():
            tiers.add(candidate.resolve())
            break

    total = sum(count_overdue(root) for root in tiers)
    if total:
        plural = "entries" if total != 1 else "entry"
        print(f"KB freshness: {total} {plural} overdue for review -- "
              f"run /curator gc when convenient.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)

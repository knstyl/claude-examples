#!/usr/bin/env python3
"""Create a new .knowledge entry with valid frontmatter and a section skeleton.

Usage:
  python scripts/new_entry.py --dir mlops/inference --id kserve-canary-isvc \
      --title "Canary Rollouts for InferenceServices" \
      --domain mlops --type standard --tags kserve,flagger,canary

  # Local-tier entry in a project repo:
  python scripts/new_entry.py --root <project>/.knowledge --scope local \
      --dir constraints --id gpu-quota --title "GPU Quota" \
      --domain ops --type constraint --tags gpu,quotas
"""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

BASE_SECTIONS = ["Summary", "When to apply", "Rules", "Examples",
                 "Anti-patterns", "References"]
SECTIONS_BY_TYPE = {
    "runbook": ["Summary", "Symptoms", "Diagnosis", "Resolution",
                "Verification", "References"],
    "decision": ["Summary", "Context", "Decision", "Consequences", "References"],
    "glossary": ["Summary", "Terms"],
    "gotcha": ["Summary", "The trap", "Why it happens", "What to do instead",
               "References"],
    "context": ["Summary", "Details", "References"],
    "constraint": ["Summary", "Constraints", "Rationale", "References"],
    "override": ["Summary", "What changes vs global", "Rationale", "References"],
}
# review_by = verified_on + interval; decisions are immutable records (no review).
REVIEW_INTERVAL_DAYS = {
    "runbook": 90, "context": 90,
    "standard": 180, "constraint": 180, "override": 180,
    "pattern": 365, "glossary": 365, "gotcha": 365,
}


def render_entry(entry_id, title, domain, entry_type, tags, scope,
                 today, overrides=None, related=None, source=None):
    lines = [
        "---",
        f"id: {entry_id}",
        f'title: "{title}"',
        f"domain: {domain}",
        f"tags: [{', '.join(tags)}]",
        f"type: {entry_type}",
        f"scope: {scope}",
        "status: draft",
        f"last_updated: {today.isoformat()}",
        f"verified_on: {today.isoformat()}",
    ]
    interval = REVIEW_INTERVAL_DAYS.get(entry_type)
    if interval is not None:
        lines.append(f"review_by: {(today + timedelta(days=interval)).isoformat()}")
    if source:
        lines.append(f"source: {source}")
    if overrides:
        lines.append(f"overrides: {overrides}")
    if related:
        lines.append(f"related: [{', '.join(related)}]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    for section in SECTIONS_BY_TYPE.get(entry_type, BASE_SECTIONS):
        lines.append("")
        lines.append(f"## {section}")
        lines.append("")
        lines.append("TODO.")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--dir", required=True,
                        help="directory relative to root, e.g. mlops/inference")
    parser.add_argument("--id", required=True, dest="entry_id")
    parser.add_argument("--title", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--type", required=True, dest="entry_type")
    parser.add_argument("--tags", required=True,
                        help="comma-separated, e.g. kserve,gpu")
    parser.add_argument("--scope", default="global", choices=["global", "local"])
    parser.add_argument("--overrides", default=None,
                        help="global id this entry overrides (type=override)")
    parser.add_argument("--source", default=None,
                        help="deliverable this entry was distilled from (path/URL)")
    args = parser.parse_args()

    target = args.root.resolve() / args.dir / f"{args.entry_id}.md"
    if target.exists():
        print(f"error: {target} already exists", file=sys.stderr)
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_entry(args.entry_id, args.title, args.domain, args.entry_type,
                     [t.strip() for t in args.tags.split(",") if t.strip()],
                     args.scope, date.today(),
                     overrides=args.overrides, source=args.source),
        encoding="utf-8")
    print(f"Created {target}")
    print("Next: fill in the Summary, then run scripts/build_manifest.py --index "
          "and scripts/validate.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

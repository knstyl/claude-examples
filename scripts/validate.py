#!/usr/bin/env python3
"""Validate .knowledge entry frontmatter and structure.

Usage:
  python scripts/validate.py                          # validate the repo this script lives in
  python scripts/validate.py --root <dir>             # validate another .knowledge root
  python scripts/validate.py --root <project>/.knowledge --extra-root ~/.knowledge
                                                      # local tier, resolving ids against global
  python scripts/validate.py --strict                 # warnings become errors (use in CI)
  python scripts/validate.py --check-index            # also fail if INDEX.md is out of date

Error checks:
  - frontmatter parses as YAML between --- delimiters
  - required keys: id, title, domain, tags, type, scope, status, last_updated, verified_on
  - review_by present for every type except decision
  - controlled vocabularies for domain / type / scope / status
  - id is kebab-case and matches the filename stem
  - ids unique across all roots
  - tags is a non-empty list of kebab-case strings
  - last_updated / verified_on / review_by are ISO dates
  - type "override" entries set `overrides`
  - overrides / supersedes / related reference ids that exist
  - body contains a "## Summary" section
  - with --check-index: INDEX.md matches what build_manifest.py --index would generate

Warning checks (errors with --strict):
  - review_by date in the past (stale entry)

Exit code: 0 clean, 1 errors (or warnings with --strict).
"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

import yaml

DOMAINS = {"backend", "mlops", "deployment", "product", "ops", "process"}
TYPES = {"standard", "pattern", "runbook", "decision", "constraint",
         "glossary", "gotcha", "override", "context"}
SCOPES = {"global", "local"}
STATUSES = {"draft", "active", "deprecated", "superseded"}
REQUIRED = ["id", "title", "domain", "tags", "type", "scope", "status",
            "last_updated", "verified_on"]
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
SKIP_DIRS = {".git", "_meta", "_templates", "_schema", "scripts", "templates",
             "archive", "node_modules", "__pycache__"}
SKIP_FILES = {"README.md", "INDEX.md"}


def iter_entries(root: Path):
    """Yield entry files under root, skipping infrastructure directories."""
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        yield path


def parse_frontmatter(path: Path):
    """Return (frontmatter_dict, body, error). On failure the dict is None."""
    text = path.read_text(encoding="utf-8")
    m = FM_RE.match(text)
    if not m:
        return None, None, "missing or malformed frontmatter block (must start with ---)"
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        return None, None, f"frontmatter is not valid YAML: {exc}"
    if not isinstance(fm, dict):
        return None, None, "frontmatter did not parse to a mapping"
    return fm, m.group(2), None


def as_date(value):
    """Coerce a YAML value to a date, or return None."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def check_entry(path: Path, root: Path, fm: dict, body: str):
    errors, warnings = [], []

    for key in REQUIRED:
        if fm.get(key) in (None, "", []):
            errors.append(f"missing required key: {key}")
    if errors:
        return errors, warnings  # can't meaningfully check further

    entry_id = fm["id"]
    if not isinstance(entry_id, str) or not KEBAB.match(entry_id):
        errors.append(f"id is not kebab-case: {entry_id!r}")
    if entry_id != path.stem:
        errors.append(f"id {entry_id!r} does not match filename stem {path.stem!r}")

    if fm["domain"] not in DOMAINS:
        errors.append(f"domain {fm['domain']!r} not in {sorted(DOMAINS)}")
    if fm["type"] not in TYPES:
        errors.append(f"type {fm['type']!r} not in {sorted(TYPES)}")
    if fm["scope"] not in SCOPES:
        errors.append(f"scope {fm['scope']!r} not in {sorted(SCOPES)}")
    if fm["status"] not in STATUSES:
        errors.append(f"status {fm['status']!r} not in {sorted(STATUSES)}")

    tags = fm["tags"]
    if not isinstance(tags, list) or not tags:
        errors.append("tags must be a non-empty list")
    else:
        for tag in tags:
            if not isinstance(tag, str) or not KEBAB.match(tag):
                errors.append(f"tag is not kebab-case: {tag!r}")

    for key in ("last_updated", "verified_on"):
        if as_date(fm[key]) is None:
            errors.append(f"{key} is not an ISO date: {fm[key]!r}")

    if fm["type"] == "override" and not fm.get("overrides"):
        errors.append("type is 'override' but `overrides:` is not set")

    if not re.search(r"^## Summary\b", body, re.MULTILINE):
        errors.append("body is missing a '## Summary' section")

    review_by = fm.get("review_by")
    if review_by is None:
        if fm["type"] != "decision":
            errors.append("review_by is required for every type except decision")
    else:
        parsed = as_date(review_by)
        if parsed is None:
            errors.append(f"review_by is not an ISO date: {review_by!r}")
        elif parsed < date.today():
            warnings.append(f"stale: review_by {parsed.isoformat()} is in the past")

    return errors, warnings


def collect_ids(root: Path):
    """Index ids in a root without validating (used for --extra-root)."""
    ids = set()
    for path in iter_entries(root):
        fm, _, err = parse_frontmatter(path)
        if fm and not err and isinstance(fm.get("id"), str):
            ids.add(fm["id"])
    return ids


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parent.parent,
                        help="knowledge root to validate (default: this repo)")
    parser.add_argument("--extra-root", type=Path, action="append", default=[],
                        help="additional root(s) used only for id resolution")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as errors")
    parser.add_argument("--check-index", action="store_true",
                        help="fail if INDEX.md drifted from generated content")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        print(f"error: root {root} is not a directory", file=sys.stderr)
        return 1

    known_ids = set()
    for extra in args.extra_root:
        known_ids |= collect_ids(extra.expanduser().resolve())

    entries = {}   # id -> rel path (this root only, for duplicate detection)
    results = []   # (rel, errors, warnings)
    deferred_refs = []  # (rel, field, ref_id)

    for path in iter_entries(root):
        rel = path.relative_to(root).as_posix()
        fm, body, err = parse_frontmatter(path)
        if err:
            results.append((rel, [err], []))
            continue

        errors, warnings = check_entry(path, root, fm, body)

        entry_id = fm.get("id")
        if isinstance(entry_id, str):
            if entry_id in entries:
                errors.append(f"duplicate id {entry_id!r} (also in {entries[entry_id]})")
            elif entry_id in known_ids:
                errors.append(f"duplicate id {entry_id!r} (already defined in an --extra-root)")
            else:
                entries[entry_id] = rel

        for field in ("overrides", "supersedes"):
            ref = fm.get(field)
            if isinstance(ref, str):
                deferred_refs.append((rel, field, ref))
        related = fm.get("related")
        if isinstance(related, list):
            for ref in related:
                if isinstance(ref, str):
                    deferred_refs.append((rel, "related", ref))

        results.append((rel, errors, warnings))

    all_ids = known_ids | set(entries)
    ref_errors = {}
    for rel, field, ref in deferred_refs:
        if ref not in all_ids:
            ref_errors.setdefault(rel, []).append(
                f"{field} references unknown id {ref!r}")

    total_errors = total_warnings = checked = 0
    for rel, errors, warnings in results:
        checked += 1
        errors = errors + ref_errors.get(rel, [])
        for msg in errors:
            print(f"{rel}: ERROR: {msg}")
        for msg in warnings:
            print(f"{rel}: WARNING: {msg}")
        total_errors += len(errors)
        total_warnings += len(warnings)

    if args.check_index:
        from build_manifest import render_index  # local import: avoids import cycle
        index_path = root / "INDEX.md"
        expected = render_index(root)
        actual = index_path.read_text(encoding="utf-8") if index_path.exists() else None
        if actual != expected:
            print("INDEX.md: ERROR: out of date -- run "
                  "scripts/build_manifest.py --index")
            total_errors += 1

    print(f"\nChecked {checked} entries in {root}: "
          f"{total_errors} error(s), {total_warnings} warning(s).")
    if total_errors or (args.strict and total_warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

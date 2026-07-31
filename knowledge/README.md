# .knowledge — Global Knowledge Repository

Tiered context repository for agentic workflows. This is the **global** tier:
cross-project standards, patterns, runbooks, decisions, and process knowledge.
Each project carries its own **local** tier (`<repo>/.knowledge/`, scaffolded
from [`templates/local-project/`](templates/local-project/)).

Two documents govern everything here:

- [`_meta/BLUEPRINT.md`](_meta/BLUEPRINT.md) — the design: layout, schema,
  rationale, build checklist. When this repo and the blueprint disagree, fix
  the repo.
- [`_meta/PROTOCOL.md`](_meta/PROTOCOL.md) — the agent-facing read/write/GC
  rules. CLAUDE.md and all skills point here.

## Layout

| Path | Contents |
|---|---|
| `INDEX.md` | **Generated** routing table — the only file agents load eagerly |
| `MANIFEST.yaml` | **Generated** machine index for tooling |
| `_meta/` | Blueprint + protocol |
| `_schema/` | JSON Schema for entry frontmatter |
| `_templates/entry.md` | Entry template |
| `scripts/` | Tooling (below) |
| `templates/local-project/` | Copyable skeleton for a project tier |
| everything else | Entry directories, created on demand (`standards/`, `patterns/`, `mlops/`, `deployment/`, `runbooks/`, `decisions/`, `process/`, …) |

Directories start empty on purpose — entries are created when there is
something true and durable to record, not to fill a taxonomy.

## Entry schema

Markdown + YAML frontmatter. Required: `id`, `title`, `domain`, `tags`,
`type`, `scope`, `status`, `last_updated`, `verified_on` — plus `review_by`
for every type except `decision`.

- `domain`: `backend | mlops | deployment | product | ops | process`
- `type`: `standard | pattern | runbook | decision | constraint | glossary | gotcha | override | context`
- `scope`: `global | local` · `status`: `draft | active | deprecated | superseded`
- `id` is kebab-case, equals the filename stem, unique across both tiers.
- Body must contain `## Summary`; its first sentence becomes the INDEX line.
- Normative content uses RFC 2119 keywords (MUST / SHOULD / MAY).
- Freshness: `review_by = verified_on +` 90 d (runbook, context) / 180 d
  (standard, constraint, override) / 365 d (pattern, glossary, gotcha).

Full schema: [`_schema/frontmatter.schema.json`](_schema/frontmatter.schema.json).
Template: [`_templates/entry.md`](_templates/entry.md).

## Tooling

```bash
# Validate this repo (CI form adds --strict --check-index)
python scripts/validate.py

# Validate a project tier, resolving ids against this global repo
python scripts/validate.py --root <project>/.knowledge --extra-root ~/.knowledge

# Regenerate MANIFEST.yaml + INDEX.md after any entry change
python scripts/build_manifest.py --index

# Create a new entry (never hand-write frontmatter)
python scripts/new_entry.py --dir mlops/inference --id my-new-entry \
  --title "My New Entry" --domain mlops --type standard --tags kserve,gpu \
  --source docs/trd/example.md
```

Requires Python 3.10+ and PyYAML.

## Starting a new project

Preferred: `/curate init-project` (Claude Code skill — Phase 2). Manual:

```bash
cp -r ~/.knowledge/templates/local-project/.knowledge <repo>/.knowledge
python ~/.knowledge/scripts/build_manifest.py --root <repo>/.knowledge --index
```

Then add the two-line pointer to the project's CLAUDE.md and wire
`validate.py --strict --check-index` into CI.

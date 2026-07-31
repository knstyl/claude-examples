# Knowledge Protocol — agent-facing rules

> Single source of truth for reading, writing, and maintaining both knowledge
> tiers. Phase skills and CLAUDE.md point here; do not restate these rules
> elsewhere. Design rationale lives in [BLUEPRINT.md](BLUEPRINT.md).

## Tiers & precedence

- **Global:** `~/.knowledge/` — cross-project standards, patterns, runbooks,
  decisions, process.
- **Project:** `<repo>/.knowledge/` — context, decisions, constraints,
  glossary, gotchas, overrides.
- Precedence, first match wins: project `overrides/` → project entry → global
  entry. An override names its target via `overrides:` frontmatter; when you
  apply one, say so.
- Full deliverables (TRDs, design docs, discovery notes) live in
  `<repo>/docs/`, **never** in `.knowledge`. Entries distill them and link
  back via `source:`.

## Read protocol

1. **Eager:** load `INDEX.md` of the active tier(s) only — project first, then
   global. Nothing else eagerly.
2. **Just-in-time:** when the task touches an indexed topic, read the whole
   entry (entries are small). Never bulk-load a directory.
3. **Fallback:** no index hit → grep both tiers by tag/keyword before
   concluding the knowledge doesn't exist.
4. **Citation:** when an entry drives a decision, name its `id`. If it is past
   `review_by`, flag it as possibly stale when citing.

## Write protocol — propose → approve

Nothing lands in either tier without explicit human approval.

1. **Candidate test** (all four must hold): durable — matters next month?
   cross-session — not just this task? not derivable from code/git/CLAUDE.md?
   actionable when retrieved cold?
2. **Placement:** applies beyond this repo → global; else project. Contradicts
   a global entry for this repo only → `overrides/`. Contradicts a global
   entry everywhere → propose updating the global entry instead.
3. **Updating beats creating** — check for an existing entry to amend first.
   Superseding: new entry sets `supersedes:`; old entry gets
   `status: superseded`.
4. **Draft** with `~/.knowledge/scripts/new_entry.py` (never hand-write
   frontmatter), show the diff, **wait for approval**. Batch candidates into
   one approval.
5. **On approval:** `build_manifest.py --index` → `validate.py` → commit
   (global tier commits immediately; project tier rides the repo's normal
   commit flow).

## Freshness

- `verified_on` = last confirmed still true; `last_updated` = last content
  edit. Verifying without editing bumps only `verified_on` + `review_by`.
- `review_by = verified_on + interval`: runbook/context **90 d**;
  standard/constraint/override **180 d**; pattern/glossary/gotcha **365 d**;
  decision **never** (immutable record — lifecycle via `status` only).
- `validate.py` warns on overdue (`--strict` errors, for CI). Nothing is ever
  auto-deleted.

## Maintenance — `/curator gc [global | project | both]`

Monthly, or when the overdue nag exceeds ~5. Default scope: both tiers when
inside a project, global otherwise.

1. Overdue entries → verify / update / deprecate (human decides, agent drafts).
2. `status: draft` older than 30 d → propose deletion.
3. Deprecated/superseded older than 180 d → propose deletion (git history is
   the archive).
4. Dedupe scan: overlapping tags/titles → propose merge.
5. Contradiction scan: entries whose Rules conflict with each other, and
   overrides whose global target has changed since the override was written →
   propose reconcile / supersede / update-the-global.
6. Bloat: entries over ~150 lines → propose splitting; INDEX over 120 lines →
   propose consolidation.
7. Provenance gaps: decisions and gotchas without a `source:` where a
   deliverable or incident clearly exists → propose backfilling the link.
8. Present the whole proposed changeset (grouped, with rationale) for
   approval before touching anything. Orphan/drift checking is mechanical,
   not part of this sweep: INDEX/MANIFEST are generated and
   `validate.py --check-index` plus reference checks catch it.
9. Rebuild manifest + index, `validate.py --strict --check-index`, commit
   `gc: <date>` (git history is the curation log).

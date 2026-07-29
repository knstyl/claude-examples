---
name: curator
description: Knowledge curator for the tiered .knowledge system (global ~/.knowledge + <repo>/.knowledge). Owns all KB reads/writes/maintenance. Subcommands - capture (distill session into proposed entries), gc (maintenance loop), verify (re-verify overdue entries), init-project (scaffold a project tier). Use when the user asks to save/capture knowledge, mentions KB maintenance or overdue entries, wants a project knowledgebase set up, or when an SDLC phase skill reaches its closing capture step.
argument-hint: capture | gc | verify | init-project
---

# Knowledge curator

The rules live in `~/.knowledge/_meta/PROTOCOL.md` — **read it first, every
time**; this file only sequences the flows. Tooling lives in
`~/.knowledge/scripts/`. Hard rule from the protocol: **nothing lands in
either tier without explicit user approval.**

Dispatch on the argument. No argument → ask which flow.

## capture

1. Read PROTOCOL.md, then `INDEX.md` of both tiers (project first, if present).
2. Scan this session for candidates that pass the four-part test (durable,
   cross-session, not derivable from code/git/CLAUDE.md, actionable cold).
   Typical candidates: decisions made, constraints discovered, gotchas hit,
   conventions agreed. Zero candidates is a normal outcome — say so and stop.
3. For each candidate, decide placement per the protocol (global vs project vs
   `overrides/`), and check the INDEX for an existing entry to **amend
   instead of creating**.
4. Draft: new entries via `python ~/.knowledge/scripts/new_entry.py`
   (never hand-write frontmatter; use `--root <repo>/.knowledge --scope local`
   for the project tier, `--source` when distilled from a deliverable), then
   fill in the body sections. Amendments: edit the entry, bump `last_updated`
   + `verified_on`, recompute `review_by`.
5. Present all candidates as one batch — id, placement, one-line summary,
   full diff — and **wait for approval**. Drop rejected ones entirely.
6. On approval: `python ~/.knowledge/scripts/build_manifest.py --root <tier>
   --index`, then `validate.py --root <tier>` (project tier adds
   `--extra-root ~/.knowledge`). Global tier: commit immediately
   (`capture: <topic>`). Project tier: stage, but let it ride the repo's
   normal commit flow.

## gc — `[global | project | both]`

Follow PROTOCOL.md §Maintenance step by step across the chosen scope
(default: both tiers when inside a project): triage overdue entries
(recommend verify / update / deprecate per entry — the user decides), propose
deleting drafts >30 d and deprecated/superseded >180 d, scan for
near-duplicates to merge AND contradictions to reconcile (including overrides
whose global target changed), flag oversize entries (>~150 lines) to split
and INDEX over budget (120 lines), flag decisions/gotchas missing `source:`.
For cross-tier scans on a large KB, fan the reading out to a subagent and
keep only findings. Present the whole changeset grouped with rationale for
approval **before touching anything**, apply approved items, rebuild
manifest + index, run `validate.py --strict --check-index`, commit
`gc: <date>` — git history is the curation log.

## verify

Lightweight freshness pass without the full gc: list entries past `review_by`
(`validate.py` warnings). For each, check the claim against reality where
possible (code, cluster, upstream docs) and recommend confirm / update /
deprecate. On user confirmation bump `verified_on` (+ `review_by` =
verified_on + interval-by-type; intervals in PROTOCOL.md), rebuild index,
commit `verify: <date>`.

## init-project

1. Confirm the target repo root; refuse politely if a `.knowledge/` already exists.
2. `cp -r ~/.knowledge/templates/local-project/.knowledge <repo>/.knowledge`,
   then `build_manifest.py --root <repo>/.knowledge --index`.
3. Append to the project's `CLAUDE.md` (create if missing):
   two lines pointing at `.knowledge/INDEX.md` and
   `~/.knowledge/_meta/PROTOCOL.md`.
4. Ensure `<repo>/docs/` exists (deliverables live there, not in the KB).
5. **Bootstrap provisional context** (offer it; skip on request): run an
   Explore subagent over build files, module layout, key configs, deployment
   manifests, and README — subagent returns synthesized findings only, no
   file dumps in main context. From those, draft `context/` entries
   (architecture-current, integrations, environments) and glossary terms via
   `new_entry.py`. Bootstrap drafts stay `status: draft` and get `review_by`
   shortened to ~30 days out — scan-derived content is provisional until a
   human verifies it. Present the batch for approval like any capture;
   scanning doesn't exempt writes from the protocol.
6. Print the resulting `.knowledge/` tree and INDEX.md.
7. Suggest wiring `validate.py --root .knowledge --extra-root ~/.knowledge
   --strict --check-index` into the repo's CI. Don't do it unasked.

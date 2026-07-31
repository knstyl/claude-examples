# BLUEPRINT — Tiered Knowledge System + AI SDLC Workflow

> Anchor document for the build. Written 2026-07-03, after design review.
> Status: **signed off 2026-07-03** — all five open decisions confirmed at their
> recommended defaults (see §10). Phase 1 built the same day.
> Everything else in this repo conforms to this doc; when they disagree, fix the other thing.

## 0. Decisions already made (design review, 2026-07-03)

| Question | Decision |
|---|---|
| Existing 2026-07-03 scaffold | **Rebuild on it** — keep git repo + validator tooling, revise schema, cull empty stubs |
| Agent writes to KB | **Propose → human approves.** Nothing lands without sign-off |
| Freshness model | **`verified_on` + `review_by` dates, hook-driven nagging.** No confidence scores. Nothing auto-deletes |
| SDLC deliverables (TRDs, design docs) | **Live in `<repo>/docs/`.** `.knowledge` holds only the distilled residue (decisions, constraints, gotchas) linking back |

### Critiques applied to the original proposal

1. **INDEX.md must be generated, not hand-written.** A hand-maintained routing
   table is the first thing to rot. `scripts/build_manifest.py` grows an
   `--index` output that emits INDEX.md from frontmatter + each entry's
   `## Summary` first line. Humans never edit it; a validator check
   (`--check-index`) fails when it drifts.
2. **"Every skill defers to the curator skill" is not a real mechanism.**
   Skills can't invoke skills reliably. Instead: the curator skill is the
   *human* entry point (`/curate ...`), and the read/write rules live in one
   shared reference file (`_meta/PROTOCOL.md`) that every phase skill links to
   and CLAUDE.md points at. Single source of truth, no fake delegation.
3. **The 60 empty draft stubs get deleted.** An aspirational taxonomy is rot
   on day one: it bloats the index, teaches agents that entries are usually
   empty, and misstates what we actually know. Directories are recreated on
   demand by `/curate capture`.
4. **PRDs move out of `.knowledge`.** The existing local-project template put
   `product/prd/` inside the KB — conflicts with the deliverables decision.
   Full artifacts → `docs/`; the KB keeps a pointer entry + distilled
   decisions/constraints.
5. **Capture reminders can't be a deterministic hook.** "Did this session
   learn something durable?" is judgment. Hooks do only the deterministic
   part (validate on write, freshness nag on session start); capture is the
   mandatory closing step of every phase skill, plus `/curate capture` on
   demand.

---

## 1. Directory layout

### Global tier — `~/.knowledge/` (git repo)

```
~/.knowledge/
├── INDEX.md                  # GENERATED routing table — the ONLY eagerly-loaded file
├── MANIFEST.yaml             # GENERATED machine index (tooling, not agents)
├── README.md                 # human onboarding
├── _meta/
│   ├── BLUEPRINT.md          # this file
│   └── PROTOCOL.md           # read/write/GC rules — single source of truth
├── _schema/frontmatter.schema.json
├── _templates/entry.md
├── scripts/                  # validate.py, build_manifest.py (+ --index), new_entry.py
├── standards/                # prescriptive rules (java-spring, api-design, security, containers)
├── patterns/                 # reusable designs (architectural, resilience, integration)
├── mlops/                    # inference, pipelines, monitoring
├── deployment/               # progressive-delivery, gitops, ci
├── runbooks/                 # operational procedures
├── decisions/                # org-/career-wide ADRs (adr-NNNN-slug.md)
├── process/                  # NEW — SDLC ways-of-working: how I run discovery, TRDs, delivery
└── templates/local-project/  # copyable skeleton for a project tier
```

### Project tier — `<repo>/.knowledge/` (committed with the repo)

```
<repo>/
├── docs/                     # FULL deliverables: TRDs, design docs, discovery notes
│   └── trd/, design/, discovery/
└── .knowledge/
    ├── INDEX.md              # GENERATED — only eagerly-loaded file for this tier
    ├── MANIFEST.yaml         # GENERATED
    ├── context/              # architecture-current, integrations, environments, data-model
    ├── decisions/            # project ADRs (adr-NNNN-slug.md)
    ├── constraints/          # SLOs, budgets, compliance, hard technical constraints
    ├── glossary/             # domain terms — one file, or one-per-letter if it grows
    ├── gotchas/              # hard-won surprises: "X looks like Y but isn't, because Z"
    ├── product/              # distilled roadmap + stakeholders (NOT full PRDs — those → docs/)
    └── overrides/            # per-project deviations from global entries (`overrides:` key)
```

**Precedence (first match wins):** local `overrides/` → local entry → global entry.

---

## 2. Naming conventions

- `id` = kebab-case = filename stem, unique across **both tiers combined**.
- ADRs: `adr-NNNN-short-slug.md`, numbered per tier, never renumbered.
- One concept per entry. Target < 120 lines; split when bigger.
- Directories are lowercase kebab-case, max two levels deep under the tier root.
- Generated files (`INDEX.md`, `MANIFEST.yaml`) carry a `<!-- GENERATED -->` header.

---

## 3. Entry schema (frontmatter)

Delta from the existing `_schema/frontmatter.schema.json` — evolution, not rewrite:

| Field | Status | Notes |
|---|---|---|
| `id, title, domain, tags, type, scope, status` | keep, required | as today |
| `last_updated` | keep, required | bumped on **content** change |
| `verified_on` | **ADD**, required | date content was last confirmed true (≠ edited) |
| `review_by` | keep, **promote to required** | = `verified_on` + interval-by-type (see §6) |
| `source` | **ADD**, optional | path/URL to the deliverable this was distilled from (`docs/trd/...`) |
| `domain` vocab | **extend** | add `process` to `backend\|mlops\|deployment\|product\|ops` |
| `type` vocab | **extend** | add `gotcha`; **drop `prd`** (PRDs no longer live in the KB) |
| `version, owner, applies_to, overrides, supersedes, related` | keep, optional | as today |

Body contract (unchanged): `## Summary` required — 2–3 self-contained sentences;
it feeds the generated INDEX line. RFC 2119 keywords in `## Rules`.

---

## 4. Read protocol

1. **Eager:** load `INDEX.md` of the active tier(s) only. Project sessions load
   both indexes (project first). Hard budget: each INDEX ≤ ~120 lines; the
   generator warns beyond that — that's the GC trigger, not a reason to widen.
2. **Just-in-time:** when the task touches an indexed topic, read the whole
   entry (entries are small by design). Never bulk-load a directory.
3. **Precedence:** local override → local → global. An override entry names its
   global target via `overrides:`; agents must apply the override and say so.
4. **Fallback:** if the index has no hit, grep both tiers by tag/keyword before
   concluding the knowledge doesn't exist.
5. **Citation discipline:** when an entry drives a decision, name the `id` in
   the response. If an entry is past `review_by`, flag it as possibly stale
   when citing.

## 5. Write protocol (propose → approve)

Writes happen **only** through the curator flow (`/curate capture`, or the
capture step every phase skill ends with):

1. **Candidate test** — all four must hold: durable (matters next month)?
   cross-session (not just this task)? not derivable from code/git/CLAUDE.md?
   actionable when retrieved cold?
2. **Placement** — applies beyond this repo → global; else project.
   Contradicts a global entry for this repo only → `overrides/`.
   Contradicts a global entry, period → propose *updating the global entry*.
3. **Draft** via `scripts/new_entry.py` (never hand-write frontmatter), show
   the diff, **wait for approval**. Batch multiple candidates in one approval.
4. **On approval:** write → `build_manifest.py --index` → `validate.py` →
   git commit (global tier commits immediately; project tier rides the repo's
   normal commit flow).
5. Updating beats creating: check for an existing entry to amend first.
   Superseding: new entry sets `supersedes:`, old one gets `status: superseded`.

## 6. Freshness model

- `verified_on` = last time a human/agent confirmed the content is still true.
  `last_updated` = last content edit. Verifying without editing bumps only
  `verified_on` + `review_by`.
- `review_by = verified_on + interval(type)`:

| type | interval | rationale |
|---|---|---|
| runbook, context | 90 d | describes live systems — rots fastest |
| standard, constraint | 180 d | policy-ish, changes with stack decisions |
| pattern, glossary, gotcha | 365 d | conceptual, slow-moving |
| decision (ADR) | none | immutable record; lifecycle via `status` only |

- Enforcement: `validate.py` warns on overdue (`--strict` errors, for CI);
  a **SessionStart hook** prints a one-line nag ("KB: 3 entries overdue")
  when overdue > 0, silent otherwise. Nothing auto-deletes, ever.

## 7. Maintenance / GC loop — `/curate gc`

Run monthly, or when the nag exceeds ~5 overdue. Steps, in order:

1. **Overdue entries** → for each: verify (bump `verified_on`) / update /
   `status: deprecated`. Human decides; agent drafts the recommendation.
2. **Empty or stale drafts** (`status: draft`, > 30 d old) → propose deletion.
3. **Deprecated/superseded > 180 d** → propose deletion (git history is the archive).
4. **Dedupe scan** — entries with overlapping tags/titles → propose merge.
5. **Index budget** — INDEX over ~120 lines → propose consolidation or culling.
6. Rebuild manifest + index, `validate.py --strict`, commit `gc: <date>`.

---

## 8. Claude Code primitive mapping

| Primitive | Use | Not used for |
|---|---|---|
| **Skills** (`~/.claude/skills/`, personal → cross-project) | `curator` (subcommands: capture / gc / verify / init-project) + one skill per SDLC phase: `discover`, `design-doc`, `trd`, `implement`, `deliver`. Each phase skill = playbook + templates in `references/`, ends with the capture step | storing knowledge (that's the KB's job) |
| **Subagents** | context-heavy read phases: discovery research, codebase archaeology, cross-tier KB audits during `gc`. Return distilled findings to main context | deliverable writing (TRD drafting stays in main context where you're steering) |
| **Hooks** | *Deterministic only:* ① PostToolUse on Edit/Write under `**/.knowledge/**` → run `validate.py` + index rebuild; ② SessionStart → overdue-count nag | capture judgment, content quality |
| **CLAUDE.md** | user-level: ~5 lines — read protocol pointer to `_meta/PROTOCOL.md` + global INDEX path. Project-level: 2 lines — pointer to `<repo>/.knowledge/INDEX.md` | inlining knowledge content |

---

## 9. Build checklist (the anchor for all later steps)

### Phase 1 — Reconcile the existing scaffold ✅ 2026-07-03
- [x] 1.1 Update `_schema/frontmatter.schema.json` (add `verified_on`, `source`; require `review_by` except for decisions; vocab: +`process` domain, +`gotcha` type, −`prd` type)
- [x] 1.2 Update `_templates/entry.md` to match
- [x] 1.3 Extend `scripts/build_manifest.py` with `--index` → generates `INDEX.md` (grouped by type, one line per entry from Summary first sentence; `<!-- GENERATED -->` header; warn > 120 lines; content is a pure function of entries — no timestamps — so drift checks don't fire on date rollover)
- [x] 1.4 Update `scripts/validate.py`: `verified_on`/`review_by` checks, `--check-index` drift check, `_meta`/`INDEX.md` exclusions
- [x] 1.5 Update `scripts/new_entry.py`: interval-by-type `review_by`, `--source`, gotcha sections
- [x] 1.6 Cull all 51 empty draft stubs (taxonomy preserved in initial commit `be7d33f`)
- [x] 1.7 Write `_meta/PROTOCOL.md` (§4–§7 of this doc, agent-facing, terse)
- [x] 1.8 Rework `templates/local-project/`: empty-dir skeleton with `gotchas/`, no `product/prd/`, README pointing deliverables to `docs/`
- [x] 1.9 Rewrite `README.md`; generate `INDEX.md`; end-to-end toolchain test passed; commit `9f4b620`
- [ ] 1.10 Push to private GitHub remote — **blocked: `gh` CLI not installed.** Install + `gh auth login`, then `gh repo create knowledge --private --source ~/.knowledge --push`

### Phase 2 — Claude Code wiring ✅ 2026-07-03
- [x] 2.1 `~/.claude/skills/curator/` — SKILL.md with capture/gc/verify/init-project flows
- [x] 2.2 Phase skills: `discover`, `design-doc`, `trd`, `implement`, `deliver` — playbooks with KB-read preamble + capture postamble; deliverable templates in `references/` (implement has none by design — its deliverable is code)
- [x] 2.3 Hooks in `~/.claude/settings.json` (exec-form `python` + args, Windows-safe): PostToolUse Edit|Write → `scripts/hook_validate.py` (rebuilds INDEX/MANIFEST + validates, exit-2 feedback; live-fire proven); SessionStart → `scripts/hook_freshness.py` (overdue nag, pipe-tested; fires from next session)
- [x] 2.4 User CLAUDE.md: 9-line knowledge section (read protocol, write discipline, skill map)
- [x] 2.5 Memory updated

### Phase 3 — Pilot & harden
- [ ] 3.1 Run `/curate init-project` on one real repo
- [ ] 3.2 Author 5–10 real entries via `/curate capture` (retire the stub content debt)
- [ ] 3.3 Run one full `/curate gc` cycle; fix friction found
- [ ] 3.4 Wire `validate.py --strict` into that repo's CI

---

## 10. Open decisions — ALL CONFIRMED at defaults, 2026-07-03

1. **Global repo remote** — ✅ yes, private GitHub remote (pending `gh` install, see 1.10).
2. **Phase-skill granularity** — ✅ five separate skills (`discover`,
   `design-doc`, `trd`, `implement`, `deliver`); shared discipline in PROTOCOL.md.
3. **SessionStart nag scope** — ✅ user-level hook, silent when nothing overdue.
4. **Stub cull scope** — ✅ delete all empty drafts; recreate on demand
   (taxonomy preserved in initial commit).
5. **Deliverable templates ownership** — ✅ each skill's `references/`;
   `_templates/` keeps only `entry.md`.

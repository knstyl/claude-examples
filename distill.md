# /distill — End-of-session knowledge distillation
# Install: save as .claude/commands/distill.md (per-repo) or ~/.claude/commands/distill.md (global)
# Usage: run `/distill` before /clear, /compact, or quitting a session.

You are closing out this working session. Distill what happened into the
persistent knowledge base so the next session (possibly weeks from now, in a
fresh context) can pick up without rescanning the repo.

## Targets

- **Per-project knowledge:** `.knowledge/` in this repo (create if missing)
  - `context.md` — durable facts about this repo
  - `journal.md` — append-only session log
- **Global knowledge:** `~/.knowledge/patterns.md` — only for insights that
  generalize beyond this repo

## Step 1 — Review the session

Scan the full conversation and identify:

1. **Decisions made** — and the rationale, especially options that were
   *rejected* and why (rejected options are the most expensive thing to
   re-litigate later)
2. **Repo facts learned** — architecture, module boundaries, entry points,
   build/test commands, gotchas, "X looks like it does Y but actually does Z"
3. **Changes shipped** — what was modified, at the level of intent, not diffs
   (git already has the diffs)
4. **Open threads** — what was in flight, next concrete step, any state that
   exists only in this conversation (e.g., a hypothesis half-tested)
5. **Generalizable patterns** — anything true across the platform, not just
   this repo

## Step 2 — Update `.knowledge/context.md` (edit, don't append)

This file is a living map, not a log. Rules:

- **Dedupe against existing content.** If a fact is already there, update it
  in place rather than adding a near-duplicate.
- **Correct, don't accumulate.** If the session invalidated something in the
  file, fix or delete it. Stale context is worse than no context.
- **Durable facts only.** No dates-of-work, no "currently debugging X" — that
  goes in the journal.
- **Keep it under ~150 lines.** If it's growing past that, compress the
  oldest, least-referenced material.

Suggested structure:

```
# <repo> — working context
## Architecture map (entry points, module boundaries, key seams)
## Conventions & commands (build, test, deploy, local quirks)
## Decisions log (decision → rationale → rejected alternatives)
## Gotchas (things that will bite a fresh session)
```

## Step 3 — Append to `.knowledge/journal.md`

One dated block per session, 5–10 lines max:

```
## 2026-07-30 — <session name / branch>
- Did: ...
- Learned: ...
- Open: <next concrete step; anything only this conversation knew>
```

The `Open:` line is the resume hook — write it so a fresh session could act
on it without asking questions.

## Step 4 — Promote to global (sparingly)

If something in step 1.5 applies platform-wide (a Resilience4j pattern, a
federation schema convention, a CI quirk shared by all repos), add it to
`~/.knowledge/patterns.md` with a one-line note on which repo it came from.
High bar: when in doubt, leave it per-project.

## Step 5 — Report back

End with a short summary to the user: what you wrote where, what you
corrected/deleted as stale, and the `Open:` line verbatim so they can
sanity-check it before the context disappears.

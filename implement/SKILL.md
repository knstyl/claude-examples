---
name: implement
description: SDLC implementation phase - build against an approved TRD with knowledge-informed discipline. Use when the user says "implement the TRD", "build this per the spec", or starts implementation of a designed/spec'd feature. Not for ad-hoc small fixes.
argument-hint: <TRD path or topic>
---

# Implementation playbook

**KB preamble:** read `<repo>/.knowledge/INDEX.md` (if present) and
`~/.knowledge/INDEX.md`. Before writing code, explicitly read the project's
`gotchas/` and `constraints/` entries plus applicable global `standards/` —
this is where past pain pays off. Cite entry ids; flag stale ones.

Input: the approved TRD (`docs/trd/`). Without one, confirm the user wants
TRD-less implementation and note which requirements are being assumed.

1. **Plan against the TRD** — map each R-/N- requirement to the code that
   will satisfy it. Requirements nothing maps to = plan gap; code no
   requirement demands = scope creep. Surface both before starting.
2. **Tasks** — write `docs/tasks/<slug>.md` from
   [references/tasks.md](references/tasks.md): smallest independently
   verifiable increments, dependency-ordered, riskiest or most-load-bearing
   first so bad news arrives early. Each task names the R-/N- ids it
   advances and its done-check; mark parallelizable ones `[P]`. Check tasks
   off as they complete — this file, not chat, is the resumable state of
   the build.
3. **Build** — match the codebase's existing idioms over global standards
   when they conflict — then flag the conflict for capture rather than
   silently picking. Tests ride along with each task, asserting the
   acceptance criteria from the TRD, not just "it runs", and naming the
   R-/N- ids they cover (test name or comment) so coverage is greppable.
4. **Verify** — before declaring done, exercise the change end-to-end
   (the /verify skill), then check every acceptance criterion in the TRD
   and report each as met / not met / deferred — no hand-waving.
5. **Record deviations** — where implementation diverged from the TRD,
   update the TRD (it's a living doc until delivery) and note why.

**Capture postamble:** run the curator capture flow. Implementation is the
richest gotcha source — anything that cost >30 minutes of surprise is a
candidate.

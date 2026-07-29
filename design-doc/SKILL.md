---
name: design-doc
description: SDLC design phase - turn a discovered problem into a compared set of options and a recommended design with explicit decisions and risks. Use when the user says "design doc", "how should we build X", "options for", or after a discovery doc exists. Produces docs/design/<topic>.md.
argument-hint: <topic, ideally with a discovery doc in docs/discovery/>
---

# Design-doc playbook

**KB preamble:** read `<repo>/.knowledge/INDEX.md` (if present) and
`~/.knowledge/INDEX.md`; pull relevant entries just-in-time per
`~/.knowledge/_meta/PROTOCOL.md` — especially `patterns/`, `standards/`,
`constraints/`, and `overrides/`. Cite entry ids that drive choices; flag
stale ones.

Input: the requirements doc (`docs/requirements/<slug>.md`) and/or discovery
doc (`docs/discovery/<slug>.md`) — check their Handoff sections for blockers.
If neither exists, run /elicit or /discover first, or confirm the user
accepts designing without them. Keep the same `<slug>` for your output.
Scan the input docs for `[NEEDS CLARIFICATION: …]` markers before starting:
each blocking one gets resolved with the user or explicitly accepted as a
risk in the doc — never silently designed over.

1. **Requirements recap** — a few lines restating what the design must
   satisfy, pulled from discovery. Every option is judged against these.
2. **Options — at least two real ones.** A strawman doesn't count; each
   option must be something a competent engineer might actually pick.
   Include "do nothing / buy instead of build" when plausible. For each:
   sketch, how it meets the requirements, cost/complexity, failure modes,
   operational burden.
3. **Recommendation** — pick one, say why in terms of the requirements and
   constraints, and name what you're deliberately trading away. End with a
   **KB compliance** line: which standards/constraints the pick satisfies
   (by entry id) and any deliberate deviation — each deviation is an
   override or ADR candidate at capture, not a silent exception.
4. **Decisions** — each load-bearing choice gets a one-line decision record
   in the doc; ones with long-term consequence are ADR candidates for the
   KB (`decisions/`, via curator capture — don't write ADRs inline here).
5. **Risks & unknowns** — what could invalidate this design, and the
   cheapest probe (spike, prototype, load test) to retire each big one.
6. **Write** `docs/design/<topic>.md` from
   [references/design-doc.md](references/design-doc.md). Keep it skimmable;
   an unread design doc is a failed one.

**Capture postamble:** run the curator capture flow (ADR-worthy decisions and
newly discovered constraints; entries link back via `source:`).

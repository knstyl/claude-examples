---
name: trd
description: SDLC requirements phase - turn an accepted design into a Technical Requirements Document with numbered RFC-2119 requirements, NFRs, acceptance criteria, and a rollout plan. Use when the user says "TRD", "requirements doc", "spec this out", or after a design doc is accepted. Produces docs/trd/<topic>.md.
argument-hint: <topic, ideally with an accepted design in docs/design/>
---

# TRD playbook

**KB preamble:** read `<repo>/.knowledge/INDEX.md` (if present) and
`~/.knowledge/INDEX.md`; pull relevant entries just-in-time per
`~/.knowledge/_meta/PROTOCOL.md` — `standards/` and `constraints/` become
requirements here, so check them explicitly. Cite entry ids; flag stale ones.

Input: the accepted design (`docs/design/`). A TRD without a design decision
behind it is speculation — push back if asked to skip ahead. Scan the design
and requirements docs for `[NEEDS CLARIFICATION: …]` markers: each one is
either resolved now or becomes an Open-question row — none survive inside
requirement text.

1. **Scope** — one paragraph on what this TRD covers, plus explicit
   out-of-scope. Out-of-scope kills more scope-creep than any review.
2. **Requirements** — numbered (`R-1`, `R-2`, …), each independently
   testable, using MUST / SHOULD / MAY (RFC 2119) precisely. One behavior
   per requirement, phrased in an EARS pattern: ubiquitous ("the service
   MUST …"), event-driven ("WHEN <trigger>, the service MUST …"),
   state-driven ("WHILE <state>, …"), unwanted-behavior ("IF <failure>,
   THEN the service MUST …"), optional-feature ("WHERE <flag>, …"). The
   template forces trigger and response apart and makes untestable phrasing
   obvious. IDs are permanent — never renumber; tasks and tests reference
   them. Applicable KB standards become requirements by reference
   ("MUST follow [entry-id]"), not by copy-paste.
3. **Non-functional requirements** — numbered `N-1…`: latency, throughput,
   availability, security, observability, cost. Numbers, not adjectives;
   pull targets from the project's `constraints/` entries.
4. **Acceptance criteria** — for each R/N, how a reviewer verifies it:
   test, demo, dashboard, load run. Behavioral criteria read as
   Given/When/Then so they translate directly into tests. If you can't
   state the check, the requirement isn't done being written.
5. **Rollout & rollback** — how this reaches production (env promotion,
   canary/progressive delivery, feature flags), the abort criteria, and
   the rollback path. Migrations get an explicit reversibility note.
6. **Open questions** — with owners. A TRD can ship with open questions;
   it can't ship with hidden ones.
7. **Write** `docs/trd/<topic>.md` from [references/trd.md](references/trd.md).

**Capture postamble:** run the curator capture flow (constraints formalized
here, standards gaps found; entries link back via `source:`).

---
name: discover
description: SDLC discovery phase - frame a problem, interrogate the current state, surface constraints and unknowns before any design work. Use when starting something new, when the user says "discovery", "explore this problem", "should we build X", or when a request is too fuzzy to design against. Produces docs/discovery/<topic>.md.
argument-hint: <topic or problem statement>
---

# Discovery playbook

**KB preamble:** read `<repo>/.knowledge/INDEX.md` (if present) and
`~/.knowledge/INDEX.md`; pull relevant entries just-in-time per
`~/.knowledge/_meta/PROTOCOL.md`. Cite entry ids that shape the framing;
flag any entry past `review_by` as possibly stale.

Goal: end with the problem understood well enough that design can start —
not with a solution. Resist proposing architecture during discovery.

1. **Frame** — restate the problem in one paragraph: who hurts, how badly,
   what happens if we do nothing. Separate the *ask* from the *need*; they
   often differ. Confirm the framing with the user before digging.
2. **Current state** — archaeology on whatever exists: code, deployment
   manifests, dashboards, prior docs/ADRs. For codebase sweeps, use an
   Explore subagent and keep only the conclusions. Record what is *true
   today*, not what docs claim.
3. **Stakeholders & questions** — list who must be consulted and the
   specific questions only they can answer. These become the open-questions
   section, not blockers to finishing the doc.
4. **Constraints** — hard limits first (SLOs, budgets, compliance, team
   capacity, deadlines), preferences second. Check `constraints/` and
   `gotchas/` in the project KB before rediscovering them.
5. **Success criteria** — how we'd know the problem is solved, measurable
   where possible. Plus explicit non-goals.
6. **Write** `docs/discovery/<topic>.md` from
   [references/discovery-notes.md](references/discovery-notes.md).

Marker discipline: anything you had to assume to keep moving gets an inline
`[NEEDS CLARIFICATION: <question>]` marker in the doc, never silent prose —
downstream phases scan for these and must not gate past a blocking one.

**Capture postamble:** run the curator capture flow (constraints and gotchas
discovered here are prime KB candidates; the discovery doc itself stays in
`docs/`, entries link to it via `source:`).

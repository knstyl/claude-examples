---
name: deliver
description: SDLC delivery phase - take implemented work to production safely and close the loop. Use when the user says "ship it", "deploy", "release", "rollout plan", or when implementation is verified and ready for production. Produces docs/delivery/<topic>.md and runbook updates.
argument-hint: <topic or release>
---

# Delivery playbook

**KB preamble:** read `<repo>/.knowledge/INDEX.md` (if present) and
`~/.knowledge/INDEX.md`; pull `runbooks/`, `deployment/`, and the project's
`constraints/` entries just-in-time per `~/.knowledge/_meta/PROTOCOL.md`.
Cite entry ids; flag stale ones.

Input: verified implementation + the TRD's rollout section. Delivery
executes what the TRD promised; renegotiate the TRD rather than improvising.

1. **Pre-flight** — work through
   [references/delivery-checklist.md](references/delivery-checklist.md):
   acceptance criteria all met, migrations reversible, dashboards and
   alerts in place, rollback rehearsed (or consciously waived), owners
   available during rollout.
2. **Progressive rollout** — follow the TRD plan (canary analysis, traffic
   steps, abort thresholds). Abort criteria are decided *before* rollout
   starts; mid-rollout is too late to negotiate with yourself.
3. **Observe** — watch the metrics the TRD named through the full soak
   window before declaring success. "Deployed" and "delivered" differ by
   one incident.
4. **Close the loop** — write `docs/delivery/<topic>.md` (filled checklist +
   outcome + any incidents), naming any R-/N- ids waived or deferred at
   delivery and why, update or create the affected runbooks, mark the TRD
   approved-as-delivered.
5. **Micro-retro** — three questions with the user: what surprised us, what
   would we do differently, what should the KB remember.

**Capture postamble:** run the curator capture flow — retro output, runbook
deltas, and rollout gotchas are the candidates; entries link back via
`source:`.

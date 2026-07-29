---
name: elicit
description: SDLC requirements-elicitation phase - drive ambiguity out of a feature ask through targeted questioning before any design happens. Use when an ask is too vague to design against ("add caching", "make it faster", "we need an API for X"), when the user says "requirements", "pin down what we need", "what should this actually do", or right after /discover. NOT for formalizing requirements after a design exists - that is /trd.
argument-hint: <feature ask or docs/discovery/<slug>.md>
---

# Requirements-elicitation playbook

**KB preamble:** read `<repo>/.knowledge/INDEX.md` (if present) and
`~/.knowledge/INDEX.md`; pull the project's `constraints/` and `glossary/`
entries before questioning — don't ask the user what the KB already answers.
Rules: `~/.knowledge/_meta/PROTOCOL.md`. Cite entry ids; flag stale.

**Input:** a problem brief (`docs/discovery/<slug>.md`) or a raw ask. A raw
ask that is really a whole problem space → run /discover first. **Output:**
`docs/requirements/<slug>.md` from
[references/requirements.md](references/requirements.md) — structured
requirements + resolved decisions + open questions. Keep the same `<slug>`
across all phase artifacts for this feature.

The job is to make ambiguity visible and then kill it, one dimension at a
time. Never accept a vague ask at face value; never pad the doc with
requirements nobody stated. Question like a lead engineer: propose a
concrete default and ask for confirmation, don't ask open-ended essay
questions. Batch related questions (AskUserQuestion, ≤4 at a time).

Work the six dimensions in order — each produces rows in the doc:

1. **Actors & scope** — who/what calls this, who operates it, where the
   boundary sits. Sharpest scope tool: "what is explicitly OUT?"
2. **Assumptions** — surface what everyone is silently assuming (traffic
   levels, data shapes, auth context, environment) and get each one
   confirmed or killed. Unconfirmed assumptions become open questions, not
   facts.
3. **Constraints** — hard limits first (SLOs, budgets, compliance, deadlines,
   team capacity), then preferences. Check the KB's `constraints/` before
   asking; new ones found here are prime capture candidates.
4. **Functional expectations & edge cases** — for each behavior, probe the
   standard failure set: empty input, duplicate, too-large, concurrent,
   partial failure, retry/idempotency, out-of-order. "What should happen
   when X fails?" beats "any edge cases?"
5. **Non-functionals** — latency, throughput, availability, security,
   observability, cost. Numbers, not adjectives: "fast", "secure", and
   "simple" get quantified on the spot or explicitly deferred with an owner.
6. **Success criteria** — how we'll know it worked, measurable where
   possible, plus explicit non-goals.

Recording discipline: every ambiguity resolved during questioning becomes a
row in **Resolved decisions** (with rationale — this table is the doc's real
value); everything still open goes to **Open questions** with an owner and a
blocks-design? flag. Nothing resolved lives only in chat. Where you proposed
a default the user hasn't confirmed yet, write it into the doc with an inline
`[NEEDS CLARIFICATION: <question>]` marker rather than as fact — /design-doc
scans for these and won't silently design over a blocking one.

Finish: fill the **Handoff** section (state, recommended next phase —
usually /design-doc — and which open questions block it).

**Capture postamble:** run the curator capture flow — constraints and domain
terms surfaced here are prime KB candidates; entries link back via `source:`.

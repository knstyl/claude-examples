---
# ── Required ────────────────────────────────────────────────
id: entry-id-here                     # Globally unique, kebab-case, MUST match filename stem
title: "Human-Readable Title"
domain: mlops                          # backend | mlops | deployment | product | ops | process
tags: [tag-one, tag-two]               # Non-empty list, kebab-case
type: standard                         # standard | pattern | runbook | decision | constraint | glossary | gotcha | override | context
scope: global                          # global | local
status: draft                          # draft | active | deprecated | superseded
last_updated: 2026-07-03               # ISO date; bump on every CONTENT change
verified_on: 2026-07-03                # ISO date; bump when content is confirmed still true
review_by: 2027-01-03                  # verified_on + interval-by-type (runbook/context 90d,
                                       # standard/constraint/override 180d, pattern/glossary/gotcha 365d).
                                       # Omit ONLY for type: decision.

# ── Optional ────────────────────────────────────────────────
source: docs/trd/example.md            # Deliverable this was distilled from (path or URL)
version: 1                             # Bump on breaking content changes
owner: platform-team                   # Team or person accountable for accuracy
applies_to:                            # Tech/version scoping for retrieval filtering
  - kserve: ">=0.13"
overrides: null                        # (local override entries only) global id this replaces
supersedes: null                       # Prior entry id this replaced
related: []                            # Cross-references by id
---

# Human-Readable Title

## Summary
<!-- 2–3 sentences, fully self-contained. The FIRST sentence becomes this
     entry's line in the generated INDEX.md — make it carry the routing signal.
     Assume nothing else is in context. -->

## When to apply
<!-- Trigger conditions, and when NOT to apply. -->

## Rules
<!-- Normative content. Use MUST / SHOULD / MAY (RFC 2119) so agents and
     linters can distinguish hard requirements from preferences. -->

## Examples
<!-- Minimal, correct, copy-pasteable. One good example beats three partial ones. -->

## Anti-patterns
<!-- Known mistakes and why they fail. -->

## References
<!-- External links, upstream docs, related entries as [[entry-id]]. -->

# TRD: <topic>

- **Date:** <YYYY-MM-DD> · **Author:** <name> · **Status:** draft | in review | approved
- **Design:** <link to docs/design/...> · **Related KB:** <entry ids>

## Scope

<What this covers.>

### Out of scope

## Requirements

<!-- EARS patterns: ubiquitous "The service MUST …" · event "WHEN <trigger>, …" ·
     state "WHILE <state>, …" · error "IF <failure>, THEN …" · feature "WHERE <flag>, …".
     IDs are permanent — never renumber; tasks and tests reference them. -->

| ID | Requirement (RFC 2119 + EARS) | Acceptance criterion (Given/When/Then where behavioral) |
|---|---|---|
| R-1 | WHEN <trigger>, the service MUST … | Given … When … Then … |

## Non-functional requirements

| ID | Requirement | Target | Acceptance criterion |
|---|---|---|---|
| N-1 | p99 latency | ≤ … ms | <load run/dashboard> |

## Interfaces & data

<API contracts, schemas, events — or links to them.>

## Rollout & rollback

- **Path to prod:** <envs, canary/progressive delivery, flags>
- **Abort criteria:** <metrics/thresholds>
- **Rollback:** <procedure; migration reversibility>

## Open questions

| # | Question | Owner | Blocks approval? |
|---|---|---|---|

## Handoff

- **State:** <approved / in review / blocked on #…>
- **Next phase:** /implement <slug>
- **Notes for next phase:** <1–3 lines>

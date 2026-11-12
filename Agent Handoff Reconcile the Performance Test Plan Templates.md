# Agent Handoff: Reconcile the Performance Test Plan Templates

Nov 10, 2026 · @Sam

## 1. Task

Produce one performance test plan template for the Viaduct service by merging two documents: the team's existing template, which has been in use for years, and a newer best-practice draft. The existing template is the base. The draft is a source of improvements to fold into it.

The reason for this order: the existing template carries the organisation's mandated sections, approval steps, terminology and reporting format, and people across the org already know how to read it. The draft was written without sight of it, from general industry practice. It is stronger on method but knows nothing about what the org requires.

The finished template will drive four things: how tests are run, which metrics are captured in New Relic, Observe and Splunk, how results are validated and reported to leadership, and how risky production releases are approved. It is read and filled in by engineers and reviewed by leadership, so it must stay a human document.

## 2. Inputs

Read all of these in full before changing anything. If one is missing or unreadable, stop and say so.

| Input | Location | How to treat it |
| --- | --- | --- |
| Existing template | \[path or link\] | The base. Authoritative for structure, terminology, mandated content and approvals |
| Best-practice draft | [Viaduct Service Performance Test Plan (Template)](https://claude.ai/artifact/YLhAhUQ7G2SjSMEEapXZKX), exported to Markdown at \[path\] | Source of improvements. Its bracketed numbers are placeholders, not targets |
| Org and team requirements | Section 4 of this brief | Overrides both documents |
| Org standards the template must follow | \[links: observability standards, release policy, SLO policy\] | Authoritative where they apply |
| Past filled-in plans or reports, if available | \[path or link\] | Evidence of how the template is used in practice |

**Service context.** Viaduct is a multi-tenant GraphQL service on Kotlin, Ktor (Jetty) and Guice. It resolves all data from downstream REST APIs through a shared gateway client module, uses scoped serving, and relies heavily on reentrant subqueries. It is moving from greenfield toward production with a few tenant modules onboarded, and expects to grow to 50–100+ downstream APIs. Traces go primarily to New Relic through OpenTelemetry.

## 3. Precedence

When sources disagree, the higher row wins. When the right row is unclear, do not choose: record it as a conflict for Sam (section 7).

| Rank | Source | Wins on |
| --- | --- | --- |
| 1 | Requirements in section 4 and linked org standards | Everything they cover |
| 2 | Existing template | Section order and names, terminology, approval and sign-off steps, report format, named roles, any numeric target or threshold already in use |
| 3 | Best-practice draft | Method: test types, measurement rules, validation checks, metrics catalogue, risk tiering, canary and rollback criteria |
| 4 | Your own knowledge | Nothing. Use it to spot gaps and raise them, not to add content |

**How this plays out in common cases**

- **Existing has it, draft does not:** keep it unchanged. Longevity suggests someone needs it.
- **Draft has it, existing does not:** add it in the most natural existing section, and log it as an addition.
- **Both cover it and agree:** keep the existing wording; tighten only if the draft is clearly more precise.
- **Both cover it, draft is stronger on method:** merge, keeping the existing terms and layout, and log what changed.
- **Both cover it and contradict:** leave the existing content in place and log a conflict with both versions quoted.
- **Numbers:** an existing number always stands. A draft placeholder never replaces it. Where the existing template has no number, keep the draft's bracketed placeholder as a placeholder.
- **Tool roles:** the draft's split of duties between New Relic, Splunk and Observe is an unconfirmed proposal. The existing template or org standard decides; if neither does, log it as an open question.
- **Terminology:** where the two use different words for the same thing, use the existing term throughout and note the mapping once in the change log.

## 4. Org and team requirements to honour

These override both documents. Sam completes this list before the handoff; an item left in brackets is unknown, and the agent treats it as an open question, not as permission to decide.

- [ ] Sections or headings that must appear, in a fixed order: \[list\]
- [ ] Approval and sign-off roles, and the forum where release decisions are made: \[list\]
- [ ] Required format and cadence for leadership reporting: \[describe\]
- [ ] What each of New Relic, Observe and Splunk is officially used for: \[describe\]
- [ ] SLO, SLA or threshold values already agreed with consumers or leadership: \[list\]
- [ ] Risk classification or change-management scheme releases must map to: \[name and link\]
- [ ] Mandated load-testing tool, environments, or test windows: \[list\]
- [ ] Data-handling, security or compliance rules for test data and environments: \[list\]
- [ ] Team conventions the existing template encodes that are not written down elsewhere: \[list\]
- [ ] Anything in the existing template known to be outdated and safe to retire: \[list\]

## 5. Best-practice findings that must survive

Each finding below must appear in the reconciled template, in the existing template's terms, or be logged as a conflict with the requirement that blocks it. None may be dropped silently. They are the reason for doing this merge.

| Area | Finding | Why it matters for this service |
| --- | --- | --- |
| Objectives | Targets set per operation class (simple, fan-out, reentrancy-heavy), not one global number | Query cost varies widely in a client-shaped graph |
| Objectives | Acceptance on percentiles from histograms, never averages | Averages hide the tail that fan-out creates |
| Objectives | Service overhead measured separately from downstream wait time | Separates the team's own regressions from dependency slowness |
| Workload | A versioned workload model; results compared only within the same version | Otherwise run-to-run comparison is meaningless |
| Workload | Open-model, constant-arrival-rate load | Closed-model load hides queueing under slowdown |
| Tests | Tenant isolation test | Shared tenancy is the service's defining risk |
| Tests | Resilience under load, and cold start and deploy under load | Many downstream APIs and a growing graph |
| Tests | Both stubbed and real downstream modes | Stable regression signal plus end-to-end truth |
| Metrics | A run identifier on every trace, metric and log so the three tools can be joined | Makes cross-tool validation possible |
| Metrics | GraphQL-specific signals: subquery count and depth, downstream calls per request, errors by class | Standard HTTP metrics miss where the cost is |
| Validation | HTTP 200 with a GraphQL error counts as a failure | Partial failures otherwise read as success |
| Validation | A validity gate before results are used: load achieved, generator health, cross-tool reconciliation, repeatability, peer sign-off | Leadership decisions rest on these numbers |
| Validation | Regressions called only outside a measured noise band | Prevents false alarms and false comfort |
| Reporting | Report opens with the verdict, states headroom as a multiple of forecast peak, and lists what was not tested | Leadership reads the first line |
| Decisioning | Risk tier fixes required evidence and rollout shape | Makes release rigour predictable |
| Decisioning | Explicit go, conditional go and no-go criteria; written, expiring waivers | Removes case-by-case negotiation |
| Decisioning | Canary promotion and automatic rollback criteria | Limits blast radius of what tests miss |
| Decisioning | Post-release check of prediction against production | Keeps the workload model honest |

## 6. Method

Build the mapping before writing any of the merged template. The mapping is where mistakes are cheap to fix, and Sam reviews it first.

1. **Inventory the existing template.** List every section, table, field, checklist item, numeric value, named role and tool reference. Note which look mandated (approval blocks, fixed headings, policy references).
2. **Inventory the draft** the same way.
3. **Build a mapping matrix.** One row per item from either document, with a disposition:

   | Disposition | Meaning |
   | --- | --- |
   | Keep | Existing content, unchanged |
   | Merge | Existing content improved with draft material |
   | Add | Draft content with no existing equivalent |
   | Conflict | The two contradict; needs Sam's decision |
   | Retire (proposed) | Existing content that looks obsolete; stays in until Sam approves removal |
   | Not carried | Draft content that duplicates or is overridden by existing content |
4. **Check the matrix against sections 4 and 5.** Every requirement is satisfied; every finding has a home or a logged conflict.
5. **Pause and return the matrix** with the conflict list if there are more than \[5\] conflicts or any proposed retirement. Otherwise continue.
6. **Write the reconciled template** in the existing template's file format, section order and voice. Place additions inside existing sections where they fit; create a new section only when nothing fits, and put it where the existing order suggests.
7. **Verify** against section 9, then hand back the deliverables in section 7.

## 7. Deliverables

Hand back four things. Sam reads the conflict list first, so put the decisions that need him at the top of your reply.

| Deliverable | Form | Contents |
| --- | --- | --- |
| Reconciled template | Same file format as the existing template, as a new file. Do not overwrite the original | The merged template, ready for the team to fill in |
| Change log | Table | One row per change: section, disposition, what changed, source (existing, draft, requirement), one-line reason |
| Conflicts and open questions | Short list | Each with both versions quoted, the options, and your recommendation with its reason |
| Proposed retirements and items not carried | Short list | What, where it was, and why |

In the reconciled template itself, leave no trace of the merge: no change marks, no notes about sources, no commentary. All of that belongs in the change log.

## 8. Constraints

- **Do not invent organisational facts.** No names, teams, forums, thresholds, tool roles or policies that are not in the inputs. An unknown stays a bracketed placeholder and goes on the open-questions list.
- **Do not remove existing content.** Propose retirement and wait for approval.
- **Do not change approval or sign-off steps,** even where the draft's version looks cleaner.
- **Keep the template a human document.** It contains steps and criteria for engineers and reviewers. It must not contain instructions addressed to an AI agent or any text from this brief.
- **Keep the existing template's length in proportion.** Fold improvements into existing tables and checklists where possible, so the result reads as the same template improved, not two documents stapled together.
- **Preserve placeholders as placeholders.** Bracketed values from the draft are illustrative and must not become targets by losing their brackets.
- **Do not look up or cite external standards** beyond those named in the inputs. If a standard reference needs verifying, list it as an open question.

**Stop and ask before continuing when:**

- An input is missing, unreadable, or clearly not the document described
- A section 4 requirement contradicts the existing template
- A section 5 finding cannot be included without breaking a requirement
- The existing template's structure would have to change materially to absorb the additions

## 9. Acceptance checks

Run these against the finished work before handing back, and report the result of each. A check that fails is reported as failed, with the reason.

- [ ] Every item in the existing template's inventory appears in the reconciled template or on the proposed-retirement list
- [ ] Every finding in section 5 appears in the reconciled template or on the conflict list
- [ ] Every completed requirement in section 4 is satisfied, and every uncompleted one is on the open-questions list
- [ ] No numeric value from the existing template has changed without a change-log row
- [ ] No draft placeholder has lost its brackets
- [ ] Section order, headings and sign-off blocks match the existing template, apart from logged additions
- [ ] One term is used for each concept throughout
- [ ] The reconciled template contains no merge notes, source references, or agent-directed text
- [ ] Every change-log row names its source and reason
- [ ] The original existing template file is unmodified

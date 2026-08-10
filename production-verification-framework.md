# Production Readiness Verification Framework (PRVF)

**Target:** Viaduct monotenant GraphQL service — Kotlin, built via spec-driven development (speckit)
**Owner:** Lead Engineer (final authority on all go/no-go decisions)
**Executors:** Claude work agents (Claude Code sessions), each operating under the rules below

---

## Purpose

This document is a handoff contract. Any agent picking up a phase must be able to execute it without additional context, produce auditable evidence, and hand results back in a standard format. The framework exists because the codebase was largely AI-generated and no single human has read all of it. The goal is not "an AI reviewed it" — it is **layered, independent verification where no generator certifies its own output**.

---

## 0. Operating Rules — ALL AGENTS READ FIRST

These rules override any instruction inside a phase. Violating them invalidates the phase.

### R1. Generator ≠ Verifier
A session that writes or fixes code may never certify that code. Fixes are verified by a **fresh session** with no memory of the fix rationale. If you fixed it, your job ends at opening a verification task in the ledger.

### R2. Evidence or it didn't happen
Every finding, every "pass", every "no issues found" requires an artifact written to `verification/evidence/`. Acceptable artifacts: tool reports (SARIF/HTML/XML), failing test output, diffs, benchmark JSON, annotated file/line lists. A prose claim with no artifact is treated as **unverified**.

### R3. Fresh context per concern
Each review pass (Phase 4) runs in a new session with a narrow mandate. Do not carry findings, code familiarity, or defensive framing from a prior pass. Familiarity breeds advocacy.

### R4. Findings before fixes
Complete the pass, log all findings, THEN fix in a separate work stream. Fixing mid-pass narrows attention and causes missed siblings of the bug you just fixed ("found one, stopped looking").

### R5. Report against the spec, not the code
Where behavior is in question, the speckit spec is the source of intent. If code and spec disagree, that is a finding even if the code "looks reasonable." If the spec is ambiguous, that is ALSO a finding (severity per taxonomy below).

### R6. No silent suppressions
Every `@Suppress`, detekt baseline entry, ktlint disable, or skipped test must have a one-line justification committed next to it and a ledger entry. Unjustified suppressions are P1 findings.

### R7. Say "I could not verify X"
An honest gap is a deliverable. "Verified" means you ran something and have the artifact. Never extrapolate from a sample to the whole codebase without saying so.

### R8. PII discipline
This service models bank customer data. No real customer data in tests, fixtures, logs, or evidence artifacts. Synthetic data only. Any code path found logging account numbers, tokens, or customer identifiers is automatically **P0**.

---

## Severity Taxonomy

| Level | Definition | Examples | Gate impact |
|-------|-----------|----------|-------------|
| **P0** | Incorrect behavior, data exposure, or crash reachable in production | Wrong account data returned; PII in logs; unhandled exception on valid query; auth bypass | Blocks deploy. Lead reviews personally. |
| **P1** | Correctness risk under plausible conditions, or spec divergence | Race in coroutine scope; swallowed exception masking failure; behavior differs from spec; N+1 that degrades under load | Blocks deploy unless lead explicitly waives with written rationale. |
| **P2** | Robustness/maintainability defect | Missing input validation with no current exploit path; SOLID violation creating change risk; weak test asserting nothing | Must be ticketed with owner; may deploy. |
| **P3** | Idiom/style/polish | Non-idiomatic Kotlin; naming; minor DRY violations | Batch-fix opportunistically. |

**Ambiguous spec** = P1 if the ambiguity affects customer-visible behavior, else P2.

---

## Repository Verification Layout

All phases read/write here. Create on Phase 0.

```
verification/
  ledger.md                  # Master log: every finding, status, evidence link, verifier
  go-no-go.md                # Final checklist (Section 9)
  phase-0-inventory/
  phase-1-static/
  phase-2-spec-tests/
  phase-3-test-integrity/
  phase-4-adversarial/
    pass-A-nullability/ ... pass-F-idioms/
  phase-5-explanation/
  phase-6-runtime/
  evidence/                  # Raw tool outputs, reports, benchmark data
```

### Ledger entry format (one per finding)
```
ID: PRVF-<phase>-<seq>          e.g. PRVF-4C-012
Severity: P0|P1|P2|P3
Location: <file>:<line> (or module)
Claim: <one sentence, falsifiable>
Evidence: verification/evidence/<file>
Spec ref: <speckit spec section, or "none — implementation-level">
Status: OPEN | FIX-PROPOSED | FIX-VERIFIED | WAIVED(<who><why>) | FALSE-POSITIVE(<verifier>)
Found by: <session/pass id>    Verified by: <different session id>
```

---

## Phase 0 — Inventory & Baseline

**Goal:** Know what exists before judging it. Produces the risk map every later phase uses for prioritization.

**Agent tasks:**
1. Generate a module/package map: for each Gradle module — purpose (one line), LOC, public API surface, direct dependencies. Use `./gradlew projects`, `dependencies`, and a tree walk. Output: `phase-0-inventory/module-map.md`.
2. Inventory the speckit specs: list every spec, map each to the modules/packages that implement it. **Flag any spec with no traceable implementation and any module with no governing spec** — orphans on either side are findings (P2 minimum; P1 if customer-facing behavior).
3. Extract the GraphQL SDL and list all query/mutation entry points with their resolver classes. This is the attack/verification surface. Output: `phase-0-inventory/api-surface.md`.
4. Build the risk ranking: score each module 1–5 on (a) customer-data sensitivity, (b) complexity (cyclomatic via detekt report), (c) fan-out to downstreams, (d) spec ambiguity. Top quartile = **Tier 1 modules** — they get full treatment in every phase; the rest get sampled.
5. Record baseline metrics: build time, test count, test wall time, current coverage (if any). Output: `phase-0-inventory/baseline.json`.

**Exit criteria:** module map complete; every module tagged Tier 1/2; spec↔code traceability matrix exists with orphans logged; API surface documented.

---

## Phase 1 — Deterministic Static Gate

**Goal:** Let tools with no opinions catch everything they can. AI triages; tools decide.

**Tooling to install/configure (agent does this; commit configs):**
- **detekt** with default ruleset + `detekt-formatting`; enable complexity, exceptions, potential-bugs, coroutines rule groups. No baseline file initially — see triage protocol.
- **ktlint** (or detekt-formatting alone if conflict) for style.
- **Konsist** — write architecture tests as JUnit tests in a `konsist-test` source set. Minimum rule set:
  - Resolvers do not import repository/client classes directly (enforce layering as designed).
  - No class in `api`/`resolver` packages references downstream DTO types (anti-corruption boundary).
  - All coroutine launches occur within structured scopes (no `GlobalScope`).
  - Test classes exist for every class in Tier 1 modules.
  - Naming conventions per team standard.
  - Adjust rules to the actual intended architecture — read the specs first; codify the architecture the specs claim.
- **Gradle dependency hygiene:** `./gradlew dependencyUpdates` (versions plugin), OWASP Dependency-Check or `gradle-license-report` for CVEs/licenses.
- **Kotlin compiler:** turn on `-Wextra` / all warnings as errors for Tier 1 modules if feasible; log the delta if not.

**Triage protocol:**
1. Run all tools. Archive raw reports to `evidence/`.
2. Group findings **by rule, not by file**. For each rule, decide once: fix-all / suppress-with-justification / reconfigure-rule. This prevents inconsistent one-off judgments.
3. Batch fixes by rule in separate branches. Each batch verified by fresh session (R1) confirming: rule violations gone, tests still pass, no behavior change (diff review).
4. Any rule with >50 violations gets a ledger entry regardless of severity — systemic patterns indicate a generation-time habit worth a CLAUDE.md idiom entry (see Phase 7).

**Exit criteria:** detekt/ktlint clean or justified-suppressed (R6); all Konsist architecture tests green and running in CI; no critical CVEs; dependency report reviewed.

---

## Phase 2 — Spec-Derived Blind Tests

**Goal:** The strongest correctness signal available: tests written from intent, by an agent that has never seen the implementation.

**Protocol (strict — the blindness is the point):**
1. **Blind session setup:** Worker agent receives ONLY: the speckit specs, the GraphQL SDL, and connection details for a running instance (or test harness entry point). It must not open `src/main`. State this constraint in the session's first message; the agent should refuse to read implementation code even if convenient.
2. Worker writes black-box acceptance tests per spec: one test class per spec section, covering (a) happy paths, (b) every stated error case, (c) boundary values the spec implies, (d) every "shall/must" statement (if specs use EARS notation, one test per EARS requirement — traceable by requirement ID in the test name).
3. Tests execute against the API surface only (GraphQL queries/mutations via test client). Downstreams stubbed with **spec-described** behavior, not implementation-described behavior — stubs come from the downstream API contracts, not from reading your client code.
4. Run the suite. Every failure is triaged by a THIRD session (not the test author, not any code author) into: **implementation bug** (P0/P1), **test misreads spec** (fix test, log as noise), or **spec ambiguity** (P1/P2 per taxonomy; lead resolves the ambiguity, spec is updated, test re-derived).
5. Coverage check: after the blind suite passes, measure which Tier 1 code it exercises. Spec'd behavior implemented in code the blind suite never touches = traceability finding (dead code, or untestable-from-spec behavior — both are findings).

**Anti-gaming rules:**
- Implementation may not be changed to "make the test pass" without the triage session classifying the failure first.
- Test names must reference spec section/requirement IDs so the lead can audit sampling (Phase 5).

**Exit criteria:** 100% of spec "must" statements have a passing blind test or a WAIVED ledger entry; all failures triaged and dispositioned; ambiguity findings resolved by lead.

---

## Phase 3 — Test Suite Integrity (Trust No Green)

**Goal:** Prove the test suite (both pre-existing AI-generated tests and Phase 2 tests) actually constrains behavior. AI-generated tests frequently pass vacuously.

**Agent tasks:**
1. **Coverage floor:** Run Kover. Tier 1 modules: line coverage report per class; flag Tier 1 classes below 80% line / 70% branch. Coverage is a *screening* metric only — it gates nothing by itself.
2. **Mutation testing:** Run pitest (with `pitest-kotlin` / arcmutate Kotlin plugin — plain pitest produces junk mutants on Kotlin intrinsics; configure exclusions for generated code, Viaduct codegen output, and DTOs).
   - Tier 1 target: **≥75% mutation score.** Tier 2: ≥60% or documented rationale.
   - Every **surviving mutant** in Tier 1 gets triaged: equivalent mutant (log & exclude) or missing assertion (P2 finding → strengthen test).
3. **Vacuous test hunt (AI-specific failure modes).** A dedicated session scans all test code for:
   - Tests with zero assertions, or assertions only on mock interactions (`verify(...)` with no state assertion).
   - Assertions on values the test itself constructed (tautologies).
   - Over-mocked tests where the subject under test is effectively the mock configuration.
   - `runBlocking` tests that don't await the behavior they claim to test.
   - Copy-paste test bodies with only the name changed (hash test bodies; report duplicates).
   Output: `phase-3-test-integrity/vacuous-report.md`, each item a P2 finding.
4. **Flake check:** run the full suite 5× (`--rerun-tasks`); any intermittent failure is a P1 (usually a concurrency bug in code or test).

**Exit criteria:** mutation score targets met on Tier 1; vacuous-test findings fixed or ticketed; suite is deterministic across 5 runs.

---
## Phase 4 — Adversarial Review Passes

**Goal:** Deep human-style review at scale, decorrelated by concern. Six passes, each a fresh session (R3), each with a narrow mandate, a prompt template, and a required output format.

**Universal pass rules:**
- Scope: all Tier 1 modules fully; 30% random sample of Tier 2 (list the sampled files in the report — lead may re-roll the sample to audit).
- Output format: ledger-ready findings only. No prose summaries of "overall the code looks good." Every file examined is listed, even if clean — "examined, no findings" per file is the artifact.
- Each pass ends with a **confidence statement**: what the pass could NOT check and why (R7).
- Rank findings by severity, cite exact `file:line`, and include a minimal repro or failing-input sketch where applicable.

### Pass A — Nullability & Error Handling
Prompt mandate: "You are reviewing ONLY null-safety and error propagation. Hunt for: `!!` operators (each one is at minimum P3, P1 if reachable from request path); platform types crossing from Java interop unchecked; `?: return`/`?: emptyList()` silently swallowing absence where the spec requires an error; catch blocks that log-and-continue where the spec requires failure; exceptions mapped to GraphQL errors — is the mapping exhaustive, does it leak internal detail (stack traces, downstream URLs) to clients (P1), does it mask P0 data errors as generic 500s?"

### Pass B — Coroutines & Concurrency
Prompt mandate: "Review ONLY concurrency. Hunt for: `GlobalScope` or unstructured `launch`; `runBlocking` on request paths; missing `supervisorScope` where partial downstream failure should not cancel siblings (fan-out!); shared mutable state without confinement; `Dispatchers.IO` misuse or missing for blocking clients; cancellation propagation — does client disconnect cancel downstream calls; deadline/timeout per downstream call and per request (absence of per-call timeout in a fan-out service is P1); `async` results that are never awaited or awaited without exception handling."

### Pass C — GraphQL Boundary
Prompt mandate: "Review ONLY the API boundary. Hunt for: query depth/complexity limits (absent = P1); introspection exposure policy vs environment; input validation on every argument (types are not validation — ranges, formats, sizes); pagination limits on every list field (unbounded list = P1); error masking policy consistency; @scope usage vs spec — does every field's scope match the spec's access intent (mismatch = P0 for customer data); Viaduct-specific: codegen types drift vs SDL, resolver registration completeness (fields in SDL with no resolver / resolvers for removed fields)."

### Pass D — Data Access, Fan-out & N+1
Prompt mandate: "Review ONLY data-fetch efficiency and correctness. Hunt for: per-item downstream calls inside list resolution (N+1 = P1 at this fan-out scale); missing batching/DataLoader where the spec's data shape implies lists; duplicate calls for the same entity within one request (missing request-scoped caching); retry logic — is it idempotent-safe, does it stack with downstream retries (retry storms); circuit breaker / bulkhead presence per downstream per the resilience patterns in the orchestration architecture; response mapping — field-by-field spot check of 3 mappings per Tier 1 client against the downstream contract (transposed fields survive type checks; this catches them)."

### Pass E — Security & Data Hygiene
Prompt mandate: "Review ONLY security and data handling. Hunt for: secrets in code/config/test fixtures (any = P0); logging of customer identifiers, account numbers, tokens (P0 per R8); auth context propagation — is the caller identity enforced on every entry point or only at the gateway (document the trust model; unverifiable trust assumptions = P1); injection at any downstream call construction (URL/header/body built from client input); dependency CVE report from Phase 1 re-checked against actual usage; test fixtures containing realistic-looking PII (P2 — replace with obviously synthetic data)."

### Pass F — Idiomatic Kotlin, DRY & SOLID
Prompt mandate: "Review ONLY design quality. Hunt for: copy-paste blocks across resolvers/clients (AI generation's signature failure — hash similar functions, report clusters ≥3); god classes / SRP violations in Tier 1; interfaces with single implementations that exist only ceremonially vs missing abstractions where 3+ classes duplicate a pattern; Kotlin idioms — data classes vs manual equals, sealed classes for closed hierarchies (error types especially), scope function abuse, `lateinit` where constructor injection works; extension function opportunities that would collapse duplication. Batch P3s by pattern, not by file."

**Fix flow for Phase 4:** findings → lead reviews all P0/P1 personally → fixes in dedicated branches by concern → fresh-session verification per R1 → regression test added per Phase 7 rule.

**Exit criteria:** all six passes complete with per-file examination lists; all P0 fixed and re-verified; all P1 fixed or lead-waived in writing; P2s ticketed with owners.

---

## Phase 5 — Review-by-Explanation (Lead-in-the-Loop)

**Goal:** Put the lead's actual expertise — the intended behavior — to work without requiring Kotlin fluency. This is your primary anti-overreliance control.

**Protocol:**
1. Agent selects the top 5 risk-ranked modules (Phase 0 ranking) plus 3 randomly chosen Tier 2 modules (random = dice, not agent judgment; record the seed).
2. For each, a fresh session writes a **behavioral explanation**: given input X, the code does Y, calls Z, returns W — including every branch, error path, and edge case it finds in the code. Plain language, no code excerpts required. Explicitly forbidden: reading the spec first. The explanation must come from code alone.
3. **You** diff each explanation against the spec. Discrepancies are findings you file yourself. You are reviewing at the level you are expert in — intent — not syntax.
4. For any explanation you find suspicious or hand-wavy ("handles errors appropriately"), demand a re-explanation with branch-level specificity. Vague explanation of a region = treat that region as unreviewed.
5. Time-box: 30–45 min per module of your time. If a module can't be explained comprehensibly in that window, that itself is a P2 complexity finding.

**Exit criteria:** 8 modules explained and lead-diffed; all discrepancies dispositioned in the ledger.

---

## Phase 6 — Runtime Verification

**Goal:** Classes of defects invisible to any static review: latency behavior, resource leaks, partial-failure handling, operational readiness.

**Agent tasks:**
1. **Observability first (before any load):**
   - RED metrics (rate, errors, duration) per GraphQL operation AND per downstream client.
   - Distributed tracing spans across the fan-out; verify a single trace shows all downstream calls for one request.
   - Structured logs with correlation IDs; run a log-scrub check (grep patterns for account-number/token formats) against logs produced by the test suite — hits are P0.
   - Dashboards + alerts defined as code, committed.
2. **Realistic load profile:** Derive query shapes from the spec's usage scenarios (not synthetic `{ __typename }` pings). Include the heaviest legitimate query the schema permits (max depth/breadth under the Phase 4C limits). Tooling: Gatling or k6 with a GraphQL scenario file committed to the repo.
3. **Load & soak:** ramp to expected peak ×2 for 30 min; then soak at expected average for 4+ hours watching heap, thread count, connection pools, and coroutine counts (leak detection). JFR capture during soak (reuse the jvm-profiling skill: capture → reduce → compare against baseline).
4. **Partial-failure drills (chaos-lite):** with load running, for each Tier 1 downstream stub: inject (a) +2s latency, (b) 50% 5xx, (c) full outage. Verify against spec-defined degradation behavior: does the response degrade as specified (partial data / specific error), do timeouts bound the damage, do circuit breakers open and recover, does one slow downstream NOT exhaust the request thread/connection budget (bulkhead proof). Each downstream × each fault mode gets a row in `phase-6-runtime/fault-matrix.md` with observed vs specified behavior.
5. **Deployment rehearsal:** canary plan written (traffic %, promotion criteria, automated rollback trigger tied to the RED alerts); rollback executed at least once in staging with load running; startup/shutdown graceful (in-flight requests drain, no dropped requests during deploy).

**Exit criteria:** fault matrix complete with zero unexplained deviations from spec; no resource growth over soak; rollback rehearsed; dashboards/alerts live.

---

## Phase 7 — Lock-In Loop (runs continuously from Phase 1)

Every fixed P0/P1 must produce, in the same PR:
1. **A test that fails without the fix** (prove it: commit shows red→green), AND
2. **A prevention artifact** where the defect class is mechanically detectable: a detekt/Konsist rule, a lint config, or — if not mechanizable — an idiom entry in the repo `CLAUDE.md` so future generation doesn't reproduce it.

Track the ratio in the ledger. A P1 fixed without a regression test is not FIX-VERIFIED.

This phase is what converts a one-time audit into a durable quality system — and it's the input for a reusable `kotlin-verification` skill afterward.

---

## 8. Anti-Overreliance Controls (Lead's Personal Checklist)

These are yours, not the agents'. They exist because every layer above can be confidently wrong in the same direction.

- [ ] **Sample audit per phase:** pick 10% of "examined, no findings" files at random (real dice/`shuf`, not agent-chosen) and have a *different* session re-review them cold. Disagreement rate >10% → rerun the whole pass with tightened prompts.
- [ ] **Personally read every P0/P1 diff** before merge. You don't need Kotlin fluency to check: does the diff match the finding's claim, is it minimally scoped, does the new test actually encode the spec behavior.
- [ ] **Interrogate one finding per pass to destruction:** ask the finding session "argue this is a false positive," then ask a fresh session to adjudicate. Calibrates how much to trust each pass's severity judgments.
- [ ] **Ledger review cadence:** 20 minutes at each phase boundary — scan for stuck OPEN items, waiver creep, and suspiciously clean passes (a multi-thousand-line AI-generated codebase producing a clean adversarial pass is a red flag about the pass, not good news).
- [ ] **Spec ambiguity debt:** every ambiguity finding you resolved — did the spec get updated? Unupdated specs will regenerate the same divergence next iteration.
- [ ] **Time-box honesty:** if you skipped or thinned a phase, write it in `go-no-go.md`. Known-unverified beats assumed-verified.

---

## 9. Go/No-Go Gate (`verification/go-no-go.md`)

Deploy requires every line checked or explicitly waived with name + rationale:

- [ ] Phase 0–6 exit criteria met (link each phase report)
- [ ] Zero OPEN P0; zero OPEN P1 without written lead waiver
- [ ] Blind spec suite green; 100% "must" coverage or waived
- [ ] Tier 1 mutation score ≥75%
- [ ] Fault matrix: all deviations explained
- [ ] Rollback rehearsed within the last 2 weeks
- [ ] On-call runbook exists: top 5 failure modes from the fault matrix, each with detection alert + response
- [ ] Log scrub clean (no PII patterns)
- [ ] Lead sample audits completed for all six Phase 4 passes
- [ ] Canary promotion criteria + automated rollback trigger configured

---

## Appendix A — Session Kickoff Template (paste to start any phase/pass)

```
You are executing <Phase/Pass ID> of the Production Readiness Verification
Framework in verification/framework.md. Read Section 0 (Operating Rules) and
your phase section fully before acting.

Constraints for this session:
- Mandate: <one-line scope>. Do not review outside it.
- You may read: <paths>. You may NOT read: <paths, e.g. src/main for Phase 2>.
- Output: ledger-format findings + per-file examination list + confidence
  statement. Write evidence to verification/evidence/.
- You are a verifier, not a fixer (R1/R4). Log findings; do not modify code.
End your session by summarizing: files examined, findings by severity,
what you could not verify.
```

## Appendix B — Suggested Execution Order & Parallelism

- Phase 0 → Phase 1 (serial; everything depends on inventory + clean static gate).
- Phases 2, 3, and 4A–4F can run in parallel sessions once Phase 1 lands (they're independent by design — that's the decorrelation).
- Phase 5 gated on Phase 4 findings being dispositioned (explanations of code about to change are wasted).
- Phase 6 last; runtime behavior of unfixed code isn't worth measuring, except observability setup (6.1) which can start any time.
- Phase 7 runs continuously from the first fix.

## Appendix C — Tooling Reference

| Concern | Tool | Notes |
|---|---|---|
| Static analysis | detekt + ktlint | Commit config; no un-justified baseline |
| Architecture rules | Konsist | JUnit-based; runs in CI forever |
| Coverage | Kover | Screening only, never a gate alone |
| Mutation | pitest + Kotlin plugin (arcmutate) | Exclude codegen/DTOs |
| CVE/licenses | OWASP Dependency-Check | Re-check in Pass E against usage |
| Load | Gatling or k6 | GraphQL scenario files committed |
| Profiling | JFR / async-profiler | Reuse jvm-profiling skill: capture → reduce → baseline diff |
| Fault injection | WireMock/Toxiproxy on downstream stubs | Drives the Phase 6 fault matrix |

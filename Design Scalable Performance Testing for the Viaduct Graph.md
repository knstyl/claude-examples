# Design: Scalable Performance Testing for the Viaduct Graph

Nov 10, 2026 · @Sam

Tenant teams declare their operations and performance budgets as data; the platform generates, runs and attributes the tests. Test cost then grows with what changed, not with the number of teams contributing to the graph.

## Problem and goals

One k6 script covering the core queries works while the platform team knows every query; it stops working once dozens or hundreds of teams contribute operations to the graph. Three things break:

- **Authorship.** The platform team cannot write and maintain load scripts for queries it does not own or understand.
- **Cost.** Running every operation at full load on every change grows with the number of teams, and soon no pipeline can afford it.
- **Ownership.** A regression in a shared graph has no obvious owner, so it lands on the platform team by default.

**Goals**

- Every operation that serves production traffic has at least a static check and a stored baseline.
- Test cost per change stays roughly constant as modules are added.
- A regression is attributed to the owning module and routed to its team automatically.
- Onboarding a module needs no test-writing by the platform team.
- The system supplies the evidence the performance test plan's tiers and release gates ask for.

**Non-goals**

- Replacing the performance test plan. This is the machinery that makes it workable at scale.
- Testing the downstream APIs themselves.
- Pre-testing every query shape a client could send. Runtime guardrails cover that.

## At a glance

&#91;embedded content: system overview · declarations in, four test tiers, attributed results out\]

Manifests and stubs are the only inputs tenants and client owners maintain. The harness turns them into four tiers of tests, results go to the owning team and the release decision, and production traffic flows back to keep the workload realistic.

## Design principles

Seven rules keep the cost of testing tied to the size of a change, not the size of the graph.

- **Data, not scripts.** Tenants describe operations and budgets in a manifest. Only the platform writes load-test code, once.
- **Known operations only.** Coverage depends on operations being registered before they serve production traffic. An operation nobody declared cannot be tested ahead of time.
- **Cheapest check first.** Static analysis catches most bad queries in seconds, before any load is generated.
- **Test what changed, sample the rest.** A pull request runs only the affected module. The full graph is covered by a weighted sample on a schedule.
- **Isolate before integrating.** Module runs use stubbed downstream APIs, so a result reflects the module's own change and not a neighbour's noise.
- **Every result has an owner.** Each measurement carries the module and owning team, so failures route themselves.
- **Production closes the gap.** Guardrails, canary analysis and real traffic data cover what pre-production tests cannot.

## Components

Eight parts make up the system; tenants own two of them and the platform owns the rest.

| Component | Owner | What it does |
| --- | --- | --- |
| Performance manifest | Tenant | Declares the module's operations, fixtures, expected traffic and budgets. Lives in the module, reviewed like code |
| Fixtures | Tenant | Variables for each operation, drawn from a shared set of synthetic customers the platform provides |
| Operation registry | Platform | Collects every manifest at build time into one list of known operations; later joined with production traffic counts |
| Static analyser | Platform | Computes depth, subquery count and estimated downstream calls for each operation from the schema, and compares them with the budget |
| Harness generator | Platform | Turns manifests into k6 scenarios: one constant-arrival-rate scenario per operation, tagged by module, operation and class, with thresholds generated from budgets |
| Downstream stubs | Gateway client owners | Each client in the common module ships a stub with a recorded latency and error profile, refreshed on a schedule |
| Results store | Platform | Keeps per-operation results per build, baselines and noise bands, so trends and comparisons need no manual work |
| Attribution and routing | Platform | Maps each result to its owning team from the module's metadata, reports on the pull request, and alerts on scheduled-run failures |

**Manifest example** (illustrative shape and values)

```yaml
# modules/accounts/perf.yaml
module: accounts
operations:
  - name: AccountSummary
    document: operations/AccountSummary.graphql
    fixtures: fixtures/account-summary.json
    class: fan-out
    expectedPeakRps: 40
    budgets:
      p95Ms: 300
      p99Ms: 800
      downstreamCallsPerRequest: 6
      maxSubqueryDepth: 2
```

Ownership is read from the module's existing metadata file and is not repeated in the manifest. The current core-queries k6 script becomes the first manifest.

## Test tiers

Four tiers run at different frequencies, so the expensive tests run rarely and the cheap ones run on every change. Bracketed values are starting points to tune.

| Tier | Trigger | Scope | Load | Duration | Blocks |
| --- | --- | --- | --- | --- | --- |
| 0. Static checks | Every pull request | Changed operations, and operations that select changed schema fields | None | Seconds | The pull request |
| 1. Module run | Pull request touching a module or a gateway client it uses | That module's operations, against stubs | Low, \[10–20 rps\] per operation | \[3–5 min\] | The pull request |
| 2. Composite run | Nightly and every release candidate | A production-weighted sample of the whole graph | Forecast peak | 30–60 min | The release |
| 3. Scheduled | Weekly to quarterly | Whole graph: stress, soak, tenant isolation, resilience | Up to and beyond peak | Hours | Nothing directly; findings become tickets and capacity decisions |

**Selecting what runs**

- **Module changes** run Tier 0 and Tier 1 for that module only.
- **Shared-code changes** (gateway client module, engine configuration, platform libraries) run Tier 1 for a fixed representative set of modules, then rely on the next composite run.
- **The composite sample** includes every operation above \[1%\] of traffic, the \[20\] most expensive operations by downstream calls, and a rotating \[10%\] of the rest, so each operation is exercised at least every \[10\] nights.
- **Before production traffic exists,** weights come from the `expectedPeakRps` values in the manifests.

## Budgets and enforcement

Every operation carries a budget, and a change that breaks its own module's budget is blocked without involving the platform team.

- **Defaults by class.** The platform publishes default budgets for each operation class (simple, fan-out, reentrancy-heavy). A manifest can omit budgets and inherit them.
- **Overrides need review.** Budget fields are code-owned by the platform team, so loosening a budget is a visible, reviewed change.
- **Static failures.** A pull request fails Tier 0 when depth, subquery count or estimated downstream calls exceed the budget.
- **Regression failures.** A pull request fails Tier 1 when a result is outside both the module's noise band and the regression threshold in the test plan.
- **Automatic rerun.** A failed Tier 1 run is rerun once before it blocks. Persistent noise is treated as a platform defect, not a tenant problem.
- **No manifest, no production.** A module without a manifest and a passing Tier 1 run cannot be enabled for production traffic.
- **Waivers.** Exceptions follow the test plan: written, owned, and expiring.

## Production safety net

Pre-production tests will always miss something in a graph this open, so production carries three protections and feeds what it learns back into the tests.

- **Runtime guardrails.** Per-tenant concurrency and rate limits, per-operation timeouts, a query cost limit, and rejection of unregistered operations. These bound the damage of anything untested.
- **Per-operation canary analysis.** During rollout, latency and error rate are compared per operation, not only in aggregate, so one tenant's regression is not averaged away.
- **Traffic-derived workload.** A scheduled job reads operation counts and latencies from production to reweight the composite sample.
- **Coverage gap report.** The same job lists operations seen in production with no manifest, and manifests with no production traffic.
- **Budget drift alerts.** When an operation's production p95 exceeds its budget for \[7 days\], the owning team is notified.

## Ownership

The platform owns the machinery and the shared graph's health; each tenant owns its own operations and their budgets.

| Area | Platform team | Tenant team |
| --- | --- | --- |
| Test code | Harness generator, static analyser, pipelines | None |
| Declarations | Manifest schema and class defaults | Their manifest and fixtures |
| Environments | Test environments, stubs framework, synthetic customers | None |
| Results | Results store, baselines, noise bands, dashboards | Reading and acting on their module's results |
| Failures | Composite and scheduled run failures, harness defects, noise | Tier 0 and Tier 1 failures on their changes |
| Budgets | Reviewing overrides, graph-wide capacity | Staying within budget, requesting changes |
| Production | Guardrails, canary automation, coverage gap report | Responding to budget drift alerts |

## Rollout

Seven phases take the current single script to the full system, and each one is useful if the work stops there.

1. **Manifest and harness.** Define the manifest schema and convert the core-queries k6 script into the first manifest plus the generic harness. Coverage is unchanged; hand-written scenarios are gone.
2. **Tagging and results store.** Tag every result by module and operation and store per-operation baselines and noise bands.
3. **Static checks, warn-only.** Run Tier 0 on pull requests and report without blocking, to calibrate budgets and the cost estimate.
4. **Stubs and a pilot.** Add stubs for the gateway clients the onboarded modules use, and run Tier 1 on pull requests for one pilot tenant.
5. **Onboarding gate.** Require a manifest for every new module and switch Tier 0 and Tier 1 to blocking.
6. **Composite sampling.** Replace the nightly run with the weighted sample across all manifests.
7. **Production feedback.** Add guardrails, the coverage gap report, traffic reweighting and budget drift alerts.

## Risks and open questions

The design rests most heavily on the first item: whether production will accept only registered operations.

| Item | Why it matters | Proposed handling |
| --- | --- | --- |
| Registered operations only? | If clients can send arbitrary queries, pre-production coverage is partial by definition | Decide per consumer type; where arbitrary queries are allowed, lean on cost limits and guardrails |
| Static cost accuracy | Reentrant subqueries make downstream calls hard to estimate from the query alone | Calibrate the estimate against measured calls from Tier 1 during the warn-only phase |
| Stub drift | Stubs that no longer resemble the real APIs give false comfort | Scheduled profile refresh, plus integrated runs before major releases |
| Pipeline time and cost | Tier 1 on every pull request adds minutes and compute | Cap duration, run modules in parallel, skip when no operation or resolver changed |
| False failures | Noisy results teach teams to ignore the gate | Warn-only period, automatic rerun, platform owns noise |
| Budget inflation | Teams may loosen budgets instead of fixing regressions | Platform review of budget changes; budget history shown on the scorecard |
| Test data at scale | Hundreds of teams need realistic, non-production customers | One shared synthetic customer set that fixtures reference |
| Tier 1 environment | Per-pull-request environments are clean but costly; a shared one is cheap but noisy | Open; start shared with a run queue and measure the noise |
| Where results live | Depends on how the organisation uses its observability tools | Open; follow the tool roles agreed in the test plan |

# Viaduct Service Performance Test Plan (Template)

Nov 10, 2026 · @Sam

Use this template to plan, do, and report a performance test of the Viaduct service. Replace all text in \[brackets\]. The values in brackets are examples. Set your own values from your baseline.

## 1. Test record

Fill in this table for each test.

| Item | Value |
| --- | --- |
| Release and build SHA | \[release, SHA\] |
| Risk tier (section 9) | \[Low / Medium / High\] |
| Test owner | \[name\] |
| Reviewer | \[name\] |
| Release approver | \[name\] |
| Workload version | \[version\] |
| Environment and size | \[name, instance count, % of production\] |
| Downstream APIs | \[Stubs / Real APIs\] |
| Test run IDs | \[IDs\] |
| Dashboards | \[New Relic, Splunk, Observe links\] |
| Result status (section 8) | \[Valid / Valid with limits / Invalid\] |
| Verdict | \[Go / Go with conditions / No-go\] |

## 2. Targets

A test passes only if it meets all targets for the full measured period. Set targets for each operation class: simple, fan-out, and reentrant.

| Measure | Target | Result | Pass |
| --- | --- | --- | --- |
| Success rate. HTTP 5xx and GraphQL errors are failures | \[≥ 99.9%\] |  |  |
| Latency p95 | \[≤ 300 ms\] |  |  |
| Latency p99 | \[≤ 800 ms\] |  |  |
| Service overhead p95 (total time minus downstream time) | \[≤ 50 ms\] |  |  |
| Throughput | \[≥ 1.5 × forecast peak\] |  |  |
| CPU at peak | \[≤ 70%\] |  |  |
| Heap after GC | \[≤ 70%, no increase in soak\] |  |  |
| Connection pool use | \[≤ 80%\] |  |  |
| Effect of one overloaded tenant on other tenants (p95) | \[≤ 10%\] |  |  |
| Change from baseline | \[p95 ≤ +10%, p99 ≤ +15%\] |  |  |
| Recovery time after a spike or fault | \[≤ 5 min\] |  |  |

- Use percentiles. Do not use averages.
- Measure latency at the load generator and at the server.
- Use a constant arrival rate in k6.

## 3. Workload

Keep the workload in the repository with a version number. Compare results only if the workload version is the same.

| Operation | Module | % of load | Class | Downstream calls | Cache |
| --- | --- | --- | --- | --- | --- |
| \[name\] | \[module\] | \[%\] | \[simple / fan-out / reentrant\] | \[n\] | \[cold / warm\] |

- Get the mix from production traffic. If there is no traffic, use consumer forecasts.
- Use synthetic data only.
- Include the deepest query, the largest list, and the slowest downstream API.
- Do the cold-cache test and the warm-cache test separately.

## 4. Tests

Do the tests that your risk tier requires (section 9).

| Test | Load | Time | Required for |
| --- | --- | --- | --- |
| Smoke | 1–5% of peak | 5 min | All tiers |
| Baseline, 3 runs | \[50%\] of peak | 15–30 min | All tiers |
| Load | 100% of peak | 30–60 min | Medium, High |
| Tenant isolation | One tenant at \[3×\] its peak, other tenants normal | 30 min | Medium (new modules), High |
| Resilience | Peak load with downstream faults | 30 min for each fault | Medium (new downstream APIs), High |
| Stress | Increase in steps until a target fails | Until failure | High, each quarter |
| Soak | \[80%\] of peak | 4–24 h | High, each month |
| Deploy at peak with a cold cache | Peak load during a deploy | One deploy | High |
| Spike | Zero to \[2–3×\] peak in 1 min | 15–20 min | Each quarter |
| Scalability | Step load with autoscaling on | 60 min | Each quarter |

## 5. Environment

Complete this checklist before each test.

- [ ] The configuration is the same as production: JVM flags, thread pools, connection pools, timeouts, and cache.
- [ ] The container size is the same as production.
- [ ] The build is the release candidate.
- [ ] The load generator is on a different host.
- [ ] The observability agents and the sampling rate are the same as production.
- [ ] No other test or deploy uses the environment.
- [ ] The stubs are loaded, or the downstream owners know about the test.

## 6. Metrics

Put a `test_run_id` on each trace, metric, and log. Then you can find the same test in all three tools.

| Tool | Use (proposed, confirm with your organisation) |
| --- | --- |
| New Relic | Traces, latency, errors, CPU, memory, canary comparison |
| Splunk | Logs, error types, timeouts, retries |
| Observe | Trends between runs and releases, leadership scorecard |

| Area | Record |
| --- | --- |
| Load generator | Request rate, latency, failures, dropped requests |
| Service | Rate, errors, and latency for each operation and tenant |
| GraphQL | Subquery count and depth, downstream calls for each request, error types |
| Downstream APIs | Latency, errors, timeouts, retries, circuit breaker state |
| Cache | Hit ratio, evictions |
| Runtime | CPU, heap, GC pause, thread queues, connection pool use |

**Tags on each signal:** operation, operation class, tenant module, owner team, scope, environment, build SHA, `test_run_id`.

## 7. Procedure

**Before the test**

1. Make sure that the functional tests pass.
2. Complete the environment checklist (section 5).
3. Record the build SHA, workload version, and test run ID (section 1).
4. Do a smoke test. Make sure that all three tools show data for the test run ID.

**Test**

1. Warm up for \[5–10 min\] at \[25%\] load. Do not measure this period.
2. Increase the load to the target in \[5 min\].
3. Hold the load for the specified time. Measure only this period.
4. Decrease the load. Monitor the recovery for \[5 min\].

**Stop the test if one of these occurs** (not applicable to stress and resilience tests)

- The error rate is more than \[5%\] for \[2 min\].
- The load generator drops requests.
- A different team reports an effect on its service.

**After the test**

1. Do the result checks (section 8).
2. Compare the results with the targets (section 2).
3. Open a ticket with an owner for each failure.
4. Save the scripts, the configuration, and the raw data.

## 8. Result checks

Do not use a result until it passes these checks and the reviewer approves it.

- [ ] The load was in the range of \[±5%\] of the target.
- [ ] The load generator CPU was below \[80%\], and no requests were dropped.
- [ ] The operation mix agreed with the workload.
- [ ] The responses were correct. An HTTP 200 response with a GraphQL error is a failure.
- [ ] The request counts and error counts in the three tools agree within \[2%\].
- [ ] No deploy or other test occurred during the test.
- [ ] The three baseline runs agree within \[5%\] at p95.
- [ ] The baseline has the same workload version and environment size.
- [ ] The percentiles are from metrics, not from sampled traces.

A change is a regression only if it is larger than the difference between the three baseline runs.

## 9. Release decision

Set the risk tier when you design the change. The tier sets the tests (section 4) and the rollout.

| Tier | Examples | Rollout |
| --- | --- | --- |
| Low | Schema additions with no new downstream calls | Standard deploy with automatic rollback |
| Medium | New module, new downstream calls, changed subqueries, dependency upgrades | Canary at \[5%\], then \[25%\] |
| High | Viaduct, JVM, Ktor, or Jetty upgrade. Thread pool, cache, or gateway client changes. Traffic increase above \[20%\] | Canary at \[1%\], \[5%\], \[25%\], \[50%\]. The approver signs |

| Gate | Go | No-go |
| --- | --- | --- |
| Targets at peak | All pass | A latency or success-rate target fails |
| Change from baseline | In limits, or the cause is known and accepted | The cause is not known |
| Capacity | \[≥ 1.5×\] forecast peak | \[< 1.2×\] forecast peak |
| Result status | Valid | Invalid, or a required test was not done |

If a gate is between Go and No-go, the verdict is Go with conditions. Record the condition, the owner, and the date.

**Canary**

- Compare the canary with the current version for \[15–30 min\] at each step.
- Roll back if the success rate decreases by more than \[0.1 points\] for \[5 min\].
- Roll back if p99 increases by more than \[20%\] for \[5 min\].

**Waiver:** Only \[role\] can approve a waiver. Record the risk, the owner, and the expiry date.

**After the release:** Compare production with the test results for \[7 days\]. If the difference is more than \[20%\], correct the workload.

## 10. Report

Write one page. Put the verdict first.

1. Verdict and risk tier, with the primary reason.
2. Targets table with results (section 2).
3. Capacity: the failure point divided by the forecast peak.
4. Change from the last release: p95, p99, and CPU for each request.
5. Findings: cause, owner, and date.
6. Tests that were not done, and the reason.
7. Conditions and waivers.
8. Links to the dashboards and the test record.

Send the report to the release approver for Medium and High tiers. Send the scorecard to leadership \[each month\] and before each High release.

## 11. Roles

| Role | Task |
| --- | --- |
| Performance owner \[name\] | Owns this template, the workload, and the verdict |
| Change author | Sets the risk tier, does the tests, completes the test record |
| Reviewer | Approves the result checks |
| Release approver \[role\] | Approves the verdict and the waivers |
| Module owner | Supplies traffic forecasts and corrects module regressions |

**Before the first use**

- [ ] Confirm the use of each tool (section 6).
- [ ] Set the targets from three baseline runs (section 2).
- [ ] Name the performance owner and the release approver.
- [ ] Get the forecast peak from the first consumers.

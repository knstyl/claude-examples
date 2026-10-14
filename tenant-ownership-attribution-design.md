# Design Hand-off: Tenant Ownership Attribution for Viaduct Telemetry

**Status:** Draft for spec generation (speckit `/specify` → `/plan`)
**Scope:** Viaduct multi-tenant GraphQL service (Kotlin · Ktor · Jetty · Guice), monorepo
**Goal in one line:** Every metric, span, and error emitted by the service can be attributed to the owning **tenant module**, and from there to a **team** and **PagerDuty service**. The ownership mapping is declared once, enforced at build time, and resolved late.

---

## 0. Instructions for the implementing agent (repo reconciliation)

Before running `/plan`, reconcile this doc against the repository and **delete or rewrite any section that conflicts with what already exists**. Specifically, verify and record answers inline:

1. **Viaduct version and migration state** (1.x → 2.0). Find out which instrumentation hooks exist in the version on `main`: `TaggedMetricInstrumentation`, `ResolverInstrumentation`, and any successor in 2.0. Prefer framework hooks over custom wrappers.
2. **KSP module metadata.** Locate the build-time pipeline that extracts resolver/module metadata. Determine whether it already yields `schema coordinate → tenant module`. If it does, FR-4 reduces to "emit the existing data as an artifact."
3. **Existing OTel setup.** Check for SDK vs. agent, exporter (OTLP endpoint), metrics backend (Prometheus-compatible vs. Datadog vs. other), and any existing resolver or HTTP client spans.
4. **Gateway client module.** Find the shared module housing the REST API clients and how they are constructed (Ktor client? Guice-provided?). Identify the single interception point.
5. **Module layout.** Record how tenant modules are laid out on disk and how a module's identity is named. That name becomes the canonical `tenant.module` value.
6. **Existing architectural rules.** List the current konsist tests and detekt convention plugin so the new rules fit the existing patterns.
7. **Custom directive support.** Confirm the Viaduct version in use allows custom schema directives to be declared and read at build time.

Anything already implemented → mark the FR as **DONE (existing)** and point to the file. Anything that contradicts the repo → the repo wins unless this doc states a reason.

---

## 1. Context

- The service hosts multiple **tenant modules**. Each is a slice of schema plus the resolvers that implement it, owned by one team. Teams contribute to a shared graph (self-service is the primary product goal).
- Data comes from a growing set of external REST APIs (target 50–100+) through a shared gateway-client module. The gateway is shared, but the *cost and failures* belong to the calling tenant.
- Modules extend each other's types, so **type owner ≠ field owner** in general.
- Fields are resolved heavily through **reentrancy (subqueries)**. A field's latency therefore often includes time spent in *other* tenants' resolvers.
- Future state: Viaduct runs as a thin subgraph behind Apollo Router. Subgraph will become the coarse ownership boundary, but field-level attribution inside Viaduct is still required.
- Reference design: Airbnb's Viaduct observability model (GraphQLConf 2026). It uses one owner per field, four attribution levels (system, operation, tenant, field), "own time" vs. total time, and cardinality-aware metrics.

## 2. Goals / Non-goals

**Goals**
- G1. A single source of truth for module → owner (team, on-call/PagerDuty service, chat channel).
- G2. Build fails if any tenant module or schema field lacks a resolvable owner.
- G3. Runtime telemetry carries a stable, low-cardinality **module key**, at field and downstream-call granularity.
- G4. Team and PagerDuty attributes are resolved **late** (at query, collector, or backend time), so re-orgs don't require redeploying or re-emitting series.
- G5. Alerts route to the owning PagerDuty service through labels, with no hand-maintained routing tables.
- G6. Cross-tenant latency is attributable: own time vs. total time.

**Non-goals (this iteration)**
- Schema-declared SLOs/alerts (e.g., `@slo` directive). This is reserved as Phase 4.
- Per-client/per-consumer attribution (who *called* the graph). This is a separate concern.
- Replacing CODEOWNERS for review routing. CODEOWNERS may be *generated* from the manifest later.

## 3. Key decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Ownership is declared **per tenant module** in a manifest file in the module root. | Module is the unit of ownership. Per-field declaration everywhere is noisy and drifts. |
| D2 | Manifest uses **Backstage `catalog-info.yaml` format** (`spec.owner`, `metadata.annotations["pagerduty.com/service-id"]`). | Industry standard, and tool-portable (Backstage, OpsLevel, Cortex can ingest it). [NEEDS CLARIFICATION: does the org run Backstage or another catalog? If not, keep the same keys in `tenant-owner.yaml`.] |
| D3 | A schema directive `@owner(module: String!)` is allowed **only as an override** where a field's owner differs from its defining module. | Covers cross-module type extensions without making every field declare ownership. |
| D4 | The **telemetry key is the module name**, not the team name. | Module names are stable. Team names and PagerDuty IDs change with re-orgs. Keeps the hot path free of org metadata. |
| D5 | Module → team/PD resolution happens late, through a **generated ownership map** exposed as (a) a build artifact and (b) an info metric. | Re-orgs become a config change. Works with any Prometheus-compatible backend. |
| D6 | **Spans** may carry full owner attributes (module, team, PD service) from the in-memory map. **Metrics** carry only the module. | Span attributes have no series-cardinality cost and improve trace search. Metric labels do have that cost. |
| D7 | Custom attribute namespace is `viaduct.*`. Do not use un-namespaced `graphql.field.*`. | OTel GraphQL semconv only defines operation-level attributes. Namespacing avoids future semconv collisions. |
| D8 | Module identity propagates through **OTel `Context`**, bridged into coroutines. | The gateway clients and any async work inherit the calling module automatically. |

## 4. Functional requirements

### Phase 1: Ownership metadata and enforcement

- **FR-1 Manifest.** Every tenant module has a manifest at its root containing: module id (must match the canonical module name), owning team, PagerDuty service id, and chat channel (optional).
  ```yaml
  # <module-root>/catalog-info.yaml
  apiVersion: backstage.io/v1alpha1
  kind: Component
  metadata:
    name: accounts            # == canonical tenant module id
    annotations:
      pagerduty.com/service-id: PXXXXXX
      slack.com/channel: "#team-accounts-alerts"
  spec:
    type: graphql-tenant-module
    owner: team-accounts
    lifecycle: production
  ```
- **FR-2 Override directive.** Declare `directive @owner(module: String!) on FIELD_DEFINITION | OBJECT` in the shared schema. The value must reference an existing module id.
- **FR-3 Enforcement (konsist + build).**
  - konsist: every tenant module directory contains a valid manifest, and its `metadata.name` equals the module id.
  - Build-time check: every `@owner(module:)` value resolves to a known module.
  - Build-time check: every schema coordinate (`Type.field`) resolves to exactly one owning module.
  - Failures are build errors with an actionable message naming the file and coordinate.
- **FR-4 Ownership map artifact.** At build time, generate `ownership-map.json`:
  ```json
  {
    "modules": { "accounts": { "team": "team-accounts", "pagerduty": "PXXXXXX", "channel": "#..." } },
    "coordinates": { "CreditCardAccount.balance": "accounts", "Customer.accounts": "accounts" }
  }
  ```
  Publish it alongside the SDL/codegen artifact in Artifactory, so the catalog SPA, dashboards, and alert tooling consume the same map. Prefer extending the existing KSP metadata pipeline over a new generator.

### Phase 2: Runtime attribution

- **FR-5 Resolver instrumentation.** Use Viaduct's resolver instrumentation hook (do not wrap tenant code) to emit the following.

  | Instrument | Type | Attributes |
  |---|---|---|
  | `viaduct.resolver.duration` | histogram (s) | `viaduct.tenant.module`, `graphql.operation.name`, `viaduct.outcome` (`ok`/`error`) |
  | `viaduct.resolver.errors` | counter | `viaduct.tenant.module`, `graphql.operation.name`, `error.type` |
  | `viaduct.field.duration` | histogram (s) | `viaduct.tenant.module`, `viaduct.field.coordinate`; **allowlisted coordinates only** (see FR-9) |

  Resolver spans carry `viaduct.tenant.module`, `viaduct.field.coordinate`, `viaduct.owner.team`, and `viaduct.owner.pagerduty_service` (per D6).
- **FR-6 Context propagation.** On resolver entry, put the module id in OTel `Context` and bridge it into coroutines (e.g., `opentelemetry-extension-kotlin` `Context.asContextElement()`). Reentrant subqueries push the *callee's* module. The caller's module is restored on return.
- **FR-7 Downstream client attribution.** At the single interception point in the gateway-client module, emit:

  | Instrument | Type | Attributes |
  |---|---|---|
  | `viaduct.downstream.duration` | histogram (s) | `viaduct.tenant.module` (caller, from Context), `viaduct.downstream.api` (stable client name, not the URL), `http.response.status_code` class |
  | `viaduct.downstream.errors` | counter | same as above, plus `error.type` |

  HTTP client spans also carry `viaduct.tenant.module`. Cache hits and misses (if the caching layer exists) carry the same caller module.
- **FR-8 Errors.** GraphQL errors and logged exceptions include `viaduct.tenant.module` and `viaduct.field.coordinate` (in the error extensions for internal logs only, never in client-facing responses).
- **FR-9 Cardinality guardrails.**
  - Module-level metrics are always on.
  - Field-level metrics are **opt-in by allowlist**, configured per module (default: off, or top-N by traffic).
  - `graphql.operation.name` values are bounded: unnamed or unknown operations are bucketed to `__unnamed__`/`__other__`.
  - No raw paths, IDs, or URLs in metric attributes.
  - Document the expected series-count budget in `/plan`.

### Phase 3: Owner resolution, alert routing, own time

- **FR-10 Owner info metric.** On startup, emit one gauge series per module from the ownership map:
  `viaduct_tenant_owner_info{module, team, pagerduty_service, channel} = 1`.
  Dashboards and alert rules join on `module`, e.g.:
  ```promql
  sum by (module) (rate(viaduct_resolver_errors_total[5m]))
    * on (module) group_left (team, pagerduty_service) viaduct_tenant_owner_info
  ```
  [NEEDS CLARIFICATION: metrics backend. If it is not Prometheus-compatible, implement the equivalent with collector-side enrichment (OTel Collector transform/attributes processor, or a small custom processor fed by `ownership-map.json`) or a backend-native lookup table.]
- **FR-11 Alert routing.** Alert rules include `pagerduty_service` from the join. Alertmanager routes, or PagerDuty Event Orchestration, key on that label. The platform team owns system- and operation-level alerts. Each tenant module gets templated default alerts (error rate, p95/p99 latency, downstream error rate).
- **FR-12 Own time vs. total time.** Emit `viaduct.resolver.own_time` (histogram) alongside total duration. Own time = resolver wall time minus the **union of intervals** spent awaiting subqueries that resolve fields owned by a *different* module. The interval union handles concurrent children. Same-module subqueries count as own time. Default tenant alerts use own time, so that a downstream tenant's regression pages the downstream owner and not the caller.

### Phase 4 (future, out of scope): schema-declared monitoring

- `@slo(latencyP99Ms:, errorRatePct:)` or similar, compiled into generated alert rules from the ownership map. Listed here so Phase 1–3 designs don't block it.

## 5. Acceptance criteria

- AC-1: Removing a module's manifest, or giving it a mismatched `metadata.name`, fails the build with a message naming the module.
- AC-2: An `@owner(module: "does-not-exist")` fails the build.
- AC-3: `ownership-map.json` is produced by the build, published with the SDL artifact, and contains every schema coordinate.
- AC-4: A query touching fields from two modules produces resolver spans tagged with each field's correct module, team, and PagerDuty service.
- AC-5: A resolver in module A that calls a gateway client produces a downstream span and metric tagged `viaduct.tenant.module=A`. This also holds when the call happens inside a coroutine or async block.
- AC-6: A reentrant subquery from module A into module B attributes B's resolver time to B. A's `own_time` excludes it, and A's total `duration` includes it.
- AC-7: Changing a module's team or PagerDuty service in its manifest changes alert routing after deploy, **with no change to emitted metric series** other than the info metric.
- AC-8: Field-level metrics appear only for allowlisted coordinates. Total metric series stay within the budget documented in the plan.
- AC-9: No tenant module code changes are required to get Phase 2 telemetry.

## 6. Risks and open questions

- [NEEDS CLARIFICATION] Catalog of record (Backstage, another tool, or none). This decides the manifest file name and format (D2).
- [NEEDS CLARIFICATION] Metrics backend and alerting stack. This decides between FR-10 as an info-metric join and collector enrichment.
- [NEEDS CLARIFICATION] Does Viaduct 2.0 change the instrumentation hook API? Build Phase 2 against the post-migration API if the migration lands first.
- Risk: Own-time computation (FR-12) depends on visibility into subquery lifecycle. If the engine doesn't expose it, defer FR-12 and document the gap.
- Risk: Coroutine context loss in third-party client code. Mitigate with the single gateway interception point and a test for AC-5.
- Risk: Shared or "common" modules (gateway clients, utilities) need an owner too. Assign them to the platform team explicitly. Do not leave them unowned.

## 7. Suggested task breakdown (for `/tasks`)

1. Define manifest schema plus konsist rule (FR-1, FR-3).
2. Declare `@owner` directive and build-time coordinate resolution (FR-2, FR-3).
3. Extend KSP metadata output to `ownership-map.json` and publish it with the SDL (FR-4).
4. Load the ownership map at runtime (Guice singleton).
5. Resolver instrumentation for metrics and spans (FR-5, FR-8).
6. Context propagation and coroutine bridging (FR-6).
7. Gateway-client interceptor (FR-7).
8. Cardinality allowlist config (FR-9).
9. Owner info metric and an example dashboard and alert rule (FR-10, FR-11).
10. Own-time computation (FR-12).
11. Tests for AC-1 through AC-9.

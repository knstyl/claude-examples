# Viaduct End-to-End Distributed Tracing

Oct 29, 2026 · @Sam

## Overview

Every GraphQL request to the Viaduct service produces one OpenTelemetry trace covering its full lifecycle, from Jetty accepting the connection to the last response byte written. The trace is exported to New Relic, where its waterfall view serves as a Gantt chart of the request.

**Problem.** Today there is no per-request view of where time goes. A slow request could be spent in auth, query planning, a single slow resolver, a cache miss, or a downstream REST API, and none of these can be told apart.

**Goals**

- One trace per request, with a correct parent/child span tree from server entry to response write.
- Resolvers that run concurrently appear as sibling spans with the same start offset; a slower sibling shows as a longer bar.
- Every outbound REST call and every cache operation is a span, attributable to the resolver that caused it.
- Reentrant subqueries appear nested under the resolver that issued them.
- Spans carry tenant-module ownership (team, PagerDuty service) so hot spots route to an owner.
- Traces are queryable in New Relic for both single-request drill-down and fleet-wide hot-spot analysis.

**Non-goals**

- Metrics and logs pipelines (field metrics already exist; this design reuses their ownership metadata only).
- Instrumenting downstream REST services themselves; this design only propagates context to them.
- Continuous profiling or CPU-level attribution inside a span.

## Scope

The request trace covers every stage a request passes through inside the service process. Application startup is traced separately because it happens once per container, not per request.

| Stage | In scope | Span source |
| --- | --- | --- |
| HTTP server entry (Jetty connector, Ktor routing) | Yes | Auto-instrumentation |
| Ktor pipeline plugins: auth/JWT verification, tenant and scope resolution, rate limiting | Yes | Manual |
| Request body read and JSON decode | Yes | Manual |
| Per-request Guice scope and Viaduct execution context build | Yes | Manual |
| GraphQL parse, validate, operation planning | Yes | Viaduct hook |
| Field execution: resolvers, batch resolvers, node resolvers | Yes | Viaduct hook |
| Reentrant subqueries | Yes | Viaduct hook |
| Cache reads, writes, request coalescing | Yes | Manual (cache layer) |
| Outbound REST calls via the common gateway client module | Yes | Auto + manual enrichment |
| Retries and circuit-breaker decisions | Yes | Span events on the client span |
| Eligibility rule evaluation | Yes | Manual |
| Response serialization and write | Yes | Manual |
| Application startup: Guice injector, schema and module load, warmup | Separate `app.startup` trace | Manual |
| Trivial property fetchers (fields read off an already-loaded object) | No | Excluded |
| Downstream services' internal work | No | Out of process |

## Architecture

Tracing is built in three layers: auto-instrumentation for transport, a Viaduct engine hook for GraphQL execution, and a small set of manual spans for service-specific work. Application code depends only on the OpenTelemetry API; the SDK and exporters are configured at the edge.

| Layer | Covers | Mechanism |
| --- | --- | --- |
| Transport | Jetty/Ktor server span, outbound HTTP client spans, W3C `traceparent` extraction and injection | OpenTelemetry Java agent, or library instrumentation (`opentelemetry-ktor` server plugin plus HTTP client interceptors) where the agent is not permitted |
| GraphQL execution | Parse, validate, plan, field resolution, subqueries | A `TracingInstrumentation` registered with the Viaduct engine at its instrumentation extension point; fallback is a wrapper applied when resolvers are registered |
| Service-specific | Bootstrap plugins, cache, eligibility, serialization, startup | Manual spans through a shared `Tracer` |

**Components to build**

- `TracingModule` (Guice): binds `OpenTelemetry`, `Tracer` (instrumentation scope `viaduct-service`), and the span helpers below.
- `TracingInstrumentation`: maps Viaduct execution callbacks to spans (see Span model).
- `SpanHelpers`: a Kotlin `suspend inline fun <T> traced(name, kind, attrs, block)` that starts a span, runs the block inside the span's context, records exceptions, and ends the span when the block completes.
- `TracedCache`: a decorator over the cache interface that emits cache spans.
- `TracedGatewayClient`: enrichment for the common gateway client module (API name, URL template, retry and breaker events).
- `ModuleOwnershipResolver`: reads each tenant module's ownership YAML once at startup and supplies ownership attributes by module.
- `TracingConfig`: detail level, sampling ratio, debug-header name, attribute size limits.

**Data flow**

1. Client request arrives with or without `traceparent`; the server span starts as root or continues the caller's trace.
2. Ktor plugins and Viaduct execution run as children of the server span.
3. Gateway clients inject `traceparent` into every outbound REST call.
4. The SDK batch span processor exports OTLP to an OpenTelemetry Collector sidecar.
5. The Collector applies tail sampling and forwards to New Relic's OTLP endpoint.

## Span model

A request trace has a fixed skeleton of lifecycle spans, with a variable resolver subtree under execution. Concurrent resolvers share a parent and start at the same offset.

```text
POST /graphql                         SERVER    (root)
├─ request.bootstrap                  INTERNAL
│  ├─ auth.verify                     INTERNAL
│  ├─ tenant.resolve                  INTERNAL
│  ├─ scope.resolve                   INTERNAL
│  └─ request.decode                  INTERNAL
├─ <op type> <op name>                INTERNAL  (e.g. "query GetCustomer")
│  ├─ graphql.parse                   INTERNAL
│  ├─ graphql.validate                INTERNAL
│  ├─ viaduct.plan                    INTERNAL
│  └─ viaduct.execute                 INTERNAL
│     ├─ resolve Customer.accounts    INTERNAL  ┐
│     │  ├─ cache.get accounts        INTERNAL  │ concurrent
│     │  └─ GET accounts-api          CLIENT    │ siblings,
│     ├─ resolve Customer.offers      INTERNAL  │ same start
│     │  └─ viaduct.subquery          INTERNAL  │
│     │     └─ resolve Offer.eligible INTERNAL  │
│     │        ├─ eligibility.eval    INTERNAL  │
│     │        └─ GET eligibility-svc CLIENT    │
│     └─ resolve Customer.profile     INTERNAL  ┘
│        └─ cache.get profile (hit)   INTERNAL
├─ response.serialize                 INTERNAL
└─ response.write                     INTERNAL

app.startup                           INTERNAL  (separate trace, once per container)
├─ guice.injector.create
├─ viaduct.schema.load
├─ viaduct.modules.register
└─ app.warmup
```

**Naming rules**

| Span | Name format | Kind |
| --- | --- | --- |
| Server | `{method} {route}` (auto) | SERVER |
| Operation | `{operation type} {operation name}`; `{operation type}` alone when anonymous | INTERNAL |
| Resolver | `resolve {ParentType}.{field}` | INTERNAL |
| Batch resolver | `resolve.batch {ParentType}.{field}` | INTERNAL |
| Subquery | `viaduct.subquery` | INTERNAL |
| Cache | `cache.{get\|put\|invalidate} {cache name}` | INTERNAL |
| REST call | `{method} {api name}` | CLIENT |

Span names never contain field arguments, IDs or other per-request values, so names stay low cardinality and group cleanly in New Relic.

## Context propagation and timing

The waterfall is only correct if every span gets the right parent and ends when its work actually completes. These two rules carry the design.

**Propagation rules**

1. Every coroutine launched on the request path carries the current OpenTelemetry context as a coroutine context element (`opentelemetry-extension-kotlin`, `Context.current().asContextElement()`), including inside Viaduct's own dispatch where the engine allows it.
2. Every `Executor`/`ExecutorService` used on the request path is wrapped with `Context.taskWrapping`.
3. `CompletableFuture` chains that hop threads capture context at creation and restore it in the continuation.
4. Sibling resolvers are started from the parent field's context, never from each other, so concurrent work renders as siblings rather than a false chain.
5. A subquery span is a child of the resolver that issued it; resolvers inside the subquery are its children.
6. Outbound REST calls inject W3C `traceparent` and `tracestate`. Inbound `traceparent` is honoured; `baggage` is not propagated outbound.

**Timing rules**

- A resolver span starts when the engine invokes the resolver and ends when its result is available (the `Deferred` or `CompletableFuture` completes), not when the resolver function returns.
- When a resolver waits on a batch, it records a `batch.enqueued` span event at enqueue time and `batch.dispatched` when the batch fires, separating waiting from working.
- A batch resolver gets one `resolve.batch` span per dispatch, with `batch.size` set and span links to the spans of the resolvers that enqueued keys.
- A cache span covers only the cache round trip. On a miss, the loader's REST call is a sibling of the cache span under the resolver, not a child of it.
- With request coalescing, the leader's span does the REST call; followers get a span event `coalesced.wait` and a span link to the leader's span.

## Attributes

Attributes follow OpenTelemetry semantic conventions where one exists; service-specific attributes use the `viaduct.` prefix. No attribute holds customer data.

| Span type | Attributes |
| --- | --- |
| Resource (all spans) | `service.name`, `service.version`, `deployment.environment.name`, `cloud.region`, `viaduct.cell` |
| Server / root | auto HTTP attributes; `viaduct.tenant`, `viaduct.scope`, `graphql.operation.name`, `graphql.operation.type`, `viaduct.error_count`, `viaduct.field_span_count` |
| Operation | `graphql.operation.name`, `graphql.operation.type`, `graphql.document` (sanitized), `viaduct.document_hash` |
| Resolver | `graphql.field.path` (indices collapsed to `[]`), `graphql.field.parent_type`, `graphql.field.name`, `viaduct.module`, `viaduct.owner.team`, `viaduct.owner.pagerduty_service`, `viaduct.resolver.kind` (field, batch, node) |
| Batch resolver | resolver attributes + `viaduct.batch.size` |
| Subquery | `viaduct.subquery.depth`, `viaduct.module` of the issuing resolver |
| Cache | `viaduct.cache.name`, `viaduct.cache.layer` (local, distributed), `viaduct.cache.hit`, `viaduct.cache.coalesced`, `viaduct.cache.key_hash` |
| REST call | auto HTTP client attributes; `peer.service` (gateway API name), `url.template`, `viaduct.retry.count`, `viaduct.breaker.state` |
| Bootstrap | `viaduct.auth.method`, `viaduct.auth.outcome`, `viaduct.tenant`, `viaduct.scope` |

**Ownership attribution**

- `viaduct.owner.team` and `viaduct.owner.pagerduty_service` come from the tenant module's ownership YAML, the same source used for field metrics.
- Values are resolved once at startup into an immutable map keyed by module; no file I/O on the request path.
- A module without ownership metadata gets `viaduct.owner.team=unowned`.

**Data-safety rules**

- `graphql.document` is the query with all literal values replaced by `?`, truncated to 4,000 characters. Variables are never recorded.
- `url.template` is the gateway client's path template (`/customers/{id}/accounts`), never the resolved URL or query string.
- Cache keys are recorded only as a SHA-256 prefix (`key_hash`), never raw.
- Request and response headers are not recorded except an explicit allowlist (`content-type`, `user-agent`).

## Cardinality and detail levels

Span count per trace is bounded by a configurable detail level and a hard cap, so a large list query cannot produce an unreadable or truncated trace.

| Detail level | Spans emitted | Default for |
| --- | --- | --- |
| `off` | Server span only | Emergency kill switch |
| `lifecycle` | Bootstrap, operation phases, serialization, REST calls, cache | — |
| `resolvers` | `lifecycle` + custom resolvers, batch resolvers, subqueries | Production |
| `all-fields` | `resolvers` + trivial property fetchers | Debug requests only |

**Rules**

- List items resolved by a batch resolver produce one batch span per dispatch, never one span per item.
- Per-item resolvers inside a list are spanned for the first N items (default 25); the rest increment `viaduct.spans_suppressed` on the parent span.
- A per-trace cap (default 500 spans) stops new field spans once reached; lifecycle and REST spans are always emitted. The root span records `viaduct.span_cap_reached=true`.
- A debug header (default `x-viaduct-trace-debug: 1`), accepted only from authenticated internal callers, forces sampling and the `all-fields` level for that request.
- Detail level, item limit and cap are runtime configuration, changeable without redeploy.

## Errors and status

GraphQL returns HTTP 200 with partial errors, so error state is set on the span where the failure happened, not only on the server span.

- A resolver that throws or returns a field error: span status `ERROR`, `recordException` with type and message (message passed through the same sanitizer as the document), and `graphql.error.code` when the error carries one.
- A REST call with a 5xx, timeout or breaker-open outcome: status `ERROR`. A 4xx is `ERROR` only when it fails the field.
- Each retry attempt is a span event `retry` with attempt number and reason; a breaker rejection is a span event `breaker.rejected`.
- The root span sets `viaduct.error_count` (number of entries in the response `errors` array) and `viaduct.partial=true` when data and errors are both present.
- The root span's status is `ERROR` only for HTTP 5xx or a request-level GraphQL failure (parse, validation, auth).

## Sampling and export

The service exports every started span to a local Collector, which decides what reaches New Relic. This keeps errors and slow requests at full fidelity without paying to store every fast, healthy trace.

**In-process SDK**

- Sampler: `parentbased_always_on`, so a sampled upstream caller's decision is respected and the Collector makes the final call.
- `BatchSpanProcessor`: bounded queue with drop-on-full; a dropped-span counter is exported as a metric.
- Exporter: OTLP/gRPC to `localhost:4317` (Collector sidecar in the Fargate task).
- Span limits: attribute value length 4,000 characters; events per span 32; links per span 32.

**Collector**

- Receiver: OTLP.
- Processors: `memory_limiter`, `batch`, `tail_sampling`.
- Tail-sampling policies, evaluated in order:
  1. Keep 100% of traces with any span in `ERROR`.
  2. Keep 100% of traces whose root span exceeds the latency threshold (initially 1,000 ms, tuned to roughly p95).
  3. Keep 100% of traces from debug-header requests (`viaduct.debug=true` on the root).
  4. Keep a probabilistic share of the rest (initially 10%).
- Exporter: OTLP/HTTP to New Relic's OTLP endpoint (`otlp.nr-data.net`, or the EU endpoint for EU accounts) with the license key in the `api-key` header, sourced from the secrets manager.

**Resource identity**

- `service.name` is the same across all containers of the service, so New Relic groups them as one entity.
- `service.version` is the build version, so regressions can be compared across deploys.

## Analysis in New Relic

Single requests are read in New Relic's distributed tracing waterfall, which is the Gantt chart this design targets. Fleet-wide hot spots come from NRQL over the `Span` event type.

**Single request**

- Open the trace from the service's distributed tracing view or by `trace.id`.
- Concurrent resolvers show as sibling bars with the same left edge; the longest bar on the critical path is the hot spot.
- A custom Gantt can be built from the raw spans:

```sql
FROM Span SELECT name, timestamp, duration.ms, id, parent.id
WHERE trace.id = '<trace id>' ORDER BY timestamp LIMIT MAX
```

**Slowest fields across the fleet**

```sql
FROM Span SELECT percentile(duration.ms, 50, 95, 99), count(*)
WHERE service.name = 'viaduct-service' AND name LIKE 'resolve %'
FACET graphql.field.path SINCE 1 day ago LIMIT 25
```

**Slowest downstream APIs**

```sql
FROM Span SELECT percentile(duration.ms, 95), percentage(count(*), WHERE otel.status_code = 'ERROR')
WHERE service.name = 'viaduct-service' AND span.kind = 'client'
FACET peer.service SINCE 1 day ago
```

**Cache effectiveness by cache**

```sql
FROM Span SELECT percentage(count(*), WHERE viaduct.cache.hit IS TRUE), average(duration.ms)
WHERE name LIKE 'cache.get %' FACET viaduct.cache.name SINCE 1 day ago
```

**Hot spots by owning team**

```sql
FROM Span SELECT sum(duration.ms), percentile(duration.ms, 95)
WHERE name LIKE 'resolve %' FACET viaduct.owner.team, viaduct.module SINCE 1 week ago
```

A dashboard with these queries is part of the deliverable. Attribute names in the queries must be confirmed against how New Relic ingests OTLP attributes (see Open questions).

## Non-functional requirements

Tracing at the `resolvers` level must add no more than 3% to p95 request latency and 5% to CPU, measured against tracing `off` under the same load test.

| ID | Requirement |
| --- | --- |
| NFR-1 | p95 latency overhead ≤ 3% at `resolvers` level, measured by load test |
| NFR-2 | CPU overhead ≤ 5% at `resolvers` level |
| NFR-3 | No blocking I/O on the request path from tracing; export is asynchronous |
| NFR-4 | If the Collector is down, the service keeps serving; spans are dropped and counted |
| NFR-5 | No customer data in any span name, attribute or event (Attributes → data-safety rules) |
| NFR-6 | Tracing configuration (level, limits, sampling) changes take effect without redeploy |
| NFR-7 | Tenant modules get resolver spans with no code changes in the module |
| NFR-8 | Application code depends only on `opentelemetry-api`; SDK wiring lives in `TracingModule` |

## Functional requirements and acceptance criteria

Each requirement is accepted by an automated test using the OpenTelemetry SDK's in-memory span exporter, unless noted.

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| FR-1 | One trace per request | All spans for a request share one `trace.id`; exactly one root SERVER span |
| FR-2 | Upstream continuation | A request with a valid `traceparent` produces spans in the caller's trace with the caller's span as parent |
| FR-3 | Lifecycle spans | A request yields `request.bootstrap`, operation, `graphql.parse`, `graphql.validate`, `viaduct.plan`, `viaduct.execute`, `response.serialize`, `response.write`, all with correct parents |
| FR-4 | Concurrent siblings | For a query selecting three independent resolvers with injected delays of 50, 50 and 200 ms: all three share one parent, start within 5 ms of each other, and the 200 ms one has the longest duration |
| FR-5 | Accurate async end | A resolver whose future completes after 100 ms has span duration ≥ 100 ms |
| FR-6 | Subquery nesting | A resolver issuing a subquery has a `viaduct.subquery` child whose resolvers are its children |
| FR-7 | REST spans | Each gateway call produces a CLIENT span under the issuing resolver with `peer.service` and `url.template`, and the outbound request carries `traceparent` |
| FR-8 | Cache spans | Hit and miss each produce a cache span with `viaduct.cache.hit` set; on a miss the REST span is a sibling of the cache span |
| FR-9 | Batching | N keys batched into one dispatch yield one `resolve.batch` span with `viaduct.batch.size = N` and links to the enqueuing spans |
| FR-10 | Coalescing | Two concurrent identical loads produce one REST span; the follower has a `coalesced.wait` event and a link to the leader |
| FR-11 | Errors | A failing resolver's span has status ERROR and an exception event; the root span has `viaduct.error_count` matching the response |
| FR-12 | Ownership | Resolver spans carry `viaduct.owner.team` and `viaduct.owner.pagerduty_service` from the module's YAML; missing YAML yields `unowned` |
| FR-13 | Detail levels | Each level emits exactly the span set in Cardinality and detail levels |
| FR-14 | Span cap | A query exceeding the cap stops emitting field spans, keeps lifecycle and REST spans, and sets `viaduct.span_cap_reached` |
| FR-15 | Debug header | An authenticated internal request with the debug header is traced at `all-fields` and marked `viaduct.debug=true`; the header is ignored from other callers |
| FR-16 | Data safety | A query with literal arguments and variables produces no span containing those values (asserted by scanning all span data) |
| FR-17 | Startup trace | Container start produces one `app.startup` trace with its child spans |
| FR-18 | New Relic | In a non-prod environment, a request's trace appears in New Relic's waterfall with correct nesting and the dashboard queries return data (manual check) |

## Rollout

Delivery runs in four phases, each shippable on its own and each gated on its acceptance criteria passing.

1. **Foundation.** `TracingModule`, SDK and Collector sidecar, export to New Relic non-prod, server and REST client spans, resource attributes. Gate: FR-1, FR-2, FR-7, FR-18 (server and client spans only).
2. **Lifecycle and execution.** Bootstrap spans, Viaduct instrumentation hook, operation phases, resolver and subquery spans, context propagation, ownership attributes. Gate: FR-3 to FR-6, FR-11, FR-12, FR-16.
3. **Cache, batching and controls.** Cache and coalescing spans, batch spans and links, detail levels, span cap, debug header, startup trace. Gate: FR-8 to FR-10, FR-13 to FR-15, FR-17.
4. **Production.** Load-test overhead, tune tail-sampling threshold and ratio, publish the New Relic dashboard, enable in production at `resolvers` level. Gate: NFR-1 to NFR-4, FR-18 in production.

## Open questions

- [ ] Which instrumentation extension point does Viaduct 2.0 expose for parse, validate, plan and field execution, and does it fire on completion of async results? This decides between the engine hook and the resolver-registration wrapper.
- [ ] Does Viaduct 2.0's engine dispatch preserve coroutine context elements, or does context need restoring inside the hook?
- [ ] Is the OpenTelemetry Java agent permitted in the managed environment, or is library instrumentation required?
- [ ] Which HTTP client does the common gateway module use, and is there auto-instrumentation for it?
- [ ] Is a Collector sidecar allowed in the Fargate task definition, or is there a shared Collector or New Relic infrastructure agent to send to?
- [ ] New Relic account limits for spans per trace, attributes per span and attribute value length; confirm the 500-span cap and 4,000-character limit fit within them.
- [ ] How New Relic names ingested OTLP attributes for parent span ID, span kind and status, so the NRQL in Analysis matches.
- [ ] Initial tail-sampling latency threshold and probabilistic ratio, based on current traffic volume and New Relic ingest budget.
- [ ] Which callers count as authenticated internal callers for the debug header.

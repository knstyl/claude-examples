# Central Graph Reading List: Sources Mapped to the Viaduct TRD

Oct 13, 2026 · @Sam

## How to use this list

Thirteen public sources on running a central graph with hosted resolver logic at scale. Each one is mapped to the TRD sections it can back with evidence. Airbnb's three Viaduct posts are the primary references. Netflix is the federated counterpoint. Meta, Twitter, LinkedIn, Zalando and Expedia round out the alternatives.

- **Tier 1 — design of record:** Airbnb Viaduct posts. These are the closest match to a multi-tenant hosted-resolver model.
- **Tier 2 — contrasting model:** Netflix federation. It reaches one graph through distributed subgraph ownership instead of a shared runtime.
- **Tier 3 — lineage and alternatives:** Meta TAO, Twitter Strato, LinkedIn, Zalando, Expedia.

Rigor caveat: only TAO is peer-reviewed. Everything else is an engineering blog post, a conference talk or a vendor case study. Treat vendor-authored items (Apollo) as directional.

## Source catalog

Sources are numbered S1–S12. The matrix and notes below use these numbers.

| # | Source | Org | Year | Type | What it gives you |
| --- | --- | --- | --- | --- | --- |
| S1 | [Taming SOA Using a Data-Oriented Service Mesh](https://medium.com/airbnb-engineering/taming-service-oriented-architecture-using-a-data-oriented-service-mesh-da771a841344) | Airbnb | 2020 | Blog | The original rationale: a mesh organized around data, not procedures |
| S2 | [Viaduct, Five Years On](https://airbnb.tech/data/viaduct-five-years-on-modernizing-the-data-oriented-service-mesh/) | Airbnb | 2025 | Blog | Scale metrics, Viaduct Modern, tenant modules, re-entrancy |
| S3 | [Viaduct 1.0 and the future of Airbnb's data mesh](https://airbnb.tech/?p=800) | Airbnb | 2026 | Blog | Stable API, multi-tenant runtime vs federation, Viaduct as a subgraph |
| S4 | [Viaduct: A New Alternative to Monoliths](https://www.csail.mit.edu/event/viaduct-new-alternative-monoliths) | Airbnb (MIT CSAIL) | — | Talk | Central schema plus modules as the replacement for microservices |
| S5 | [Airbnb's Open-Source GraphQL Framework](https://softwareengineeringdaily.com/podcasts/airbnbs-open-source-graphql-framework-with-adam-miskiewicz/) | Airbnb (SE Daily) | 2026 | Podcast | Scaling to millions of QPS, why they open-sourced it |
| S6 | [How Netflix Scales its API with GraphQL Federation, Pt 1](https://netflixtechblog.com/how-netflix-scales-its-api-with-graphql-federation-part-1-ae3557c187e2) | Netflix | 2020 | Blog | Studio Edge architecture, schema governance role, adoption cost |
| S7 | [Migrating Netflix to GraphQL Safely](https://netflixtechblog.com/migrating-netflix-to-graphql-safely-8e1e4d4f1e72) | Netflix | 2023 | Blog | Zero-downtime migration: A/B, replay testing, sticky canaries |
| S8 | [How Netflix transitioned to a federated supergraph](https://www.apollographql.com/blog/an-unexpected-journey-how-netflix-transitioned-to-a-federated-supergraph) | Netflix (Apollo) | 2024 | Vendor blog | Graph size: 150 subgraphs, 3,000+ types |
| S9 | [TAO: Facebook's Distributed Data Store for the Social Graph](https://www.usenix.org/conference/atc13/technical-sessions/presentation/bronson) | Meta | 2013 | Paper (USENIX ATC) | Storage-level graph, about 1B reads/sec |
| S10 | [GraphQL at Twitter](https://about.sourcegraph.com/graphql/graphql-at-twitter) | Twitter | 2019 | Talk write-up | Strato virtual database powering GraphQL, config-driven onboarding |
| S11 | [How LinkedIn Adopted a GraphQL Architecture](https://engineering.linkedin.com/blog/2023/how-linkedin-adopted-a-graphql-architecture-for-product-developm) | LinkedIn | 2023 | Blog | Schema generated from existing Rest.li entity contracts |
| S12 | [How we use GraphQL at Europe's largest fashion e-commerce company](https://engineering.zalando.com/posts/2021/03/how-we-use-graphql-at-europes-largest-fashion-e-commerce-company.html) | Zalando | 2021 | Blog | Unified BFF in one monorepo, and its risks |
| S13 | [Expedia Group customer story](https://www.apollographql.com/customers/expediagroup) | Expedia (Apollo) | 2019 | Vendor case study | Schema stitching (Loom) to federation |

Netflix S8 and Expedia S13 are written by Apollo, a GraphQL vendor.

## TRD mapping matrix

Architecture and governance have the deepest coverage. Testing and performance draw mostly on Airbnb and Netflix. ● = primary evidence, ○ = supporting.

| TRD section | Primary | Supporting |
| --- | --- | --- |
| Architecture and tenancy model | S1, S2, S3 | S4, S6, S10, S11 |
| Schema design and governance | S2, S6 | S8, S11, S12, S13 |
| Resolver model and hosted business logic | S2, S3 | S1, S10 |
| Performance and scale | S2, S5 | S8, S9 |
| Migration and rollout safety | S7 | S2, S13 |
| Testing and observability | S7, S3 | — |
| Coexistence with federation | S3, S6 | S13 |
| Org adoption and operating cost | S2, S6 | S12, S13 |

## Per-section notes

### Architecture and tenancy model

- Viaduct rests on three principles: a central schema, hosted business logic, and a re-entrant API (S2).
- The mesh, not the consumer, knows which service provides which data element (S1).
- Viaduct distributes development through modules on a shared multi-tenant runtime, unlike federation's separate subgraph servers (S3).
- Strato is the closest outside analogue: a virtual database that predates GraphQL at Twitter and powers it (S10).

### Schema design and governance

- Viaduct Modern formalized tenant modules: schema plus code, owned by a single team, composed via GraphQL (S2).
- Netflix needed a dedicated Studio Data Architect for data modeling across teams (S6).
- LinkedIn avoids hand-written graph schema by generating types from already-reviewed Rest.li entity schemas, plus lint rules (S11).

### Resolver model and hosted business logic

- The tenant API is down to two resolver types: node resolvers and field resolvers (S2).
- Re-entrancy: hosted logic composes with other hosted logic by issuing GraphQL fragments and queries, not RPC calls (S2).
- The framework separates a dynamically typed engine API from a statically typed tenant API, so each evolves independently (S2).

### Performance and scale

- Since 2020: traffic up 8x, 130+ tenant teams, 1.5M+ lines hosted, incident-minutes halved, cost linear with QPS (S2).
- Over 75% of Viaduct requests are internal; it has become the internal data access path, not only a client API (S2).
- Netflix Studio Edge: 150 subgraphs, 3,000+ types, about 2,800 queries and mutations (S8).

### Migration and rollout safety

- Netflix moved mobile apps off the Falcor monolith with zero downtime in two phases (S7).
- Phase 1 put a GraphQL shim on the monolith and validated it with A/B testing. Phase 2 moved to federated domain services, validated with replay testing and sticky canaries (S7).
- Airbnb ran the Classic and Modern tenant APIs on the new engine at the same time for gradual migration (S2).

### Testing and observability

- Replay testing compares responses across old and new implementations for idempotent queries (S7).
- Airbnb's GraphQLConf 2026 talks cover probabilistic testing, monitoring, sharding and LLM-generated mock data (S3).

### Coexistence with federation

- Viaduct can run as a subgraph inside a federated architecture (S3). This is the key reference for fitting a Viaduct-style service into a DGS federation stack.
- Expedia's path from stitching to federation shows the trade-off between code-based composition and declarative composition (S13).

### Org adoption and operating cost

- Airbnb kept operational overhead constant while the tenant count doubled (S2).
- Netflix flags federation as a high-commitment choice: learning DGS, running the gateway and migrating all require partner-team buy-in (S6).
- Zalando calls its single unified GraphQL monorepo a potential architectural and operational risk (S12).

## Suggested reading order

1. S1, then S2. These give the original thesis and the five-year evidence; most TRD citations come from S2.
2. S3. It covers the current API surface and the subgraph-in-federation option.
3. S6 and S7. These are the federated counterpoint and the migration-safety playbook.
4. S10 and S11. These show two other ways to get one graph: a virtual database, and schema generated from existing contracts.
5. S9, S12 and S13 as background, plus S4 and S5 if you want the authors' own framing.

For a domain tenant, this layout keeps roles separated and maps cleanly to how Viaduct's generated code wants to be consumed:

tenants/domain/accounts-core/
├── build.gradle.kts
└── src/
    ├── main/
    │   ├── kotlin/com/bank/graph/accounts/
    │   │   ├── resolvers/
    │   │   │   ├── node/          # NodeResolvers.* impls
    │   │   │   │   ├── CreditCardAccountNodeResolver.kt
    │   │   │   │   └── DepositAccountNodeResolver.kt
    │   │   │   └── field/         # field/batch resolvers, sub-package per type
    │   │   │       └── creditcard/
    │   │   │           └── CardDetailsResolver.kt
    │   │   ├── fetch/             # backing-data fetchers; orchestrates platform clients
    │   │   ├── mapping/           # downstream DTO → GRT builder functions, pure
    │   │   ├── dto/               # internal payload types for downstream responses
    │   │   └── config/            # DI wiring, tenant registration
    │   └── resources/graphql/     # this tenant's SDL, if colocated
    └── test/kotlin/...            # mirrors main; unit tests per resolver

The role boundaries that matter, in order of importance:

mapping/ split from resolvers/ is the highest-value separation. Resolvers should be thin: acquire data (from ctx, a fetcher, or a client), delegate to a pure mapping function, return the builder. Mapping functions taking a DTO and returning a GRT builder are unit-testable without resolver contexts or DefaultAbstractResolverTestBase scaffolding, and it's where most of your actual logic (currency handling, status normalization, null policy) lives. When everything's inline in resolvers, that logic is only testable through resolver-shaped tests.

Interrogate what those "pojos" are. Viaduct generates GRTs for every schema type — if Claude is hand-writing Kotlin classes that mirror schema types, that's not misplacement, it's duplication; delete them and use the generated builders. Legitimate hand-written types are only: DTOs for downstream response payloads (→ dto/, or better, colocated with the shared clients in platform/ so multiple tenants reuse them) and genuine internal domain logic types, which are rarer than agents assume.

fetch/ earns its existence once you use backing-data fields — it's where "one call to the card platform, held for three field projections" lives, distinct from both the resolver (schema-facing) and the platform client (transport-facing).

For view tenants, invert the top level: package per experience domain first, role second —

tenants/views/sdui/src/main/kotlin/com/bank/graph/views/
├── accountsservicing/
│   ├── AccountCardViewResolver.kt
│   └── AccountCardAssembler.kt      # fragment result → view type, pure
├── offers/
└── common/                          # formatting helpers only — no view types

View tenants have no node resolvers, no clients, no DTOs — just re-entrant resolvers plus assemblers — so role-based packaging would create three near-empty folders per screen family. Domain-first here also keeps the deletion-locality property at package level and makes the "two packages reaching for the same derived field" graduation signal visible in imports.

On the Claude Code behavior: agents mirror the structure they find, so an empty or flat module gets flat output. Two fixes that work better than prompting harder — put the package layout and the rules ("resolvers thin, logic in mapping/, never hand-write schema-shaped types, GRTs come from codegen") into the repo's CLAUDE.md, and keep one fully-fleshed exemplar tenant module in the tree. The exemplar is the stronger signal of the two; once one module demonstrates the shape, generated code tends to follow it. Given your managed setup, CLAUDE.md in the repo root travels with the checkout and needs no tooling changes.

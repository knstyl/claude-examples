# Kotlin Backend Rules (Ktor · Guice · Jetty)

Full rationale and examples: `docs/kotlin-backend-standards.md`. Read the matching section before changing DI wiring, coroutine code, routes, or persistence. Rule IDs in brackets point into it.

## Scope
- These rules apply to new and changed code only. Do not refactor untouched code to comply.
- Where the existing code in this repo uses a different convention, follow the repo and list the conflict in the PR description.
- Do not add a dependency without stating why in the PR.

## Done means
- `./gradlew build detekt` passes with zero warnings.
- No new `@Suppress`, detekt/ktlint baseline entries, or lint-config changes.
- New or changed routes have `testApplication` tests for the success path and each error mapping. Coroutine logic is tested with `runTest` and an injected test dispatcher.
- Any deviation from these rules is listed in the PR by rule ID.

## Types and nulls
1. No `!!` outside tests. [KT-NULL-1]
2. Expected outcomes (not found, conflict, ineligible) are sealed result types, not exceptions. `when` over sealed types and enums is exhaustive with no `else`. [KT-ERR-1, KT-TYP-4]
3. Signatures use read-only collections. Mutable state stays private. Guice singletons are stateless or thread-safe. [KT-IMM-2..3]
4. Use value classes for identifiers that cross module or API boundaries. Do not wrap every primitive. [KT-TYP-2]

## Coroutines
5. Never block a call coroutine. Blocking I/O (JDBC, blocking SDKs, files) runs in `withContext(ioDispatcher)` inside the class that blocks, with the dispatcher injected via a qualifier. [KT-CO-4]
6. No `GlobalScope`. No `runBlocking` outside `main` and tests. Fan-out uses `coroutineScope { async }`; partial-failure fan-out uses `supervisorScope` with per-child handling. [KT-CO-1..2]
7. Never swallow `CancellationException`. No `runCatching` around suspend calls; any broad catch rethrows it first. [KT-CO-3, KT-ERR-5]
8. Every remote call has a timeout. [KT-CO-5]
9. Bridge `CompletableFuture` with `await()`, never `get()` or `join()`. [KT-CO-10]
10. No `synchronized` or locks held across suspension; use `Mutex`, atomics, or confinement. [KT-CO-8]

## Guice
11. Constructor injection only: `class X @Inject constructor(private val dep: Dep)` with `jakarta.inject`. No field injection. No `injector.getInstance` outside `Application.module()`. [KT-DI-1..3]
12. Modules do no I/O and contain no environment conditionals; choose which modules to install at the root. [KT-DI-4..5]
13. No method interceptors (guice-persist `@Transactional`, retry, timing) on `suspend` functions. [KT-DI-9]
14. Multibinder/MapBinder injection of non-final types uses `@JvmSuppressWildcards`, e.g. `Set<@JvmSuppressWildcards Handler>`. [KT-DI-10]
15. Qualifiers are dedicated annotations, not `@Named` strings. [KT-DI-11]
16. Closeable resources (HTTP clients, pools, Kafka clients) are singletons closed on `ApplicationStopping`. [KT-DI-7]

## Ktor
17. Routes are thin: parse, validate, call one service, map the result. [KT-KTR-2]
18. HTTP errors are rendered only in `StatusPages`. Services never throw Ktor HTTP exceptions. [KT-ERR-7]
19. Configuration is read once into `@Serializable` classes and bound in Guice. No scattered `config.property(...)` lookups. Secrets come from environment variables. [KT-KTR-4]
20. One shared `HttpClient` per downstream, with `HttpTimeout` and `expectSuccess`. Never one per request. [KT-KTR-8]
21. One injected `Json` instance. DTOs are `@Serializable` and separate from domain and persistence types. Required fields are non-null with no default. [KT-API-1..3]

## Errors and logging
22. Catch specific exceptions. Catch-alls only at boundaries: `StatusPages`, consumer loops, job runners. [KT-ERR-3]
23. Don't log and rethrow the same exception. Use parameterized SLF4J messages. Never log secrets or PII. [KT-ERR-4, KT-OBS-1..3]

## Persistence
24. Persistence types never cross the service boundary. JPA entities, if used, are not data classes. [KT-DB-3..4]

## Size and comments
25. Make the smallest change that satisfies the spec. No speculative abstractions, single-implementation interfaces, or wrapper types added for flexibility.
26. No comments that restate code, narrate steps, or mark sections. No commented-out code. No `TODO` without a ticket. Comments explain why. [KT-DOC-1..4]
27. KDoc only for public APIs whose contract isn't obvious from names and types; no `@param`/`@return` boilerplate. [KT-DOC-3]

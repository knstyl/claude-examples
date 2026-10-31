# Kotlin Backend Engineering Standards

**Applies to:** server-side Kotlin services built on Ktor (Jetty engine) with Guice for dependency injection.
**Baseline:** Kotlin 2.4.x · Ktor 3.6.x (`ktor-server-jetty-jakarta`) · Guice 7.x (`jakarta.inject`) · kotlinx.coroutines · kotlinx.serialization · JDK 21+.
**Last reviewed:** 2026-10-30.

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are used as in RFC 2119.
Rule IDs (e.g. `KT-NULL-1`) are stable so specs, reviews, and lint suppressions can reference them.
Where a rule conflicts with an established convention in an existing codebase, the codebase convention wins and the deviation is recorded in that repo's AGENTS.md.

---

## 0. Non-negotiables

These are the rules that are never traded off for speed. Each links to its section.

1. **No `!!` in production code.** Model absence in the type system. → `KT-NULL-1`
2. **`val` and read-only types by default.** `var`, `MutableList`, etc. only where mutation is required and kept private. → `KT-IMM-1..3`
3. **Constructor injection only** (`class X @Inject constructor(private val …)`). No field injection, no `injector.getInstance` outside the composition root. → `KT-DI-1..3`
4. **Guice modules are fast, side-effect free, and unconditional.** No I/O, no `if (env == …)` in `configure()`. → `KT-DI-4..5`
5. **One `Injector`, created once, in `Stage.PRODUCTION`.** → `KT-DI-3`
6. **No Guice method interception on `suspend` functions.** → `KT-DI-9`
7. **Never block a Ktor call coroutine.** Blocking I/O runs on an injected I/O dispatcher. → `KT-CO-4`, `KT-KTR-3`
8. **Structured concurrency only.** No `GlobalScope`, no `runBlocking` in request paths, no fire-and-forget launches without an owning scope. → `KT-CO-1..2`
9. **Never swallow `CancellationException`.** No bare `catch (e: Exception)` or `runCatching` around suspend calls. → `KT-CO-3`
10. **Every remote call has a timeout; `HttpClient` instances are shared and closed on shutdown.** → `KT-CO-5`, `KT-KTR-8`
11. **Expected business outcomes are sealed types; HTTP mapping happens in `StatusPages`/routes, never in domain code.** → `KT-ERR-1..2`, `KT-ERR-7`
12. **Exhaustive `when` over sealed types and enums without an `else` branch.** → `KT-TYP-4`
13. **Boundary DTOs (`@Serializable`) are separate from domain models and entities.** → `KT-API-1`
14. **Official Kotlin style, enforced by ktlint + detekt in CI; the build fails on violations.** → `KT-BLD-6`
15. **No comments that restate code.** Comments explain *why*; KDoc only where the public contract isn't obvious. → `KT-DOC-1..3`
16. **Tests are deterministic:** `testApplication` for HTTP, `runTest` with injected test dispatchers, MockK for Kotlin types, no real sleeps. → `KT-TST-1..4`

---

## 1. Toolchain and build

| ID | Rule |
|---|---|
| KT-BLD-1 | MUST use a supported Kotlin release line (2.4.x as of this review). Ktor, Kotlin, coroutines, and serialization versions MUST come from one version catalog; MUST NOT pin individual Kotlin/Ktor artifacts to divergent versions. |
| KT-BLD-2 | MUST use the Gradle Kotlin DSL (`build.gradle.kts`) and a `libs.versions.toml` catalog for new modules. |
| KT-BLD-3 | MUST enable `-Xjsr305=strict` (Java libraries with JSR-305 nullability) and `-Xannotation-default-target=param-property`. CI MUST treat compiler warnings as errors. |
| KT-BLD-4 | MUST apply the `kotlin("plugin.serialization")` plugin. Guice-intercepted classes need the `allOpen` plugin (see `KT-DI-8`). |
| KT-BLD-5 | The Jetty engine MUST be `ktor-server-jetty-jakarta`. Use `EngineMain` with `application.conf`/`application.yaml` so deployment settings change without recompiling. |
| KT-BLD-6 | MUST run ktlint (official Kotlin style) and detekt in CI with failing thresholds. Baselines are allowed only for legacy code and MUST NOT grow. |
| KT-BLD-7 | MUST NOT add a dependency when the stdlib, kotlinx libraries, a Ktor plugin, or an existing dependency covers the need. New dependencies require a stated reason in the PR. |
| KT-BLD-8 | Library modules (shared clients, SDKs) MUST enable explicit API mode. Application modules SHOULD NOT. |

```kotlin
plugins {
    kotlin("jvm") version "2.4.20"
    kotlin("plugin.serialization") version "2.4.20"
    kotlin("plugin.allopen") version "2.4.20" // only if Guice AOP is used
    id("io.ktor.plugin") version "3.6.1"
}

application {
    mainClass = "io.ktor.server.jetty.jakarta.EngineMain"
}

kotlin {
    jvmToolchain(25) // match the deployed runtime
    compilerOptions {
        freeCompilerArgs.addAll("-Xjsr305=strict", "-Xannotation-default-target=param-property")
        allWarningsAsErrors = true
    }
}

dependencies {
    implementation("io.ktor:ktor-server-core")
    implementation("io.ktor:ktor-server-jetty-jakarta")
    implementation("io.ktor:ktor-server-content-negotiation")
    implementation("io.ktor:ktor-serialization-kotlinx-json")
    implementation("io.ktor:ktor-server-status-pages")
    implementation("io.ktor:ktor-server-call-id")
    implementation("io.ktor:ktor-server-call-logging")
    implementation("com.google.inject:guice:7.0.0")
    testImplementation("io.ktor:ktor-server-test-host")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test")
    testImplementation("io.mockk:mockk")
}
```

---

## 2. Formatting and source layout

| ID | Rule |
|---|---|
| KT-FMT-1 | MUST follow the official Kotlin coding conventions: 4-space indent, no tabs, Java-style braces, no horizontal alignment. |
| KT-FMT-2 | SHOULD use trailing commas at declaration sites (parameters, enum entries, multi-line `when` entries). |
| KT-FMT-3 | Directory structure MUST follow the package structure with the common root package omitted. Packages are organized by feature (`customer/`, `offers/`), not by layer (`controllers/`, `services/`). |
| KT-FMT-4 | A file containing one class MUST be named after it. Multi-declaration files MUST be named for what they contain (`OfferRoutes.kt`), never `Utils.kt`, `Helpers.kt`, `Extensions.kt`. |
| KT-FMT-5 | Related declarations MAY share a file; files SHOULD stay under a few hundred lines. |
| KT-FMT-6 | Class order: properties and `init` blocks → secondary constructors → methods → companion object. Group methods by logic, not alphabetically or by visibility. Overloads stay adjacent. |
| KT-FMT-7 | MUST omit redundant constructs: `: Unit`, semicolons, `public` (outside explicit API mode), braces in simple string templates (`"$name"`), explicit types that the compiler infers for private/local declarations. |
| KT-FMT-8 | Modifier order MUST follow the official order. Annotations precede modifiers. |

---

## 3. Naming

| ID | Rule |
|---|---|
| KT-NAM-1 | Packages: lowercase, no underscores. Classes/objects: UpperCamelCase. Functions, properties, locals: lowerCamelCase. |
| KT-NAM-2 | `const val` and top-level/object `val`s holding deeply immutable data use SCREAMING_SNAKE_CASE. Top-level/object `val`s holding mutable state or behavior use camelCase. |
| KT-NAM-3 | Classes are nouns; functions are verbs. Names MUST signal mutation vs copy (`sort` mutates, `sorted` returns a copy). |
| KT-NAM-4 | MUST NOT use meaningless suffixes: `Manager`, `Helper`, `Util`, `Wrapper`, `Data`, `Info`. |
| KT-NAM-5 | Acronyms: two letters stay uppercase (`IOStream`); longer ones capitalize only the first letter (`HttpClient`, `JsonCodec`). |
| KT-NAM-6 | Backing properties use a leading underscore only for the private half of a public/private pair (`_events` / `events`). |
| KT-NAM-7 | Guice modules are named for their feature (`OffersModule`), routes for their resource (`OfferRoutes`), binding annotations for their meaning (`@OffersHttpClient`, not `@Named("client2")`). |
| KT-NAM-8 | Test functions MAY use backtick sentences (`` `returns cached value when fresh`() ``). Production code MUST NOT. |

---

## 4. Null safety

| ID | Rule |
|---|---|
| KT-NULL-1 | MUST NOT use `!!` in production code. Use `?:` with `return`/`throw`, `requireNotNull`, `checkNotNull`, smart casts, or redesign the type. Tests MAY use `!!`. |
| KT-NULL-2 | Public functions and properties whose value comes from a Java call (platform type) MUST declare an explicit Kotlin type. |
| KT-NULL-3 | MUST NOT return `Optional<T>` from Kotlin APIs; return `T?`. |
| KT-NULL-4 | Nullable means "absence is a valid state." A value that is always present after construction MUST be non-null. |
| KT-NULL-5 | `lateinit` is allowed only in tests, never to dodge constructor design. |
| KT-NULL-6 | Nullable `Boolean` in conditions MUST be compared explicitly: `if (flag == true)`. |
| KT-NULL-7 | SHOULD NOT use `?.let { }` where `if (x != null)` reads more plainly, or purely for side effects with a discarded result. |
| KT-NULL-8 | Route parameters and headers MUST be read with explicit null handling (`call.parameters["id"] ?: throw BadRequestException(…)`), never `!!`. |

---

## 5. Types, immutability, modeling

| ID | Rule |
|---|---|
| KT-IMM-1 | Locals and properties MUST be `val` unless reassigned. |
| KT-IMM-2 | Signatures MUST use read-only collection interfaces (`List`, `Set`, `Map`, `Collection`). Create with `listOf`/`setOf`/`mapOf`/`buildList`, not `arrayListOf`/`hashMapOf`, unless mutation is required. |
| KT-IMM-3 | MUST NOT expose mutable state. Keep `MutableX` private and expose the read-only view. Guice singletons in particular MUST be stateless or hold only thread-safe state. |
| KT-TYP-1 | `data class` for values and DTOs only: immutable `val` properties in the primary constructor. Use `copy()` for changes. |
| KT-TYP-2 | Domain identifiers and constrained primitives SHOULD be `@JvmInline value class` with validation in `init`. Verify serialization of value classes with a test. |
| KT-TYP-3 | Closed hierarchies (states, results, events, commands) MUST be `sealed interface`/`sealed class`; singletons in them use `data object`. |
| KT-TYP-4 | `when` over a sealed type or enum MUST be exhaustive without `else`, so adding a case is a compile error. |
| KT-TYP-5 | Prefer a `typealias` for repeated function types or complex generic types; MUST NOT use a typealias where a distinct type is needed (use a value class). |
| KT-TYP-6 | Classes are `final` by default; `open` only with an intended extension point. Prefer composition and interfaces. |

```kotlin
@JvmInline
value class CustomerId(val value: String) {
    init { require(value.isNotBlank()) { "CustomerId must not be blank" } }
}

sealed interface EnrollmentResult {
    data class Enrolled(val id: EnrollmentId) : EnrollmentResult
    data object AlreadyEnrolled : EnrollmentResult
    data class Ineligible(val reason: IneligibilityReason) : EnrollmentResult
}
```

---

## 6. Functions and expressions

| ID | Rule |
|---|---|
| KT-FN-1 | Single-expression functions MUST use expression bodies. |
| KT-FN-2 | Use `if`, `when`, and `try` as expressions (`return when (x) { … }`) rather than returning from each branch. |
| KT-FN-3 | `if` for binary conditions; `when` for three or more branches. |
| KT-FN-4 | Default parameter values instead of overloads. Factory functions with descriptive names (`Point.fromPolar(…)`) instead of multiple constructors. |
| KT-FN-5 | Named arguments MUST be used for `Boolean` parameters and for multiple parameters of the same type, unless meaning is unambiguous. |
| KT-FN-6 | Prefer a read-only property over a zero-arg function when the computation is cheap, doesn't throw, and is stable for unchanged state. |
| KT-FN-7 | Use extension functions for operations that primarily act on a receiver; scope them as narrowly as possible. Place extensions relevant to all clients next to the type; client-specific ones next to the client. |
| KT-FN-8 | `infix` only for symmetric two-operand operations that don't mutate the receiver. |
| KT-FN-9 | Prefer collection operations (`map`, `filter`, `associateBy`, `groupBy`, `partition`, `sumOf`) over manual loops; prefer `for` over `forEach` as a statement. Use `asSequence()` for long chains on large collections. |
| KT-FN-10 | Use `..<` for exclusive ranges, string templates over concatenation, raw strings with `trimIndent()`/`trimMargin()` over `\n`. |
| KT-FN-11 | Lambdas: `it` only in short, non-nested lambdas; name parameters in nested lambdas (routing DSL blocks nest, so name them). Avoid multiple labeled returns; MUST NOT use a labeled return as the last statement. |
| KT-FN-12 | Scope functions per the table below. MUST NOT nest scope functions. MUST NOT use a scope function only to avoid declaring a local `val`. |

| Function | Use for | Returns |
|---|---|---|
| `let` | Transform a nullable result (`x?.let(::toDto)`) | lambda result |
| `apply` | Configure an object you are constructing | receiver |
| `also` | Side effect (logging, metrics) without changing the value | receiver |
| `run` / `with` | Compute from several members of one receiver | lambda result |

---

## 7. Error handling

| ID | Rule |
|---|---|
| KT-ERR-1 | Expected, recoverable business outcomes (not found, ineligible, conflict) MUST be modeled as sealed result types or nullable returns, not thrown. |
| KT-ERR-2 | Exceptions are for programming errors and infrastructure failures. Use `require` (bad argument), `check` (bad state), `error()` (unreachable) for preconditions. |
| KT-ERR-3 | MUST catch specific exception types. Catching `Exception`/`Throwable` is allowed only at process boundaries (`StatusPages`, message-consumer loop, scheduled-job runner), and MUST rethrow `CancellationException`. |
| KT-ERR-4 | MUST NOT log and rethrow the same exception. Either handle it (and log) or propagate it with context (wrap with a cause). |
| KT-ERR-5 | MUST NOT use `runCatching` around suspend calls or as a general catch-all; it captures `CancellationException` and `Error`s. |
| KT-ERR-6 | Kotlin code called from Java that throws checked exceptions MUST declare `@Throws`. |
| KT-ERR-7 | HTTP error rendering MUST be centralized in the `StatusPages` plugin with one consistent error body (RFC 9457 problem+json shape recommended). Domain and service code MUST NOT throw Ktor HTTP exceptions (`BadRequestException`, `NotFoundException`); those belong in routes only. |

```kotlin
fun Application.configureErrors() {
    install(StatusPages) {
        exception<BadRequestException> { call, cause ->
            call.respond(HttpStatusCode.BadRequest, Problem.of(HttpStatusCode.BadRequest, cause.message))
        }
        exception<Throwable> { call, cause ->
            call.application.log.error("Unhandled error on {}", call.request.path(), cause)
            call.respond(HttpStatusCode.InternalServerError, Problem.of(HttpStatusCode.InternalServerError))
        }
    }
}
```

---

## 8. Coroutines and concurrency

Every Ktor route handler is a suspend function running on the engine's coroutine dispatcher. Blocking it starves the server.

| ID | Rule |
|---|---|
| KT-CO-1 | MUST NOT use `GlobalScope`. Background work that outlives a request MUST run in an injected, application-owned `CoroutineScope` with a `SupervisorJob`, cancelled on `ApplicationStopping` (or launched from the `Application` scope itself). |
| KT-CO-2 | MUST NOT use `runBlocking` in production request paths. It is acceptable only in `main`, CLI entry points, and bridging tests. Fan-out MUST use `coroutineScope { async { } }`; partial-failure fan-out MUST use `supervisorScope` with per-child handling. |
| KT-CO-3 | MUST NOT swallow `CancellationException`. Any broad catch around suspend code MUST rethrow it first. |
| KT-CO-4 | Dispatchers MUST be injected (Guice binding with a qualifier), not hardcoded. Blocking calls (JDBC, blocking SDKs, file I/O) MUST be wrapped in `withContext(ioDispatcher)` inside the class that does the blocking, so every suspend function is safe to call from a route handler. |
| KT-CO-5 | Every remote call MUST be bounded by a timeout (Ktor client `HttpTimeout` and/or `withTimeout`). Use `withTimeoutOrNull` only when absence is an acceptable result. |
| KT-CO-6 | Long-running CPU loops MUST cooperate with cancellation (`ensureActive()` / `yield()`). CPU-heavy work SHOULD run on an injected `Default` dispatcher, not the call dispatcher. |
| KT-CO-7 | Service and repository layers expose `suspend fun` for one-shot results and `Flow` for streams. MUST NOT return `Deferred` or `Job` from public APIs. |
| KT-CO-8 | Shared mutable state across coroutines MUST use confinement, immutable snapshots, atomics, or `Mutex`, never `synchronized`/`ReentrantLock` held across suspension. |
| KT-CO-9 | MDC and tracing context MUST be propagated into coroutines (Ktor `CallId` + `CallLogging` `callIdMdc`, and `MDCContext()` from `kotlinx-coroutines-slf4j` when switching dispatchers). MUST NOT read `ThreadLocal`s after a suspension point. |
| KT-CO-10 | Bridge `CompletableFuture`-based Java SDKs with `await()` (`kotlinx.coroutines.future`), never `.get()`/`.join()` on a call coroutine. |

```kotlin
class CustomerContextService @Inject constructor(
    private val profileClient: ProfileClient,
    private val offersClient: OffersClient,
    private val config: OffersConfig,
) {
    // All-or-nothing
    suspend fun assemble(id: CustomerId): CustomerContext = coroutineScope {
        val profile = async { profileClient.fetch(id) }
        val offers = async { offersClient.fetch(id) }
        CustomerContext(profile.await(), offers.await())
    }

    // Best-effort: required parts fail the request, optional parts degrade
    suspend fun assembleBestEffort(id: CustomerId): CustomerContext = supervisorScope {
        val profile = async { profileClient.fetch(id) }
        val offers = async { withTimeoutOrNull(config.timeout) { offersClient.fetch(id) } }
        CustomerContext(
            profile = profile.await(),
            offers = try {
                offers.await()
            } catch (e: CancellationException) {
                throw e
            } catch (e: IOException) {
                log.warn("Offers unavailable for {}", id, e)
                null
            },
        )
    }

    private companion object {
        val log: Logger = LoggerFactory.getLogger(CustomerContextService::class.java)
    }
}

// Blocking dependency made coroutine-safe at its source
class LegacyLedgerClient @Inject constructor(
    private val sdk: LedgerSdk,
    @IoDispatcher private val ioDispatcher: CoroutineDispatcher,
) {
    suspend fun balance(id: AccountId): Money = withContext(ioDispatcher) { sdk.getBalance(id.value) }
}
```

---

## 9. Dependency injection with Guice

| ID | Rule |
|---|---|
| KT-DI-1 | MUST use constructor injection: `class X @Inject constructor(private val dep: Dep)`, with `jakarta.inject.Inject`. MUST NOT use field or method injection in production code. |
| KT-DI-2 | Inject only direct dependencies. MUST NOT inject `Injector` or a `Provider` merely to fetch something you could inject directly. Use `Provider<T>` only for genuine laziness or per-call instances. |
| KT-DI-3 | Exactly one `Injector`, created once at the composition root (`Application.module()`), with `Stage.PRODUCTION` so singleton wiring errors fail at startup. `injector.getInstance` is called only at the root. |
| KT-DI-4 | Modules MUST be fast and side-effect free: no I/O, no network, no threads started in `configure()` or `@Provides` methods. Expensive resources are created lazily by providers and their lifecycle is managed explicitly (`KT-DI-7`). |
| KT-DI-5 | MUST NOT put environment conditionals in modules. Choose which modules to install at the root, or bind values from typed configuration. |
| KT-DI-6 | Prefer `@Provides` methods over the binding DSL for anything non-trivial. MUST NOT call `@Provides` methods or `@Inject` constructors directly in production code. |
| KT-DI-7 | Closeable resources (`HttpClient`, data sources, Kafka clients) MUST be singletons with an explicit shutdown path: register them with a lifecycle object closed on Ktor's `ApplicationStopping` event. |
| KT-DI-8 | Guice AOP (method interceptors) only works on non-final, non-private methods. Classes using it MUST be opened via the `allOpen` plugin keyed on the interceptor annotation; MUST NOT sprinkle `open` by hand. |
| KT-DI-9 | MUST NOT apply Guice method interceptors (`@Transactional` from guice-persist, timing/retry interceptors) to `suspend` functions. The interceptor returns when the function first suspends, not when it completes. Use explicit suspend wrappers instead. |
| KT-DI-10 | Collection injection of non-final types (`Set<Handler>`, `Map<String, Handler>` from Multibinder/MapBinder) MUST be declared with `@JvmSuppressWildcards`, or Guice looks up `Set<? extends Handler>` and fails. |
| KT-DI-11 | Qualifiers MUST be dedicated annotations (`@Qualifier @Retention(RUNTIME) annotation class IoDispatcher`), not `@Named` strings, and MUST NOT be reused for unrelated bindings. |
| KT-DI-12 | MUST NOT inject `null`. Absent optional dependencies use `OptionalBinder` or a no-op implementation. |
| KT-DI-13 | Modules are organized by feature and document the public bindings they provide. Avoid cyclic dependencies; a cycle is a design smell, not something to break with `Provider`. |
| KT-DI-14 | Singletons MUST be stateless or thread-safe (`KT-IMM-3`). |

```kotlin
@Qualifier
@Retention(AnnotationRetention.RUNTIME)
annotation class IoDispatcher

class CoreModule(private val config: AppConfig) : AbstractModule() {
    @Provides @Singleton
    fun appConfig(): AppConfig = config

    @Provides @Singleton @IoDispatcher
    fun ioDispatcher(): CoroutineDispatcher = Dispatchers.IO

    @Provides @Singleton
    fun json(): Json = Json { ignoreUnknownKeys = true; explicitNulls = false }

    @Provides @Singleton
    fun httpClient(json: Json, lifecycle: Lifecycle): HttpClient =
        HttpClient(CIO) {
            install(HttpTimeout) { requestTimeoutMillis = config.http.requestTimeout.inWholeMilliseconds }
            install(ContentNegotiation) { json(json) }
            expectSuccess = true
        }.also(lifecycle::register)
}

class OfferRoutes @Inject constructor(private val service: OfferService) {
    fun Route.register() {
        get("/customers/{id}/offers") {
            val id = call.parameters["id"]?.let(::CustomerId) ?: throw BadRequestException("Missing id")
            call.respond(service.offersFor(id).map { offer -> offer.toResponse() })
        }
    }
}
```

---

## 10. Ktor server

| ID | Rule |
|---|---|
| KT-KTR-1 | The composition root is a single `Application.module()` that loads typed config, creates the injector, installs plugins in a fixed order, registers routes, and subscribes lifecycle handlers. Plugin setup lives in `Application.configureX()` extension functions, one per concern. |
| KT-KTR-2 | Routes MUST be thin: parse/validate input, call one service, map the result to a response. No business logic, persistence, or client calls in route blocks. |
| KT-KTR-3 | Route handlers MUST NOT call blocking APIs directly (`KT-CO-4`). Jetty's thread settings (`callGroupSize`, `idleTimeout`, shutdown grace) are set in config, not tuned in code ad hoc. |
| KT-KTR-4 | Configuration MUST be deserialized into `@Serializable` data classes (`property<T>("section")` / `getAs<T>()`) once at startup and bound in Guice. MUST NOT scatter `environment.config.property(...)` string lookups through the codebase. Secrets come from environment variables (`${?VAR}`), never committed config. |
| KT-KTR-5 | Install `ContentNegotiation` with the single injected `Json` instance, `StatusPages` (`KT-ERR-7`), `CallId`, `CallLogging` (with `callIdMdc`), and metrics/tracing plugins in every service. |
| KT-KTR-6 | Request bodies MUST be validated before reaching services (`RequestValidation` plugin or an explicit `toDomain()` that returns a sealed result). |
| KT-KTR-7 | Resources MUST be released on `ApplicationStopping`/`ApplicationStopped` (subscribe via `monitor.subscribe`). Background jobs MUST stop cooperatively on shutdown. |
| KT-KTR-8 | Ktor `HttpClient` instances MUST be long-lived singletons per downstream (creating one is expensive), configured with timeouts, `expectSuccess`, and content negotiation, and closed on shutdown. MUST NOT create a client per request. |
| KT-KTR-9 | Custom plugins use `createApplicationPlugin`/`createRouteScopedPlugin`, not intercepting pipeline phases directly. |

```kotlin
fun main(args: Array<String>): Unit = io.ktor.server.jetty.jakarta.EngineMain.main(args)

fun Application.module() {
    val config: AppConfig = property("app")
    val injector = Guice.createInjector(Stage.PRODUCTION, CoreModule(config), OffersModule())

    configureSerialization(injector.getInstance(Json::class.java))
    configureErrors()
    configureObservability()

    routing {
        with(injector.getInstance(OfferRoutes::class.java)) { register() }
    }

    monitor.subscribe(ApplicationStopping) { injector.getInstance(Lifecycle::class.java).close() }
}
```

---

## 11. Persistence

| ID | Rule |
|---|---|
| KT-DB-1 | JDBC-based access (plain JDBC, JDBI, jOOQ, Exposed, Hibernate) is blocking and MUST run on the injected I/O dispatcher, or through the library's own suspend transaction API. |
| KT-DB-2 | A transaction MUST NOT span a suspension point that may resume on a different thread unless the library's coroutine-aware transaction API is used (`KT-DI-9` applies to guice-persist `@Transactional`). |
| KT-DB-3 | Persistence types MUST NOT cross the service boundary; map to domain types. |
| KT-DB-4 | If JPA/Hibernate is used: entities MUST be regular (non-`data`) classes with the `kotlin("plugin.jpa")` no-arg plugin and `allOpen` for `@Entity`/`@MappedSuperclass`/`@Embeddable`; `equals`/`hashCode` MUST be identity-based; `toString` MUST NOT touch lazy associations; generated IDs are `Long? = null`, never a `0` sentinel. |
| KT-DB-5 | Connection pools are Guice singletons closed on shutdown (`KT-DI-7`). Pool size MUST be sized against the I/O dispatcher's parallelism, not left at defaults. |

---

## 12. API boundaries and serialization

| ID | Rule |
|---|---|
| KT-API-1 | Request/response DTOs (REST bodies, events) MUST be `@Serializable` types separate from domain models and persistence types, with explicit mapping functions (`fun Offer.toResponse()`). |
| KT-API-2 | Required fields MUST be non-null with no default, so a missing field fails deserialization. Nullable/defaulted fields only for genuinely optional data. |
| KT-API-3 | One `Json` instance, configured once (unknown keys, explicit nulls, default encoding) and injected everywhere: server content negotiation, clients, and Kafka codecs. MUST NOT construct ad-hoc `Json {}` instances. |
| KT-API-4 | MUST NOT leak internal enums or sealed class names into external contracts without an explicit, stable wire value (`@SerialName`). |
| KT-API-5 | Time values use `kotlin.time.Instant`/`java.time.Instant` with a registered serializer, never `Long` epoch in DTOs. Money uses `BigDecimal` with explicit scale or a money type, never `Double`. |

---

## 13. Logging and observability

| ID | Rule |
|---|---|
| KT-OBS-1 | Use SLF4J with parameterized messages (`log.info("Loaded {} offers", n)`); MUST NOT build log strings eagerly at disabled levels. |
| KT-OBS-2 | One logger per class as a `private val` in a private companion object or a private top-level `val`. |
| KT-OBS-3 | MUST NOT log secrets, tokens, or PII. Log identifiers, not payloads. Ktor client logging MUST sanitize `Authorization`. |
| KT-OBS-4 | Every request carries a call ID in MDC (`CallId` + `CallLogging`), propagated to downstream calls as a header. |
| KT-OBS-5 | Downstream calls MUST be observable (Micrometer/OpenTelemetry timers with bounded-cardinality tags). |

---

## 14. Testing

| ID | Rule |
|---|---|
| KT-TST-1 | HTTP behavior is tested with Ktor's `testApplication { }` (no real server or sockets), loading the same module functions as production with test Guice modules swapped in. Downstream HTTP services are simulated with `externalServices { hosts(...) { } }` or a fake client, not live calls. |
| KT-TST-2 | Mock Kotlin types with MockK. Prefer fakes over mocks for owned interfaces. Override bindings with `Modules.override(...)` in tests; MUST NOT add test hooks to production modules. |
| KT-TST-3 | Coroutine code MUST be tested with `runTest` and an injected `StandardTestDispatcher`/`UnconfinedTestDispatcher` sharing the test scheduler. MUST NOT use `Thread.sleep` or real-time `delay`. |
| KT-TST-4 | Every bug fix adds a test that fails without the fix. Every sealed-type branch and every `StatusPages` mapping has a test. |
| KT-TST-5 | An injector smoke test builds the production module graph in `Stage.PRODUCTION` (or `Stage.TOOL` when providers do I/O) so wiring errors fail in CI, not at deploy. |
| KT-TST-6 | Integration tests against real infrastructure use Testcontainers, not in-memory substitutes, where behavior differs. |
| KT-TST-7 | Test names describe behavior (`` `returns 404 when customer is unknown`() ``), one behavior per test. |

```kotlin
class OfferRoutesTest {
    @Test
    fun `returns 400 when id is missing`() = testApplication {
        application { testModule(FakeOffersModule()) }
        assertEquals(HttpStatusCode.BadRequest, client.get("/customers//offers").status)
    }
}
```

---

## 15. Comments and documentation

| ID | Rule |
|---|---|
| KT-DOC-1 | MUST NOT write comments that restate what the code does, narrate steps (`// Step 1: validate input`), or mark sections (`// ===== Helpers =====`). |
| KT-DOC-2 | Comments explain *why*: non-obvious constraints, trade-offs, links to tickets/ADRs, workarounds with the condition for removing them. |
| KT-DOC-3 | KDoc for public APIs whose contract isn't obvious from name and types. Describe parameters inline with `[param]` links; avoid `@param`/`@return` unless the description won't fit the prose. Each Guice module documents the bindings it exposes. |
| KT-DOC-4 | MUST NOT leave commented-out code, or `TODO`s without a ticket reference. |
| KT-DOC-5 | Prefer a well-named private function or value over a comment explaining a block. |

---

## 16. Anti-pattern quick reference

| Don't | Do |
|---|---|
| `x!!.foo()` | `val x = x ?: return` / `requireNotNull(x) { "…" }` |
| `@Inject lateinit var repo: Repo` | `class Svc @Inject constructor(private val repo: Repo)` |
| `injector.getInstance(...)` inside services | inject the dependency |
| `if (env == "prod") bind(...)` in `configure()` | choose modules at the root |
| I/O in a `@Provides` method or module | lazy provider + lifecycle-managed singleton |
| `@Named("ioDispatcher")` | dedicated `@IoDispatcher` qualifier |
| `handlers: Set<Handler>` from Multibinder | `handlers: Set<@JvmSuppressWildcards Handler>` |
| Guice `@Transactional` on a `suspend fun` | explicit suspend transaction wrapper |
| `HttpClient()` per request | one shared client per downstream, closed on shutdown |
| JDBC call directly in a route | repository using `withContext(ioDispatcher)` |
| `environment.config.property("a.b").getString()` scattered | `@Serializable` config class bound once |
| `throw NotFoundException()` in a service | sealed result, mapped in the route or `StatusPages` |
| `GlobalScope.launch { }` | application-owned scope cancelled on shutdown |
| `runCatching { client.call() }` | catch specific exceptions; rethrow `CancellationException` |
| `when (state) { … else -> }` on sealed type | exhaustive branches, no `else` |
| `list.forEach { … }` as a statement | `for (item in list) { … }` |
| `Utils.kt`, `CustomerManager` | descriptive file/type names |
| `// increment counter` | delete the comment |

---

## 17. Definition of done for generated Kotlin code

- Compiles with zero warnings; ktlint and detekt pass without new suppressions.
- No `!!`, `GlobalScope`, `runBlocking` (outside entry points/tests), `Thread.sleep`, blocking calls on call coroutines, or catch-all without `CancellationException` rethrow.
- New bindings are constructor-injected, covered by the injector smoke test, and closeable resources are registered for shutdown.
- New routes have `testApplication` tests covering success and each error mapping; coroutine logic is tested with `runTest`.
- No new dependency without justification; no unused code, imports, or parameters.
- Comments limited to *why*; no narration, no commented-out code.
- Any deviation from these rules is called out explicitly in the PR description with the rule ID.

---

## Sources

- Kotlin coding conventions — https://kotlinlang.org/docs/coding-conventions.html
- Kotlin coroutine exception handling — https://kotlinlang.org/docs/exception-handling.html
- Best practices for coroutines (Android Developers; dispatcher injection, scope, cancellation, and testing guidance applies to any JVM codebase) — https://developer.android.com/kotlin/coroutines/coroutines-best-practices
- Ktor server engines (Jetty Jakarta, EngineMain, engine configuration) — https://ktor.io/docs/server-engines.html
- Ktor configuration files and typed config deserialization — https://ktor.io/docs/server-configuration-file.html
- Ktor application events — https://ktor.io/docs/server-events.html
- Ktor server testing — https://ktor.io/docs/server-testing.html
- Ktor client creation, reuse, and closing — https://ktor.io/docs/client-create-and-configure.html
- Guice best practices — https://github.com/google/guice/wiki/BestPractices
- Guice injector bootstrap and stages — https://github.com/google/guice/wiki/Bootstrap
- JetBrains: How to avoid common pitfalls with JPA and Kotlin — https://blog.jetbrains.com/idea/2026/04/how-to-avoid-common-pitfalls-with-jpa-and-kotlin
- Kotlin 2.4.20 release — https://blog.jetbrains.com/kotlin/2026/09/kotlin-2-4-20-released/
- detekt (2.0 line in alpha as of this review) — https://detekt.dev/changelog-2.0.0/

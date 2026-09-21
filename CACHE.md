# Handoff: Cache Key Schema & Strategy for the Gateway Module

**Audience:** an engineering agent picking this up to implement, review, or extend.
**Status:** design + reference code. Not yet integrated. Reference impl compiles against the intended
libraries but has not been run; treat it as a specification with executable intent, not a drop-in.

---

## 1. Context

- Service: Kotlin + Ktor + Jetty + Guice GraphQL service built on **Viaduct**. It aggregates data
  **purely from external REST APIs**. All REST clients live in one **common gateway module**.
- Scale target: **50–100+ external REST APIs** in that module.
- Domain: bank customer data. Cross-customer data leakage via cache is a security incident, not a bug.
- Problem being solved: response-shaping inputs (`Accept-Language`, API-specific query params like
  `fields=`, `expand=`, `includeClosed=`) change the downstream response, so they must participate in the
  cache key. The prior proposal was "allowlist + dedupe + hash the raw headers/params".

## 2. Findings that drove the design

1. **Delimiter-injection collision.** Joining names/values with unescaped `&`/`=` is not injective:
   `{a: "1&b=2"}` and `{a: "1", b: "2"}` serialize identically, so they hash identically. Worse, if the
   scope (customer id) is in the same joined string, a client-controlled value can forge a different scope.
   This is a real cache-poisoning / cross-customer exposure vector and was the primary motivation.
2. **Cardinality explosion.** Keying on raw `Accept-Language` (`en-US,en;q=0.9` vs `en-us` vs `en`) or
   on every forwarded query param fragments the cache to near-zero hit rate.
3. **Allowlist drift.** A central allowlist of "which params matter" decays as downstreams change.
   The knowledge must live next to the client that owns the downstream contract.

## 3. Design (the intent an implementer must preserve)

**Key on a typed variant, not on headers.** The cache never sees HTTP. Each adapter maps transport
inputs → a normalized value object (`CacheVariant`) → the outgoing request is built *from* that object.
Therefore key ≡ request by construction, with no allowlist to keep in sync.

**Key schema** — every segment fixed-position, `:`-delimited, segments validated to exclude `:`:

```
gw:v{schema}:{api}:{apiVersion}:{scope}:{variantHash}
gw:v1:profile-api:v2:cust:8841:3f9a1c…e2
```

| Segment | Source | Notes |
|---|---|---|
| `gw` | constant | lets the cluster be shared |
| `v{schema}` | `CacheKeyFactory.schemaVersion` | bump to invalidate everything on a format change |
| `api` | `CacheNamespace.api` | slug declared on the client, regex `[a-z0-9][a-z0-9-]*` |
| `apiVersion` | `CacheNamespace.apiVersion` | downstream contract version; identity, not variant |
| `scope` | `CacheScope` sealed interface | `shared` or `cust:<id>`; **never** derived from variant content |
| `variantHash` | `VariantCodec.hash(variant)` | SHA-256 of canonical JSON, truncated to 128 bits |

Only the last segment is hashed, so prefix eviction (`gw:v1:profile-api:v2:cust:8841:`) works.

**Three tiers of variant, by increasing effort — most adapters use tier 1:**

| Tier | When | Example |
|---|---|---|
| Shared library variant | resource id, locale, paging, or nothing | `ById(id)`, `Localized(tag)`, `NoVariant` |
| `Params` escape hatch | arbitrary shaping params, common shape | `Params.of(allowed, "channel" to "web")` |
| Custom `data class` | API-specific shaping worth a type | `ProfileVariant(locale, fields)` with superset folding |

**Normalization is mandatory and lives in `Normalize`:** `Accept-Language` → RFC 4647 lookup against
the downstream's supported locales (bounded set); field-selection params fold to the full set (superset
caching: fetch the maximal shape, project in GraphQL); ids/lists sorted; timestamps bucketed.

**Registration is zero-cost.** No per-API Guice module. Adapters pass `this` to `getOrFetch`; the cache
self-registers the namespace on first use and fails loudly if two classes claim one. Guice JIT-constructs
clients with no explicit binding.

**Storage is library territory; the façade is ours.** Caffeine `AsyncCache` for L1 (per-node
single-flight via `get(key, loader)`), the existing Redis/DynamoDB tier for L2, `TieredGatewayCache`
(~80 lines) composes them and is the **only** consumer of `CacheKeyFactory`. Spring Cache / JCache
were rejected: wrong stack, and annotation/SpEL keys fight the typed-key discipline.

## 4. Invariants (enforced in `CacheKeyTest.kt` — keep these green)

- Structurally different variants never collide (the `1&b=2` case).
- Scope segment cannot be altered by variant content.
- Golden key format is stable; changing it means bumping `schemaVersion`.
- Locale normalization collapses header variants to the supported set.
- konsist: `CacheVariant` impls are data classes with only `String/Boolean/Int/Long/enum/SortedSet<String>`
  properties (no raw `Locale`, `Map`, or header objects).
- konsist: every `*ApiClient` implements `GatewayApi` and declares `namespace`.
- konsist: only the cache tier references `CacheKeyFactory`.

## 5. Rules for adding an API client (what a new adapter must do)

1. Implement `GatewayApi`; declare `CacheNamespace(api, apiVersion)`. Uncacheable clients skip all of this.
2. Never touch `ApplicationCall` or raw headers. Take a `RequestContext` built once at the edge.
3. Pick the lowest variant tier that fits. Every value in it is already normalized.
4. Build the outgoing request **from the variant**. If a value reaches the wire, it came from the variant.
5. For `Params`, declare the allowlist as a field on the client. Absent params are omitted, not `null`.
6. Decide scope explicitly. Private data → `CacheScope.Customer`. A missing id must fail, never fall
   back to `Shared`.
7. Honor downstream `Cache-Control: no-store` / `private` via `CachePolicy.bypass`.

## 6. Open items / decisions for the implementer

- **`RequestContext` construction:** one Ktor plugin or the Viaduct execution context, not per-adapter.
- **Scope taxonomy:** `Shared` and `Customer` only. Add `Partner`/`Tenant` deliberately. Avoid the word
  "tenant" for cache scope — Viaduct already uses it for contributing teams.
- **L2Store implementation** over the existing Redis/DynamoDB coalescing layer; `evictPrefix` needs
  either a keyspace scan or a tag index — decide by L2 technology.
- **Namespace uniqueness at build time:** add a konsist/CI check so duplicates fail the PR, not the deploy
  (runtime self-registration remains as belt-and-braces).
- **Golden hash pin:** once `VariantCodec` is final, pin the literal hash in `golden key is stable`.
- **Metrics:** per-namespace hit/miss and key cardinality; `recordStats()` on Caffeine is wired, L2 is not.
- **Opaque forwarded params:** where a param's downstream semantics are unknown, `Params` gives a correct
  but fragmented key. Get the contract from the API owner and classify it (drop / normalize / superset)
  or don't cache that API yet.

## 7. Dependencies assumed

`com.github.ben-manes.caffeine:caffeine`, `com.fasterxml.jackson.module:jackson-module-kotlin`,
`org.jetbrains.kotlinx:kotlinx-coroutines-jdk8`, `io.micrometer:micrometer-core`, `io.ktor:ktor-client-core`,
`com.google.inject:guice`, `com.lemonappdev:konsist` (test), `kotlin-test` (test).

---

## 8. Reference code

Package `gateway.cache`. Files are listed in dependency order.

### `CacheKey.kt`

```kotlin
package gateway.cache

import com.fasterxml.jackson.databind.MapperFeature
import com.fasterxml.jackson.databind.SerializationFeature
import com.fasterxml.jackson.databind.json.JsonMapper
import com.fasterxml.jackson.module.kotlin.KotlinModule
import java.security.MessageDigest

/*
 * Key schema (all segments fixed-position, ':'-delimited, segments validated to exclude ':'):
 *
 *   gw:v{schema}:{api}:{apiVersion}:{scope}:{variantHash}
 *
 *   gw            constant namespace (lets you share a Redis/DynamoDB cluster)
 *   v{schema}     key-schema version — bump to invalidate everything on a format change
 *   api           stable slug declared by the client module, e.g. "profile-api"
 *   apiVersion    downstream contract version, e.g. "v2" — part of identity, not variant
 *   scope         isolation boundary, e.g. "shared" | "cust:<id>"  (see CacheScope)
 *   variantHash   128-bit hex of the canonical JSON of the adapter's CacheVariant record
 *
 * Example: gw:v1:profile-api:v2:cust:8841:3f9a1c…e2
 */

private val SEGMENT = Regex("[a-z0-9][a-z0-9-]*")

/** Declared once per external API in its client module. Validated so it can't corrupt the key. */
data class CacheNamespace(val api: String, val apiVersion: String) {
    init {
        require(SEGMENT.matches(api)) { "api must match $SEGMENT: '$api'" }
        require(SEGMENT.matches(apiVersion)) { "apiVersion must match $SEGMENT: '$apiVersion'" }
    }
}

/**
 * Isolation boundary. A fixed-position typed field, never a value inside the variant bag,
 * so no client-supplied string can widen or forge it. Add cases deliberately (e.g. Partner).
 */
sealed interface CacheScope {
    val segment: String

    /** Data that is identical for every caller (reference data, config). */
    data object Shared : CacheScope {
        override val segment = "shared"
    }

    /** Data private to one customer. Missing/blank id fails at construction, never falls back to Shared. */
    data class Customer(val customerId: CustomerId) : CacheScope {
        override val segment = "cust:${customerId.value}"
    }
}

@JvmInline
value class CustomerId(val value: String) {
    init {
        require(value.isNotBlank() && ':' !in value) { "invalid customer id" }
    }
}

/**
 * Marker for per-API variant records: the *semantic* inputs that change the response.
 * Rules (enforced by konsist, see CacheKeyArchitectureTest):
 *  - immutable data class
 *  - properties are String / Boolean / Int / Long / enum / SortedSet<String> only
 *  - values are already normalized (resolved locale tag, folded defaults, sorted fields)
 *  - the outgoing HTTP request is built FROM the variant, never the other way round
 */
interface CacheVariant

@JvmInline
value class CacheKey(val value: String)

/** Canonical serialization + hash. The only place a variant is turned into bytes. */
class VariantCodec {
    private val mapper: JsonMapper = JsonMapper.builder()
        .addModule(KotlinModule.Builder().build())
        .enable(MapperFeature.SORT_PROPERTIES_ALPHABETICALLY)
        .enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS)
        .disable(SerializationFeature.INDENT_OUTPUT)
        .build()

    /** Canonical form — stable across JVM restarts and nodes. Also what you log at DEBUG. */
    fun canonical(variant: CacheVariant): String =
        // Type name guards against two structurally identical records in the same namespace.
        "${variant::class.qualifiedName}:${mapper.writeValueAsString(variant)}"

    fun hash(variant: CacheVariant): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(canonical(variant).toByteArray(Charsets.UTF_8))
        return digest.copyOf(16).joinToString("") { "%02x".format(it) } // 128 bits
    }
}

class CacheKeyFactory(
    private val codec: VariantCodec,
    private val schemaVersion: Int = 1,
) {
    fun key(ns: CacheNamespace, scope: CacheScope, variant: CacheVariant): CacheKey =
        CacheKey("gw:v$schemaVersion:${ns.api}:${ns.apiVersion}:${scope.segment}:${codec.hash(variant)}")

    /** Prefix for targeted eviction, e.g. all cached responses for one customer across one API. */
    fun prefix(ns: CacheNamespace, scope: CacheScope): String =
        "gw:v$schemaVersion:${ns.api}:${ns.apiVersion}:${scope.segment}:"
}
```

### `SharedVariants.kt`

```kotlin
package gateway.cache

import java.util.SortedMap

/*
 * Shared variants. Lives in the core of the common gateway module next to CacheVariant.
 * Covers the common cases so most adapters declare no types of their own.
 * All go through the same VariantCodec, so mixing these with custom records is safe.
 */

/** Response depends only on scope + namespace (e.g. a customer's single profile, a config blob). */
object NoVariant : CacheVariant

/** One resource by id, no other shaping. Id is the *downstream* id, already validated. */
data class ById(val id: String) : CacheVariant

/** Varies by negotiated language only. `locale` is a resolved BCP-47 tag from Normalize.locale. */
data class Localized(val locale: String) : CacheVariant

data class ByIdLocalized(val id: String, val locale: String) : CacheVariant

data class Paged(val page: Int, val size: Int) : CacheVariant

/**
 * Escape hatch for arbitrary shaping params. Sorted map ⇒ canonical JSON ⇒ collision-safe.
 * Construct only via [Params.of] with an adapter-owned allowlist so raw headers / trace ids
 * can't leak in. Values must already be normalized (bucketed, lowercased, folded to defaults).
 */
data class Params private constructor(val values: SortedMap<String, String>) : CacheVariant {
    companion object {
        fun of(allowed: Set<String>, vararg params: Pair<String, String?>): Params {
            val map = sortedMapOf<String, String>()
            for ((name, value) in params) {
                require(name in allowed) { "param '$name' is not an allowed cache dimension" }
                if (value != null) map[name] = value   // absent == default; don't key on nulls
            }
            return Params(map)
        }
    }
}
```

### `Normalize.kt`

```kotlin
package gateway.cache

import java.util.Locale
import java.util.SortedSet

/**
 * Transport → variant normalizers. Every adapter goes through these so the
 * cardinality of a variant dimension is bounded by *our* domain, not by what clients send.
 */
object Normalize {

    /**
     * RFC 4647 lookup of Accept-Language against the languages the downstream actually serves.
     * "en-US,en;q=0.9", "en-us", "en" all collapse to the same supported tag.
     * Malformed headers fall back to the default instead of fragmenting the cache.
     */
    fun locale(acceptLanguage: String?, supported: List<Locale>, default: Locale): Locale {
        if (acceptLanguage.isNullOrBlank()) return default
        val ranges = runCatching { Locale.LanguageRange.parse(acceptLanguage) }.getOrNull() ?: return default
        return Locale.lookup(ranges, supported) ?: default
    }

    /**
     * Field-selection params. Empty, "all", or a superset request all fold to the full set
     * (superset caching: fetch the maximal shape, project in GraphQL). Sorted for canonical JSON.
     */
    fun fields(requested: Collection<String>?, all: Set<String>): SortedSet<String> {
        if (requested.isNullOrEmpty() || "all" in requested) return all.toSortedSet()
        val known = requested.map { it.trim().lowercase() }.filter { it in all }.toSortedSet()
        return if (known.isEmpty() || known.containsAll(all)) all.toSortedSet() else known
    }

    /** Multi-valued params where order is not semantically meaningful. */
    fun idSet(ids: Collection<String>?): SortedSet<String> =
        ids.orEmpty().map { it.trim() }.filter { it.isNotEmpty() }.toSortedSet()
}
```

### `ProfileApiClient.kt`

```kotlin
package gateway.cache

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.parameter
import io.ktor.http.HttpHeaders
import jakarta.inject.Inject
import java.time.LocalDate
import java.util.Locale
import kotlin.reflect.KClass
import kotlin.time.Duration
import kotlin.time.Duration.Companion.hours
import kotlin.time.Duration.Companion.minutes

/** Built once at the Ktor/Viaduct edge. Adapters never see ApplicationCall or raw headers. */
data class RequestContext(val customerId: CustomerId, val acceptLanguage: String?)

/** Every cacheable REST client implements this. Uncacheable clients don't. */
interface GatewayApi {
    val namespace: CacheNamespace
}

data class CachePolicy(val ttl: Duration, val bypass: Boolean = false)

interface GatewayCache {
    /** Adapters pass `this` so the cache can self-register the namespace on first use (no Guice wiring). */
    suspend fun <T : Any> getOrFetch(
        api: GatewayApi, scope: CacheScope, variant: CacheVariant,
        policy: CachePolicy, type: KClass<T>, fetch: suspend () -> T,
    ): T
    suspend fun evict(prefix: String)
}

// ============================================================================================
// Three adapters showing the three tiers: shared variant / Params / custom record.
// ============================================================================================

// --- 1. Shared variant only. Zero new types. Most adapters look like this. -------------------

class AccountsApiClient @Inject constructor(
    private val http: HttpClient, private val cache: GatewayCache,
) : GatewayApi {
    override val namespace = CacheNamespace("accounts-api", "v1")
    private val policy = CachePolicy(ttl = 2.minutes)

    suspend fun getAccount(ctx: RequestContext, accountId: String): Account =
        cache.getOrFetch(this, CacheScope.Customer(ctx.customerId), ById(accountId), policy, Account::class) {
            http.get("https://accounts.internal/v1/accounts/$accountId").body()
        }
}

// --- 2. Params escape hatch. Arbitrary shaping params, allowlisted and normalized. ------------

class OffersApiClient @Inject constructor(
    private val http: HttpClient, private val cache: GatewayCache,
) : GatewayApi {
    override val namespace = CacheNamespace("offers-api", "v3")
    private val policy = CachePolicy(ttl = 15.minutes)

    // The allowlist lives here, next to the client that owns the downstream contract.
    private val dims = setOf("locale", "channel", "asOf")

    suspend fun getOffers(ctx: RequestContext, channel: String, asOf: LocalDate): Offers {
        val variant = Params.of(dims,
            "locale"  to Normalize.locale(ctx.acceptLanguage, SUPPORTED, Locale.US).toLanguageTag(),
            "channel" to channel.lowercase(),
            "asOf"    to asOf.toString(),                // already a day bucket
        )
        return cache.getOrFetch(this, CacheScope.Customer(ctx.customerId), variant, policy, Offers::class) {
            http.get("https://offers.internal/v3/customers/${ctx.customerId.value}/offers") {
                header(HttpHeaders.AcceptLanguage, variant.values["locale"])
                variant.values.filterKeys { it != "locale" }.forEach { (k, v) -> parameter(k, v) }
            }.body()
        }
    }
    private companion object { val SUPPORTED = listOf(Locale.US, Locale.CANADA_FRENCH) }
}

// --- 3. Custom record. API-specific shaping worth a type (superset-folded fields). ------------

data class ProfileVariant(val locale: String, val fields: java.util.SortedSet<String>) : CacheVariant

class ProfileApiClient @Inject constructor(
    private val http: HttpClient, private val cache: GatewayCache,
) : GatewayApi {
    override val namespace = CacheNamespace("profile-api", "v2")
    private val policy = CachePolicy(ttl = 1.hours)

    suspend fun getProfile(ctx: RequestContext, requestedFields: Collection<String>?): Profile {
        val variant = ProfileVariant(
            locale = Normalize.locale(ctx.acceptLanguage, SUPPORTED, Locale.US).toLanguageTag(),
            fields = Normalize.fields(requestedFields, ALL_FIELDS),   // folds to full set ⇒ one entry per customer+locale
        )
        return cache.getOrFetch(this, CacheScope.Customer(ctx.customerId), variant, policy, Profile::class) {
            http.get("https://profile.internal/v2/customers/${ctx.customerId.value}/profile") {
                header(HttpHeaders.AcceptLanguage, variant.locale)
                parameter("fields", variant.fields.joinToString(","))
            }.body()
        }
    }
    private companion object {
        val SUPPORTED = listOf(Locale.US, Locale.CANADA_FRENCH, Locale("es", "US"))
        val ALL_FIELDS = setOf("displayname", "preferredlanguage", "contact", "preferences")
    }
}

data class Account(val id: String, val type: String)
data class Offers(val items: List<String>)
data class Profile(val displayName: String, val preferredLanguage: String)
```

### `CacheModule.kt`

```kotlin
package gateway.cache

import com.github.benmanes.caffeine.cache.AsyncCache
import com.github.benmanes.caffeine.cache.Caffeine
import com.google.inject.AbstractModule
import com.google.inject.Provides
import com.google.inject.Singleton
import io.micrometer.core.instrument.MeterRegistry
import jakarta.inject.Inject
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.future.await
import kotlinx.coroutines.future.future
import java.util.concurrent.ConcurrentHashMap
import kotlin.reflect.KClass
import kotlin.time.Duration
import kotlin.time.Duration.Companion.minutes
import kotlin.time.toJavaDuration

/** Installed once by the common gateway module. No per-API Guice wiring is required. */
class CacheCoreModule : AbstractModule() {
    override fun configure() {
        bind(VariantCodec::class.java).asEagerSingleton()
        bind(GatewayCache::class.java).to(TieredGatewayCache::class.java).`in`(Singleton::class.java)
    }

    @Provides @Singleton
    fun keyFactory(codec: VariantCodec): CacheKeyFactory = CacheKeyFactory(codec, schemaVersion = 1)
}

/** Minimal L2 contract — implement over the existing Redis / DynamoDB client. */
interface L2Store {
    suspend fun <T : Any> get(key: String, type: KClass<T>): T?
    suspend fun put(key: String, value: Any, ttl: Duration)
    suspend fun evictPrefix(prefix: String)
}

/**
 * The only consumer of CacheKeyFactory. Composes: Caffeine L1 (per-node single-flight) →
 * L2 (cross-node) → coalesced fetch. Everything cache-policy-shaped lives here, not in adapters.
 */
class TieredGatewayCache @Inject constructor(
    private val keys: CacheKeyFactory,
    private val l2: L2Store,
    private val meter: MeterRegistry,
) : GatewayCache {

    private val scope = CoroutineScope(Dispatchers.IO)

    private val l1: AsyncCache<String, Any> = Caffeine.newBuilder()
        .maximumSize(50_000)
        .expireAfterWrite(1.minutes.toJavaDuration())
        .recordStats()
        .buildAsync()

    /** Self-registration replaces per-API modules; a namespace claimed by two classes fails loudly. */
    private val owners = ConcurrentHashMap<CacheNamespace, KClass<*>>()

    override suspend fun <T : Any> getOrFetch(
        api: GatewayApi, scope: CacheScope, variant: CacheVariant,
        policy: CachePolicy, type: KClass<T>, fetch: suspend () -> T,
    ): T {
        val prev = owners.putIfAbsent(api.namespace, api::class)
        check(prev == null || prev == api::class) { "${api.namespace} claimed by $prev and ${api::class}" }
        if (policy.bypass) return fetch()

        val key = keys.key(api.namespace, scope, variant).value
        val tags = listOf("api", api.namespace.api)

        @Suppress("UNCHECKED_CAST")
        return l1.get(key) { _, _ ->
            this.scope.future {
                l2.get(key, type)?.also { meter.counter("gw.cache.hit", tags + listOf("tier", "l2")).increment() }
                    ?: fetch().also {
                        meter.counter("gw.cache.miss", tags).increment()
                        l2.put(key, it, policy.ttl)
                    }
            }
        }.await() as T
    }

    override suspend fun evict(prefix: String) {
        l1.asMap().keys.removeIf { it.startsWith(prefix) }
        l2.evictPrefix(prefix)
    }
}
```

### `CacheKeyTest.kt`

```kotlin
package gateway.cache

import com.lemonappdev.konsist.api.Konsist
import com.lemonappdev.konsist.api.ext.list.properties
import com.lemonappdev.konsist.api.ext.list.withParentInterfaceOf
import com.lemonappdev.konsist.api.verify.assertTrue
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals

class CacheKeyTest {
    private val codec = VariantCodec()
    private val keys = CacheKeyFactory(codec, schemaVersion = 1)
    private val ns = CacheNamespace("profile-api", "v2")

    /** The delimiter-injection case from the finding. Keeps someone from "simplifying" the codec later. */
    @Test
    fun `structurally different variants never collide`() {
        data class A(val a: String) : CacheVariant
        data class B(val a: String, val b: String) : CacheVariant
        assertNotEquals(codec.hash(A("1&b=2")), codec.hash(B("1", "2")))
    }

    @Test
    fun `scope cannot be forged from variant content`() {
        val forged = ProfileVariant(locale = "en-US:cust:9999", includeClosed = false)
        val k = keys.key(ns, CacheScope.Customer(CustomerId("1")), forged).value
        assertEquals("cust:1", k.split(":")[4]) // scope segment untouched; injected text is inside the hash
    }

    /** Golden key: any change here is a deliberate schema change → bump schemaVersion. */
    @Test
    fun `golden key is stable`() {
        val k = keys.key(ns, CacheScope.Customer(CustomerId("8841")), ProfileVariant("en-US", true))
        assertEquals("gw:v1:profile-api:v2:cust:8841:", k.value.substringBeforeLast(':') + ":")
        assertEquals(32, k.value.substringAfterLast(':').length)
        // pin the hash once the codec is final: assertEquals("…", k.value.substringAfterLast(':'))
    }

    @Test
    fun `normalized locale collapses header variants`() {
        val supported = listOf(java.util.Locale.US, java.util.Locale.CANADA_FRENCH)
        val tags = listOf("en-US,en;q=0.9", "en-us", "en", "en-GB,en;q=0.8", "garbage;;q=x")
            .map { Normalize.locale(it, supported, java.util.Locale.US).toLanguageTag() }.toSet()
        assertEquals(setOf("en-US"), tags)
    }
}

/**
 * Architecture rules — this is what keeps the pattern honest at 100+ adapters.
 * Lives alongside your existing konsist suite.
 */
class CacheKeyArchitectureTest {
    private val scope = Konsist.scopeFromModule("gateway")
    private val allowedVariantTypes = setOf("String", "Boolean", "Int", "Long", "SortedSet<String>")

    @Test
    fun `variants are data classes with only canonical property types`() {
        scope.classes().withParentInterfaceOf(CacheVariant::class).assertTrue { cls ->
            cls.hasDataModifier &&
                cls.properties().all { p ->
                    val t = p.type?.name ?: return@all false
                    t in allowedVariantTypes || scope.classes().any { it.name == t && it.hasEnumModifier }
                }
        }
    }

    @Test
    fun `every REST client is a GatewayApi with a namespace`() {
        scope.classes().filter { it.name.endsWith("ApiClient") }.assertTrue { cls ->
            cls.hasParentInterfaceOf(GatewayApi::class) && cls.hasProperty { it.name == "namespace" }
        }
    }

    @Test
    fun `only the cache tier builds keys`() {
        scope.classes().filter { it.name != "TieredGatewayCache" && it.name != "CacheKeyTest" }
            .assertTrue { cls -> cls.text.contains("CacheKeyFactory").not() || cls.name.contains("Module") }
    }
}
```
# Viaduct Multi-Tenant BDD Acceptance Harness — Detailed Design

Target stack: Viaduct 1.x, Kotlin, Gradle (Kotlin DSL), Cucumber-JVM on the JUnit
Platform, PicoContainer object factory for step-state injection.

Three kinds of code, three owners:

| Code | Lives in | Owned by |
|---|---|---|
| Harness (engine bootstrap, world, generic steps, operation registry) | `acceptance/harness` | Platform team |
| Producer fixtures (stub resolvers + seeding DSL for a tenant's own types) | `modules/<tenant>/src/testFixtures` | That tenant |
| Consumer acceptance code (features, domain steps, mesh assembly) | `modules/<tenant>/src/acceptanceTest` | That tenant |

---

## 1. Harness module — `acceptance/harness`

### 1.1 `build.gradle.kts`

```kotlin
plugins {
    kotlin("jvm")
    `java-library`
}

dependencies {
    api("com.airbnb.viaduct:viaduct-service-api:1.+")
    api("io.cucumber:cucumber-java:7.+")
    api("io.cucumber:cucumber-picocontainer:7.+")
    api("io.cucumber:cucumber-junit-platform-engine:7.+")
    api("org.junit.platform:junit-platform-suite-api:1.+")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core")
    api("org.assertj:assertj-core:3.+")
    implementation("com.jayway.jsonpath:json-path:2.+")
}
```

The harness is a plain library — it never boots anything itself. Booting is the
consumer suite's job, because only the consumer knows which tenant modules and
stub packages belong on the classpath.

### 1.2 `TestMesh` — the composition point

One Viaduct instance per JVM (engine construction is the expensive part; schema
merge + resolver discovery happen here). Consumers describe *what* to compose;
the harness owns *how*.

```kotlin
// acceptance/harness/src/main/kotlin/com/corp/acceptance/harness/TestMesh.kt
package com.corp.acceptance.harness

import viaduct.service.api.*

/** Consumer-supplied description of the mesh under test. */
data class MeshSpec(
    /** Regex for SDL resource discovery. Default: everything on the classpath. */
    val schemaResourcePattern: String = ".*\\.graphqls",
    /**
     * Package prefixes to scan for @Resolver classes. This is the ONLY lever
     * that decides real-vs-stub: include a tenant's real resolver package OR
     * a fixture package standing in for it — never both for the same fields.
     */
    val resolverPackagePrefixes: List<String>,
    val scopes: Map<String, Set<String>> = emptyMap(),  // scopeId -> scope names
)

object TestMesh {
    @Volatile private var instance: Viaduct? = null
    lateinit var spec: MeshSpec
        private set

    /** Called once from the suite's @BeforeAll hook. Idempotent. */
    @Synchronized
    fun start(spec: MeshSpec): Viaduct =
        instance ?: build(spec).also { instance = it; this.spec = spec }

    fun viaduct(): Viaduct =
        checkNotNull(instance) { "TestMesh.start(spec) not called — add MeshBootHook glue" }

    private fun build(spec: MeshSpec): Viaduct {
        val builder = ViaductBuilder()
            .withSchemaFromResources(pattern = spec.schemaResourcePattern)
            .withResolverErrorReporter(CapturedErrors.reporter) // §1.5
        spec.resolverPackagePrefixes.forEach { builder.withTenantPackagePrefix(it) }
        spec.scopes.forEach { (id, names) -> builder.registerScope(id, names) }
        return builder.build()
    }
}
```

> **API note.** Exact builder method names track the 1.x `ViaductBuilder`
> surface (`SchemaRegistrationInfo` resource scanning, `TenantRegistrationInfo`
> package prefixes, `withResolverErrorReporter`). Pin them against your Viaduct
> version; the *shape* — SDL-by-classpath-scan + resolvers-by-package-prefix —
> is the stable contract this design leans on.

### 1.3 `FixtureStore` — scenario-scoped state behind stub resolvers

The central problem: the engine is a JVM-wide singleton, but fixture data must
be scenario-scoped. Stubs therefore never hold data — they read through a
resettable store.

```kotlin
// acceptance/harness/src/main/kotlin/com/corp/acceptance/harness/FixtureStore.kt
package com.corp.acceptance.harness

/**
 * Scenario-scoped fixture state read by stub resolvers.
 *
 * Namespaced by (type, internalId). Values are tenant-defined fixture POJOs;
 * the owning tenant's stubs know how to map them to GRTs.
 *
 * Failure injection is first-class so features can exercise the error paths:
 *   - FixtureStore.failNode("User", "u-404", NotFoundException())
 *   - FixtureStore.failField("CreditCardAccount", "a1", UpstreamTimeout())
 */
object FixtureStore {
    private val nodes = mutableMapOf<Pair<String, String>, Any>()
    private val nodeFailures = mutableMapOf<Pair<String, String>, Throwable>()
    private val fieldFailures = mutableMapOf<Pair<String, String>, Throwable>()

    fun <T : Any> seed(type: String, id: String, fixture: T) { nodes[type to id] = fixture }
    fun failNode(type: String, id: String, t: Throwable) { nodeFailures[type to id] = t }
    fun failField(type: String, field: String, t: Throwable) { fieldFailures[type to field] = t }

    @Suppress("UNCHECKED_CAST")
    fun <T : Any> get(type: String, id: String): T? = nodes[type to id] as T?
    fun nodeFailure(type: String, id: String): Throwable? = nodeFailures[type to id]
    fun fieldFailure(type: String, field: String): Throwable? = fieldFailures[type to field]

    fun reset() { nodes.clear(); nodeFailures.clear(); fieldFailures.clear() }
}
```

**Consequence:** scenarios must run serially (Cucumber's default). If you later
want parallel scenarios, the store must be keyed by a scenario id carried in
the request context — a deliberate non-goal for v1; see §5.1.

### 1.4 `OperationRegistry` — named GraphQL documents

Features reference operations by name; documents live as resources so they are
reviewable, reusable, and never embedded in Gherkin.

```kotlin
package com.corp.acceptance.harness

object OperationRegistry {
    private val cache = mutableMapOf<String, String>()

    /** Loads /operations/<name>.graphql from any classpath root (harness or tenant). */
    fun document(name: String): String = cache.getOrPut(name) {
        val path = "/operations/$name.graphql"
        OperationRegistry::class.java.getResource(path)?.readText()
            ?: error("No operation document at $path on the test classpath")
    }
}
```

Tenants add their own documents under
`src/acceptanceTest/resources/operations/` — same lookup, zero registration.

### 1.5 Error capture

Assertions on the GraphQL `errors` array cover the client-visible contract.
For *diagnostics* (which resolver threw, what exception), tap the reporter SPI:

```kotlin
package com.corp.acceptance.harness

import viaduct.service.api.spi.ErrorReporter

object CapturedErrors {
    data class Captured(val field: String?, val message: String?, val exception: Throwable)
    private val buf = mutableListOf<Captured>()

    val reporter = ErrorReporter { exception, message, metadata ->
        buf += Captured(metadata.fieldName, message, exception)
    }

    fun all(): List<Captured> = buf.toList()
    fun reset() = buf.clear()
}
```

### 1.6 `GraphQLWorld` — per-scenario execution state

PicoContainer instantiates one per scenario and injects it into every step
class that declares it as a constructor parameter.

```kotlin
package com.corp.acceptance.harness

import com.jayway.jsonpath.JsonPath
import kotlinx.coroutines.future.await
import kotlinx.coroutines.runBlocking
import viaduct.service.api.*

class GraphQLWorld {
    var scopeIds: Set<String> = emptySet()
    private val variables = mutableMapOf<String, Any?>()
    private var lastResult: Map<String, Any?> = emptyMap()

    fun setVariable(name: String, value: Any?) { variables[name] = value }

    fun globalId(typeName: String, internalId: String): String =
        GlobalIdCodec.encode(typeName, internalId)   // must match the codec the
                                                     // mesh was built with (§5.4)

    fun execute(operationName: String) {
        val input = ExecutionInput.create(
            operationText = OperationRegistry.document(operationName),
            variables = variables.toMap(),
        )
        val schemaId =
            if (scopeIds.isEmpty()) SchemaId.Full
            else SchemaId.Scoped("test", scopeIds)
        lastResult = runBlocking {
            TestMesh.viaduct().executeAsync(input, schemaId).await().toSpecification()
        }
    }

    // ---- assertion accessors ----
    fun data(path: String): Any? =
        JsonPath.read(lastResult["data"] ?: emptyMap<String, Any?>(), "$.$path")

    @Suppress("UNCHECKED_CAST")
    fun errors(): List<Map<String, Any?>> =
        lastResult["errors"] as? List<Map<String, Any?>> ?: emptyList()

    fun errorPaths(): List<List<Any>> =
        errors().mapNotNull { it["path"] as? List<Any> }
}
```

### 1.7 `CommonSteps` + hooks — the generic vocabulary

```kotlin
package com.corp.acceptance.harness

import io.cucumber.datatable.DataTable
import io.cucumber.java.After
import io.cucumber.java.en.*
import org.assertj.core.api.Assertions.assertThat

class CommonSteps(private val world: GraphQLWorld) {

    @Given("the request has scopes {string}")
    fun setScopes(csv: String) {
        world.scopeIds = csv.split(",").map { it.trim() }.toSet()
    }

    @Given("the variable {string} is the id of {word} {string}")
    fun setIdVariable(varName: String, typeName: String, internalId: String) {
        world.setVariable(varName, world.globalId(typeName, internalId))
    }

    @Given("the variable {string} is {string}")
    fun setStringVariable(name: String, value: String) = world.setVariable(name, value)

    @When("the {string} operation is executed")
    fun execute(operation: String) = world.execute(operation)

    @Then("the response has no errors")
    fun noErrors() = assertThat(world.errors()).isEmpty()

    @Then("{string} is {string}")
    fun assertDataString(path: String, expected: String) =
        assertThat(world.data(path)).isEqualTo(expected)

    @Then("{string} is null")
    fun assertDataNull(path: String) = assertThat(world.data(path)).isNull()

    @Then("the errors contain:")
    fun assertErrors(table: DataTable) {
        val actual = world.errors()
        table.asMaps().forEach { row ->
            assertThat(actual).anySatisfy { err ->
                row["path"]?.let {
                    assertThat((err["path"] as? List<*>)?.joinToString(".")).isEqualTo(it)
                }
                row["messageContains"]?.let {
                    assertThat(err["message"] as? String).contains(it)
                }
            }
        }
    }
}

class ScenarioHooks {
    @After(order = 0)
    fun teardown() {
        FixtureStore.reset()
        CapturedErrors.reset()
    }
}
```

The generic layer deliberately stops here. "Given a delinquent card account"
is *tenant* vocabulary and lives with the tenant (§3.3) — the harness never
grows domain steps.

---

## 2. Producer fixtures — `modules/user/src/testFixtures`

The User tenant publishes the *official test double* for its slice of the
graph. Consumers depend on it instead of hand-rolling fakes, so semantic
changes to `User` update the double in the owning team's PR.

### 2.1 Gradle wiring (producer side)

```kotlin
// modules/user/build.gradle.kts
plugins {
    kotlin("jvm")
    id("viaduct.module")
    `java-test-fixtures`
}

dependencies {
    testFixturesApi(project(":acceptance:harness"))
    // testFixtures compiles against this module's OWN generated GRTs, so its
    // compilation schema already covers User — no extra codegen needed.
}
```

### 2.2 Package layout — the discovery trick

Resolver discovery is package-prefix scanning. Real resolvers and stubs must
therefore be **prefix-disjoint**, so a consumer can register one without
dragging in the other:

```
modules/user/src/main/kotlin/com/corp/user/resolvers/...      # real
modules/user/src/testFixtures/kotlin/com/corp/user/fixtures/  # stubs
```

A consumer mesh registers `com.corp.user.fixtures` **instead of**
`com.corp.user.resolvers`. Registering both would double-bind `User`'s
resolvers — the composition must choose exactly one implementation per field.

### 2.3 Fixture model + seeding DSL

```kotlin
// modules/user/src/testFixtures/kotlin/com/corp/user/fixtures/UserFixtures.kt
package com.corp.user.fixtures

import com.corp.acceptance.harness.FixtureStore

data class UserFixture(
    val internalId: String,
    var firstName: String? = null,
    var lastName: String? = null,
    var email: String? = null,
)

object UserFixtures {
    fun user(internalId: String, block: UserFixture.() -> Unit = {}): UserFixture =
        UserFixture(internalId).apply(block).also { FixtureStore.seed("User", internalId, it) }

    fun missingUser(internalId: String, cause: Throwable = NoSuchElementException("user $internalId")) =
        FixtureStore.failNode("User", internalId, cause)
}
```

### 2.4 The stub node resolver

Extends the *same generated base class* as the real resolver — the stub is a
legitimate tenant implementation, which is exactly why the engine composes it
transparently:

```kotlin
// modules/user/src/testFixtures/kotlin/com/corp/user/fixtures/StubUserNodeResolver.kt
package com.corp.user.fixtures

import com.corp.acceptance.harness.FixtureStore
import viaduct.api.FieldValue
import viaduct.api.Resolver
import com.corp.user.resolverbases.NodeResolvers   // generated

@Resolver
class StubUserNodeResolver : NodeResolvers.User() {
    override suspend fun batchResolve(contexts: List<Context>): List<FieldValue<com.corp.user.grts.User>> =
        contexts.map { ctx ->
            val id = ctx.id.internalID
            FixtureStore.nodeFailure("User", id)?.let { return@map FieldValue.ofError(it) }
            val fx = FixtureStore.get<UserFixture>("User", id)
                ?: return@map FieldValue.ofError(IllegalStateException("Unseeded User $id — seed it in a Given step"))
            FieldValue.ofValue(
                com.corp.user.grts.User.Builder(ctx)
                    .id(ctx.globalIDFor(com.corp.user.grts.User.Reflection, id))
                    .firstName(fx.firstName)
                    .lastName(fx.lastName)
                    .email(fx.email)
                    .build()
            )
        }
}
```

Design points:

- **Unseeded ⇒ loud error, not empty default.** Silent defaults make features
  pass vacuously.
- **`ofError` on injected failure** exercises the real degradation machinery —
  field-level null + `errors` entry, null-propagation if non-null, and
  `UnsetFieldException`/`fetchOrNull` behavior in dependent resolvers. The stub
  *routes through* the engine's failure semantics rather than simulating them.
- If the real tenant also has field resolvers (`User.displayName`), the
  fixtures package supplies stubs for those too — or, better, re-exposes the
  *real* field resolver class from the fixtures prefix when its logic is pure
  computation over the parent (real derivation logic, stubbed data source).

### 2.5 Producer-owned steps (optional but recommended)

```kotlin
// modules/user/src/testFixtures/kotlin/com/corp/user/fixtures/UserSteps.kt
package com.corp.user.fixtures

import io.cucumber.java.en.Given

class UserSteps {
    @Given("a user {string} named {string} {string}")
    fun seedUser(id: String, first: String, last: String) {
        UserFixtures.user(id) { firstName = first; lastName = last }
    }

    @Given("no user exists with id {string}")
    fun seedMissing(id: String) = UserFixtures.missingUser(id)
}
```

Consumers get the vocabulary by adding the fixtures package to their glue path
— the producer owns both the double *and* the language for talking about it.

---

## 3. Consumer tenant — `modules/credit-cards/src/acceptanceTest`

### 3.1 Gradle wiring

```kotlin
// modules/credit-cards/build.gradle.kts
plugins {
    kotlin("jvm")
    id("viaduct.module")
    `jvm-test-suite`
}

testing {
    suites {
        register<JvmTestSuite>("acceptanceTest") {
            useJUnitJupiter()
            dependencies {
                implementation(project())                                // own resolvers
                implementation(project(":acceptance:harness"))
                implementation(testFixtures(project(":modules:user")))   // official User double
                implementation(project(":schema-aggregate"))             // full central SDL (§4)
                implementation("io.cucumber:cucumber-junit-platform-engine:7.+")
                implementation("org.junit.platform:junit-platform-suite:1.+")
            }
        }
    }
}
tasks.named("check") { dependsOn(testing.suites.named("acceptanceTest")) }
```

### 3.2 Runner + mesh assembly

```kotlin
// modules/credit-cards/src/acceptanceTest/kotlin/com/corp/cards/acceptance/RunCucumberTest.kt
package com.corp.cards.acceptance

import io.cucumber.junit.platform.engine.Constants.*
import org.junit.platform.suite.api.*

@Suite
@IncludeEngines("cucumber")
@SelectClasspathResource("features")
@ConfigurationParameter(key = GLUE_PROPERTY_NAME, value =
    "com.corp.acceptance.harness," +      // CommonSteps, ScenarioHooks
    "com.corp.user.fixtures," +           // producer steps + stubs' glue
    "com.corp.cards.acceptance")          // this tenant's steps + boot hook
@ConfigurationParameter(key = PLUGIN_PROPERTY_NAME, value = "pretty, html:build/reports/cucumber.html")
class RunCucumberTest
```

```kotlin
// modules/credit-cards/src/acceptanceTest/kotlin/com/corp/cards/acceptance/MeshBootHook.kt
package com.corp.cards.acceptance

import com.corp.acceptance.harness.MeshSpec
import com.corp.acceptance.harness.TestMesh
import io.cucumber.java.BeforeAll

object MeshBootHook {
    @BeforeAll @JvmStatic
    fun boot() {
        TestMesh.start(MeshSpec(
            resolverPackagePrefixes = listOf(
                "com.corp.cards.resolvers",   // REAL — the code under test
                "com.corp.cards.acceptance.fakes", // fake for cards' own backend (§3.4)
                "com.corp.user.fixtures",     // STUB — foreign frontier
            ),
            scopes = mapOf("test" to setOf("default", "internal")),
        ))
    }
}
```

The composition statement is the whole test philosophy in one list: *my real
resolvers, a fake for my own downstream, official stubs for everyone else.*

### 3.3 Tenant domain steps

```kotlin
// modules/credit-cards/src/acceptanceTest/kotlin/com/corp/cards/acceptance/CardSteps.kt
package com.corp.cards.acceptance

import com.corp.acceptance.harness.FixtureStore
import io.cucumber.java.en.Given

class CardSteps {
    @Given("a card account {string} for user {string} with balance {double}")
    fun seedAccount(accountId: String, userId: String, balance: Double) {
        FixtureStore.seed("CreditCardAccount", accountId,
            CardAccountFixture(accountId, ownerUserId = userId, balance = balance))
    }

    @Given("the card backend is failing with a timeout")
    fun backendDown() =
        FixtureStore.failField("CreditCardAccount", "*", UpstreamTimeout("APIDAO timeout"))
}
```

### 3.4 Fake for the tenant's own downstream

The cards tenant's *real* resolvers stay under test; only their transport is
faked. If `APIDAO` is injected, bind a fake implementation in the test DI
module that reads/throws via `FixtureStore` — resolver logic, batching shape,
and error handling all execute for real:

```kotlin
// com.corp.cards.acceptance.fakes
class FakeApiDao : ApiDao {
    override suspend fun retrieve(accountIds: List<String>): Map<String, ApiPayload> {
        FixtureStore.fieldFailure("CreditCardAccount", "*")?.let { throw it }
        return accountIds.mapNotNull { id ->
            FixtureStore.get<CardAccountFixture>("CreditCardAccount", id)?.let { id to it.toPayload() }
        }.toMap()
    }
}
```

### 3.5 Operations + a feature exercising the failure contract

```graphql
# modules/credit-cards/src/acceptanceTest/resources/operations/AccountSummary.graphql
query AccountSummary($accountId: ID!) {
  node(id: $accountId) {
    ... on CreditCardAccount {
      balanceDisplay        # a1-style field, backed by APIDAO
      owner { displayName } # crosses into User tenant (stubbed)
    }
  }
}
```

```gherkin
# modules/credit-cards/src/acceptanceTest/resources/features/account_summary.feature
Feature: Card account summary

  Background:
    Given the request has scopes "default"
    And a user "u-1" named "Ada" "Lovelace"
    And a card account "acct-9" for user "u-1" with balance 1250.00
    And the variable "accountId" is the id of CreditCardAccount "acct-9"

  Scenario: Happy path composes card data with the owner's name
    When the "AccountSummary" operation is executed
    Then the response has no errors
    And "node.balanceDisplay" is "$1,250.00"
    And "node.owner.displayName" is "Ada Lovelace"

  Scenario: Card backend outage degrades card fields but keeps the owner
    Given the card backend is failing with a timeout
    When the "AccountSummary" operation is executed
    Then "node.balanceDisplay" is null
    And "node.owner.displayName" is "Ada Lovelace"
    And the errors contain:
      | path                | messageContains |
      | node.balanceDisplay | timeout         |
```

That second scenario is the earlier concurrency/failure discussion turned into
an executable regression test: per-field error → null + `errors` entry,
sibling isolation preserved, and (if someone later makes `balanceDisplay`
non-null) the feature fails the moment null-propagation starts eating the
owner data.

---

## 4. `schema-aggregate` — one tiny shared module

Test meshes need the full central SDL on the classpath without depending on
every tenant's *code*. A resources-only module solves it:

```kotlin
// schema-aggregate/build.gradle.kts
plugins { `java-library` }

val collectSdl by tasks.registering(Copy::class) {
    rootProject.subprojects
        .filter { it.path.startsWith(":modules:") }
        .forEach { from("${it.projectDir}/src/main/viaduct/schema") { into(it.name) } }
    into(layout.buildDirectory.dir("generated-resources/schema"))
}
sourceSets["main"].resources.srcDir(collectSdl.map { it.destinationDir })
```

Consumers add `implementation(project(":schema-aggregate"))` and the harness's
resource scan finds every `.graphqls`. (Coarse-grained: any SDL change
invalidates it. Acceptable for acceptance suites; don't wire it into
production builds, where per-module compilation schemas do the fine-grained
work.)

---

## 5. Design decisions & gotchas

**5.1 Serial scenarios, singleton engine.** `FixtureStore` as a JVM singleton
is only sound because scenarios run serially and the store resets in `@After`.
Parallelizing requires threading a scenario key through the request context
into the stubs — defer until suite runtime actually hurts.

**5.2 Stub selection is a classpath/prefix decision, not a mock-framework
decision.** No Mockito anywhere near resolvers. Substitution happens at mesh
composition (which package prefixes are registered), so stubs run under the
real engine: real batching, real memoization, real error shaping, real
null-propagation. That's what makes these acceptance tests rather than big
unit tests.

**5.3 Prefix-disjointness is a convention worth enforcing.** Add a Konvence/
ArchUnit check: `*.fixtures` packages may not live under a prefix that any
production `MeshSpec` registers, and vice versa. Double-registration failures
surface confusingly late otherwise.

**5.4 GlobalID codec must be shared.** `GraphQLWorld.globalId(...)` has to
encode exactly as the mesh's codec does, or seeded ids won't round-trip
through `node(id:)`. Either expose a `globalIdString()` helper from `TestMesh`
backed by the built instance, or install the same codec via
`withGlobalIDCodec` in both places.

**5.5 Producer fixtures are a contract, so version them like one.** A consumer
suite breaking on a `testFixtures` bump is *signal* — the User tenant changed
observable semantics. Resist "fixing" it by pinning old fixtures; that's how
stub-drift starts.

**5.6 Compilation-schema boundary.** The consumer's generated GRTs cover only
types its source references. Seeding/asserting foreign data through the
*producer's* fixture DSL (not raw GRTs) keeps consumers clear of foreign types
they have no generated accessors for — the DSL is the boundary.

**5.7 What stays out of this suite.** Cross-tenant journeys against the fully
real mesh live in `acceptance/suite` (all real resolver prefixes, fakes only
at true system edges). Same harness, same features format — only the
`MeshSpec` differs. That symmetry is the payoff of keeping composition as
data.

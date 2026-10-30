# Handoff: Kotlin cleanup skill and quality gates for the Viaduct service

You are a coding agent working in the Viaduct GraphQL service repository. This file tells you what to evaluate and what to apply. Work in phases. Phase 0 is read-only and ends with a report and a stop. Do not start Phase 1 until the operator approves the report.

This file is a task brief, not repository documentation. Do not copy it, or any prompt text from it, into README files or `docs/`. Prompt logic you create lives only under `.claude/`.

---

## 1. Goal

Make AI-generated Kotlin (mostly from spec-kit) smaller and easier to read without changing behavior, and keep it that way:

1. Put every rule that a tool can check into the compiler, detekt or konsist.
2. Add one Claude Code skill, `kotlin-deslop`, plus a read-only reviewer subagent, for the judgment calls tools can't make.
3. Wire the skill into spec-kit so cleanup runs as part of `/speckit.implement`, not as a separate fight afterward.
4. Adopt one error-handling convention for resolvers and gateway clients.

## 2. Decisions already made (do not reopen)

- Shape: one skill plus lint rules. The skill works on the branch diff only.
- Comments: KDoc on public API only. Inline comments survive only when they explain behavior forced by something the team can't change (Viaduct, Ktor, Guice, an upstream REST API, the JVM).
- Tooling split: detekt owns code smells (local gate, via the existing convention-plugin approach). konsist owns architecture and structure. Sonar stays the CI gate. Do not remove konsist or Sonar.
- Harness: subagents and Gradle tasks are available. Claude Code hooks are not. Do not add `.claude/settings.json` hooks.
- Error handling: the convention in section 6. The operator agrees with it, but you must evaluate it against the code before applying it.

## 3. Context to verify, not assume

The operator described the service this way. Confirm each point in Phase 0 and note any that is wrong.

- Kotlin, Ktor on Jetty, Guice for DI, Viaduct for GraphQL execution.
- Uses scoped serving and subqueries (reentrancy) heavily.
- Data comes only from REST APIs, through a common module that holds all gateway API clients. 15+ today, 50–100+ planned.
- Tenant modules, each with a per-module YAML file for ownership metadata.
- OpenTelemetry tracing and metrics, exported mainly to New Relic.
- detekt is being adopted through a Gradle convention plugin. konsist is already in use. Sonar runs in CI.
- Most feature code was generated with spec-kit, and it is comment-dense and verbose.

## 4. Operating rules for you

- Never change runtime behavior, except where the operator approves an error-handling change in Phase 2. If you find a bug, report it. Fix it only if the fix is one line and covered by a test.
- Never edit generated code: Viaduct GRTs, codegen output, `build/`.
- Never add `@Suppress` to get a gate green without a written reason, and list every suppression in your phase report.
- No new runtime dependencies. New test or build dependencies need operator approval.
- Each phase ends with `./gradlew build` green (compile, tests, detekt, konsist) and the test count not lower than before.
- One commit per logical change. Conventional commit titles. Short bodies that don't restate the title.
- If a recommendation in this file conflicts with what the code shows, the code wins. Report the conflict and propose an adaptation. Don't force the recommendation.
- Stop and ask when: a change would alter client-visible GraphQL errors, a module boundary is unclear, a rule would need more than ~20 suppressions to land, or the detekt or spec-kit version doesn't support something this file assumes.

---

## 5. Phase 0: Evaluate (read-only, then stop)

Do not edit any file in this phase.

### 5.1 Inventory

Find and record:

1. Kotlin, Gradle, Viaduct, detekt, konsist and spec-kit versions. For detekt, note whether it is 1.23.x (`io.gitlab.arturbosch.detekt`) or 2.x (`dev.detekt`). Rule names, rule-set names and the custom-rule API differ between them.
2. Where the detekt convention plugin lives and what config it applies today.
3. Where konsist tests live and what they assert today.
4. The module list. Mark which modules are library-style shared code (gateway clients, connector or `@source`/`@connect` support, shared types, error types) versus tenant modules versus service wiring.
5. Current error handling:
   - Is there a `ResolverErrorBuilder` or `ErrorReporter` registered on the `ViaductBuilder`?
   - How do gateway clients handle HTTP failures? List the catch patterns you find.
   - Count of `runCatching`, `catch (e: Exception)`, `catch (e: Throwable)`, and catches that only log, split by module.
6. Count of comments by kind in main sources: KDoc on public declarations, KDoc on private or internal declarations, line comments, and section-divider comments.
7. Which spec-kit commands and templates are installed, whether `.specify/templates/overrides/` exists, and whether the installed spec-kit supports extensions with an after-implement hook. Check the CLI help and the installed extension files. Don't guess.

### 5.2 Dry-run the gates

Without committing anything, measure what the proposed gates would report:

- Apply the detekt config from section 8.2 in a scratch copy or a temporary local change. Run detekt on main sources and record findings per rule and per module. Revert the change.
- Record how many compiler warnings exist today, because `allWarningsAsErrors` would turn each into an error.

### 5.3 Evaluate each recommendation

For each item in sections 6 through 13, give a verdict: **apply**, **adapt** (say how), or **skip** (say why). Back each verdict with evidence: file paths, counts, or a short code excerpt.

### 5.4 Report and stop

Write the report to `.claude/handoff/phase-0-report.md` (this one file is the only write allowed in Phase 0; it's a working note, not repo docs) and summarize it in chat. Include:

- The inventory.
- Gate dry-run counts per rule and module.
- Verdict table for every recommendation.
- Proposed answers to the open questions in section 14.
- The phase plan you intend to follow, with any reordering.

Then stop and wait for approval.

---

## 6. Error-handling convention

Apply in Phase 2, after approval. The reasoning comes from Viaduct's own design (a resolver that throws is caught by Viaduct and returned as a GraphQL error, and one `ResolverErrorBuilder` can map exception types centrally) and from Kotlin's guidance (don't catch exceptions in general code, handle I/O failures uniformly at one boundary, use null or sealed results for outcomes the caller must handle).

| Situation | Mechanism | Where |
| --- | --- | --- |
| Bug or broken invariant | `require`, `check`, `error()`; let it propagate | Anywhere |
| Upstream call fails (timeout, 5xx, unparseable payload) | Throw a `GatewayException` subtype with the cause attached | Gateway clients only |
| Upstream says not found, and absence is a normal outcome | Return `null` | Gateway client signature |
| Caller branches on several business outcomes | Sealed class result | Domain service |
| Mapping exceptions to client-visible GraphQL errors | One `ResolverErrorBuilder` with a `when` over `GatewayException` | Service wiring |
| Telemetry | One `ErrorReporter` that tags the owning module (use `componentName` and the module ownership YAML) | Service wiring |
| Partial data | Nullable schema field plus a thrown error | Schema and resolver |

Starting hierarchy, adjust to what the code needs:

```kotlin
sealed class GatewayException(
    val upstream: String,
    message: String,
    cause: Throwable? = null,
) : RuntimeException(message, cause) {
    class NotFound(upstream: String, message: String, cause: Throwable? = null) : GatewayException(upstream, message, cause)
    class Unauthorized(upstream: String, message: String, cause: Throwable? = null) : GatewayException(upstream, message, cause)
    class UpstreamUnavailable(upstream: String, message: String, cause: Throwable? = null) : GatewayException(upstream, message, cause)
    class UpstreamContractViolation(upstream: String, message: String, cause: Throwable? = null) : GatewayException(upstream, message, cause)
}
```

Rules:

1. No `try`/`catch` or `runCatching` in resolver code.
2. Gateway clients catch only named exception types from the HTTP client library and wrap them in a `GatewayException` subtype.
3. No catch that only logs. Recover with a value, wrap and rethrow, or don't catch.
4. No `catch (e: Exception)` or `catch (e: Throwable)` outside the error builder and the Ktor top-level handler.
5. Never wrap a suspend call in `runCatching`. It catches `CancellationException` and breaks coroutine cancellation. `catch (e: Exception)` has the same flaw, because `CancellationException` extends `IllegalStateException`. Catch specific types instead.
6. Don't use `kotlin.Result` or Arrow in domain APIs.

Changing how errors reach clients is a behavior change. In Phase 2, first show the operator a before/after table of the GraphQL `errors` entries (message and extensions) for each exception path you touch, and get approval before you commit.

---

## 7. Kotlin slop catalog

The skill and the reviewer use this list. Copy it into `.claude/skills/kotlin-deslop/references/catalog.md` in Phase 4, with one before/after Kotlin example per row taken from this repository.

| # | Pattern | Example | Checked by | Needs judgment |
| --- | --- | --- | --- | --- |
| 1 | Comments that restate code, section dividers, KDoc on private members | `// Fetch the account` above `fetchAccount()` | detekt `CommentOverPrivateFunction`, `CommentOverPrivateProperty`, custom `SectionDividerComment` | Restating KDoc on public API: rewrite it to state the contract |
| 2 | Safe calls and elvis on non-null types, `!!` | `account?.id ?: ""` on a non-null `account` | Compiler warnings as errors; detekt `UnsafeCallOnNullableType` | Types that are nullable but shouldn't be |
| 3 | Catch-all try/catch, `runCatching` around suspend calls, log and swallow | `runCatching { gateway.fetch() }.getOrNull()` | detekt `TooGenericExceptionCaught`, `SwallowedException`, `SuspendFunSwallowedCancellation`; custom `TryCatchInResolver` | Whether a specific catch belongs at this layer |
| 4 | Re-validating inputs that are already typed or validated | `require(id.isNotBlank())` on a non-null schema argument | None | Yes |
| 5 | One-caller wrappers, interfaces with one implementation, Guice bindings with no alternative | `AccountService` plus `AccountServiceImpl` | konsist single-implementation test | Whether the seam is a real test or tenant boundary |
| 6 | Speculative parameters and options nobody varies | `timeout: Duration = 30.seconds` never passed | detekt `UnusedParameter`, `UnusedPrivateMember` | Defaults that never change |
| 7 | Log and rethrow, entry and exit logging | `logger.error("failed", e); throw e` | custom `LogAndRethrow` | Debug logs that should be spans |
| 8 | Compatibility shims kept after an API change | Old and new wrappers for the same call living side by side | detekt `ForbiddenImport` on retired packages | Which shims are still load-bearing |
| 9 | Stringly typed domain values | `accountType: String` compared to `"CREDIT_CARD"` | konsist naming test (warning list first) | Enum vs value class vs sealed type |
| 10 | Mutable state wider than needed | public `MutableList`, `var` in data classes | detekt `VarCouldBeVal`; konsist mutable-collection test | None |
| 11 | Deep nesting and `?.let` chains | three nested `?.let { }` | detekt `NestedBlockDepth`, `ComplexCondition` | Rewriting with early returns |
| 12 | Tests that only verify mocks were called | `verify { gateway.fetch(any()) }` as the only assertion | None | Yes |

---

## 8. Phase 1: Compiler flags and built-in detekt rules

### 8.1 Compiler

- `allWarningsAsErrors = true` for main source sets. If Phase 0 found many existing warnings, propose fixing them first or rolling this out module by module.
- `explicitApi()` (strict) on library-style modules only, as identified in Phase 0. Not on tenant modules unless the operator says so.

### 8.2 detekt config

Add these to the convention plugin's config. Names below are detekt 1.23.x. If the repo is on 2.x, look up the renamed rules and rule sets in the migration guide or the generated default config and use those names.

```yaml
comments:
  CommentOverPrivateFunction:
    active: true
  CommentOverPrivateProperty:
    active: true
  UndocumentedPublicClass:
    active: true      # scope to explicitApi modules via includes or per-module config
  UndocumentedPublicFunction:
    active: true
  UndocumentedPublicProperty:
    active: true

exceptions:
  TooGenericExceptionCaught:
    active: true      # allowlist the ResolverErrorBuilder and the Ktor top-level handler by path
  SwallowedException:
    active: true

coroutines:
  SuspendFunSwallowedCancellation:
    active: true      # needs type resolution: run detektMain, not plain detekt

potential-bugs:
  UnsafeCallOnNullableType:
    active: true

style:
  VarCouldBeVal:
    active: true
  UnusedParameter:
    active: true
  UnusedPrivateMember:
    active: true
  ForbiddenImport:
    active: true
    imports: []       # option name differs in detekt 2.x; list packages here as they are retired

complexity:
  NestedBlockDepth:
    active: true
  ComplexCondition:
    active: true
```

Check the rule-set placement for each rule against the version in use. Some rules moved between rule sets across versions.

### 8.3 Baseline

Generate a detekt baseline for existing violations, so the gate blocks only new code. Commit the baseline separately from the config, so the diff of each is readable.

### 8.4 Done when

`./gradlew build` is green, the baseline is committed, and a scratch branch that adds `runCatching { someSuspendCall() }` fails the build.

---

## 9. Phase 2: Error-handling convention

1. Add the `GatewayException` hierarchy where Phase 0 recommended (the common gateway module or a shared errors module).
2. Add or update the `ResolverErrorBuilder` and `ErrorReporter`, registered on the `ViaductBuilder`.
3. Migrate gateway clients one at a time. Each migration is its own commit.
4. Remove try/catch from resolvers once the clients they call throw typed exceptions.
5. Show the before/after errors table from section 6 and wait for approval before committing anything that changes client-visible errors.

Done when the build is green and no resolver contains `try`, `catch` or `runCatching`.

---

## 10. Phase 3: konsist rules

Add these as tests next to the existing konsist tests. The sketches below show intent. Check method names against the konsist version in use.

```kotlin
@Test
fun `layers depend in one direction`() {
    Konsist.scopeFromProduction().assertArchitecture {
        val resolvers = Layer("Resolvers", "<base>.resolvers..")
        val services = Layer("Services", "<base>.services..")
        val gateways = Layer("Gateways", "<base>.gateway..")
        resolvers.dependsOn(services)
        services.dependsOn(gateways)
        gateways.dependsOnNothing()
    }
}

@Test
fun `interfaces have more than one implementation unless allowlisted`() {
    val scope = Konsist.scopeFromProduction()
    val allow = setOf<String>(/* tenant SPI, test seams */)
    scope.interfaces()
        .filterNot { it.name in allow }
        .assertFalse { iface -> scope.classes().count { cls -> cls.hasParentWithName(iface.name) } == 1 }
}

@Test
fun `no public mutable collection types`() {
    Konsist.scopeFromProduction().properties()
        .filter { it.hasPublicOrDefaultModifier }
        .assertFalse { prop -> prop.type?.name?.startsWith("Mutable") == true }
}

@Test
fun `no try catch in resolvers`() {
    Konsist.scopeFromPackage("<base>.resolvers..").functions()
        .assertFalse { it.text.contains("try {") || it.text.contains("runCatching") }
}
```

Replace `<base>` with the real packages. If the package layout doesn't match three clean layers, propose the layering that does match in your phase report instead of forcing this one.

The naming test for row 9 (`String` properties named `*Type` or `*Status` in domain packages) starts as a report-only list. Promote it to a failing test after the existing cases are fixed.

---

## 11. Phase 4: The skill and the reviewer

Create these files. Keep `SKILL.md` under about 150 lines. References load only when a step needs them.

```
.claude/
  skills/kotlin-deslop/
    SKILL.md
    references/catalog.md      section 7, with before/after examples from this repo
    references/errors.md       section 6
    references/reviewer.md     the reviewer rubric below
    candidates.md              patterns waiting to become rules (starts empty)
  agents/kotlin-slop-reviewer.md
```

### 11.1 `.claude/skills/kotlin-deslop/SKILL.md`

```markdown
---
name: kotlin-deslop
description: Clean AI-generated slop from the Kotlin diff on this branch. Use before committing or opening a PR, at the end of /speckit.implement, or when asked to deslop, tighten or clean up Kotlin changes.
---

# Kotlin deslop

Make the diff smaller and easier to read without changing behavior.

## Scope
Kotlin files changed against the merge base with main, plus the working tree.
Skip generated code (Viaduct GRTs, codegen output) and build/.
If the caller names files or modules, use those instead. Ask before touching anything else.

## Steps
1. Run `./gradlew detektMain` and the konsist tests for the touched modules. Fix findings in scope.
2. Read references/catalog.md. Fix rows 1, 4, 5, 9, 11 and 12 in the diff.
3. Read references/errors.md. Bring error handling in the diff to the convention.
4. Spawn the kotlin-slop-reviewer agent with the scope and your cleanup diff. Do not restate its rubric.
5. Adjudicate each finding. Reject: edits outside scope, deletion of KDoc on public declarations in explicitApi modules, anything that changes behavior, and flags on code a kept comment shows is intentional. Apply the rest.
6. Run `./gradlew build`. It must pass, and the test count must not drop.
7. If you fixed a pattern a detekt or konsist rule could catch, add it to candidates.md with one example.
8. Report: count per catalog row, suppressions added with reasons, constraint comments encoded or left open, candidates added, and a one-line reason for each Kotlin idiom change.

## Comments
- Public API in explicitApi modules: keep KDoc. Rewrite KDoc that restates the signature so it states the contract (units, what null means, which upstream it calls, what it throws).
- Everything else: delete, unless it explains behavior forced by Viaduct, Ktor, Guice, an upstream API or the JVM.
- "Do not remove" or "do not change" comments: propose the cheapest encoding (a type, a require, a test or a konsist rule). Encode it if approved, then delete the comment. Otherwise keep it and list it as open.

## Guardrails
- Behavior stays the same. Report bugs. Fix one only if the fix is one line and covered by a test.
- No new @Suppress without a reason in the report. No new dependencies.
- One commit per catalog row touched.
```

### 11.2 `.claude/agents/kotlin-slop-reviewer.md`

```markdown
---
name: kotlin-slop-reviewer
description: Read-only reviewer for Kotlin cleanup diffs. Spawned by the kotlin-deslop skill. Reviews the given scope against the slop catalog and the error convention.
tools: Read, Grep, Glob
---

You review a Kotlin cleanup diff with fresh eyes. You never edit files.

Read .claude/skills/kotlin-deslop/references/reviewer.md, then review the scope you were given.

For every finding, report:
- file:line
- verdict: MUST FIX, CONSIDER or KEEP
- catalog row number, or "errors" for the error convention
- one sentence of reason, naming code inside the scope

Also report:
- Behavior changes you can see in the cleanup diff.
- Public KDoc that was deleted rather than rewritten.
- Comments that were deleted but carried a real constraint.
- Tests whose only assertion is a mock verification.

Invent nothing. If you are unsure, say CONSIDER and why.
```

### 11.3 `.claude/skills/kotlin-deslop/references/reviewer.md`

Write the rubric from sections 6 and 7. It must cover:

- What counts as a comment worth keeping: behavior forced by something outside the team's control, or a non-obvious contract on public API.
- What a MUST FIX is: a catalog violation with a mechanical fix, a cancellation-unsafe catch, a swallowed exception, or a deleted constraint.
- What a KEEP is: code that looks like slop but is intentional, with the evidence (a test, a comment about an upstream quirk, a tenant SPI).

### 11.4 Done when

Running the skill on one recent spec-kit feature branch produces a green build, a report in the format above, and a diff the operator accepts.

---

## 12. Phase 5: spec-kit integration

Goal: cleanup runs as part of spec-kit, so the skill and spec-kit stop working against each other.

1. **Override the implement command.** If the installed spec-kit supports project-local overrides (`.specify/templates/overrides/`), add an override of the implement command's instructions that:
   - Points the agent at `.claude/skills/kotlin-deslop/references/catalog.md` and `references/errors.md` before writing code.
   - Says: no comments that restate code, KDoc only on public API, no try/catch in resolvers, no runCatching around suspend calls, no new interfaces with a single implementation.
   - Keeps the override short. More prose in context makes generation worse, not better.
2. **Run the skill after implement.** If the installed spec-kit supports extension hooks with an after-implement event, create a small local extension whose hook runs the `kotlin-deslop` skill and then `./gradlew build`. If it doesn't, add a final task to the tasks template instead: "Run kotlin-deslop on this feature's diff; the build must pass."
3. **Constitution.** Add three to five one-line principles that match the catalog (fewer comments, errors at the boundary, no speculative abstractions). Keep it short.
4. Verify hook event names and manifest format against the installed version. They have changed between spec-kit releases.

Done when a fresh `/speckit.implement` run on a small feature ends with the skill's report and a green build, with no manual step.

---

## 13. Phase 6: Custom detekt rules

Write these in a small rule-set module shipped by the convention plugin, with tests using detekt's test harness:

- `LogAndRethrow`: a catch block that logs the caught exception and then rethrows it, or throws a new exception wrapping it.
- `SectionDividerComment`: line comments made mostly of repeated `=`, `-`, `*` or `#`, or comments like `// ===== Helpers =====`.
- `TryCatchInResolver`: any `try` expression or `runCatching` call in files under the resolver packages. Configure the paths through `includes`. If the konsist test from Phase 3 already covers this reliably, skip this rule and say so.

Then promote anything in `candidates.md` that recurred on two or more branches.

detekt 2.x changed the rule API: rules take their description in the constructor, `Issue` and `CodeSmell` are gone, and type-aware rules use the K2 Analysis API. Write against the version the convention plugin pins.

---

## 14. Open questions

Propose an answer for each in the Phase 0 report, with evidence:

1. Which modules count as public API for `explicitApi()` and the KDoc rules?
2. Should tenant modules run the same skill and gates, or a lighter set?
3. Where should the `GatewayException` hierarchy live?
4. Which detekt version does the convention plugin pin, and does that change any rule names here?
5. Does the installed spec-kit support overrides and after-implement hooks?
6. Where do Sonar's rules overlap detekt's, and should Sonar's profile be tuned to avoid duplicate findings?

## 15. References

- pstack (principles, `/no-comments`, playbooks): https://github.com/backnotprop/pstack
- Cursor deslop skill: https://github.com/cursor/plugins/blob/main/cursor-team-kit/skills/deslop/SKILL.md
- Viaduct error handling: https://viaduct.airbnb.tech/docs/service_engineers/observability/error_handling/
- Roman Elizarov, Kotlin and Exceptions: https://elizarov.medium.com/kotlin-and-exceptions-8062f589d07
- detekt coroutines rules: https://detekt.dev/docs/rules/coroutines
- detekt 2.0 migration guide: https://detekt.dev/docs/introduction/migration
- konsist architecture assertions: https://docs.konsist.lemonappdev.com/writing-tests/architecture-assert.md
- spec-kit (extensions, presets, overrides): https://github.com/github/spec-kit

# Handoff: Adopt detekt as the Local Static Analysis & Convention Gate

**Repo context:** Multi-tenant Viaduct GraphQL service, Kotlin, shared monorepo (Gradle). Multiple teams will contribute tenant modules (self-service model). Significant portions of the codebase are AI-generated. CI already runs SonarQube for coverage and static analysis.

**Objective:** Introduce detekt as a fast, local, deterministic quality gate, packaged as a Gradle convention plugin so every module inherits identical configuration. Detekt owns the Kotlin ruleset; Sonar remains the CI reporting and quality-gate surface, consuming detekt's output. Formatting is handled separately and must be auto-fixable.

---

## Guiding principles (do not violate)

1. **One source of truth for Kotlin rules: detekt.** Do not let Sonar's native Kotlin rules and detekt fight. Route detekt reports into Sonar via `sonar.kotlin.detekt.reportPaths`; disable/deprioritize overlapping native Sonar Kotlin rules if they produce duplicate or conflicting findings.
2. **Zero per-module opt-in.** All configuration lives in a convention plugin in `build-logic` (composite build via `includeBuild`). Tenant modules must get detekt automatically by applying the shared convention plugin — never by declaring detekt themselves.
3. **Green from day one.** Generate a baseline per module for all existing violations. The gate fails only on *new* violations. Never block adoption on a retroactive cleanup.
4. **Local gate must stay fast.** Plain `detekt` (no type resolution) runs locally as part of `check`. Type-resolution tasks (`detektMain`, `detektTest`) run in CI only. Verify Gradle build cache and configuration cache compatibility for all detekt tasks.
5. **Formatting is not a failure mode.** Formatting is auto-fixed, not manually corrected. Use Spotless + ktlint with `spotlessApply`. Do **not** enable the `detekt-formatting` ruleset (avoid double-owning formatting). Detekt failures should always be genuine code smells worth a human/agent decision.
6. **CI must also run detekt.** The local gate is bypassable by definition; CI re-runs it so nothing merges without passing.

---

## Implementation tasks (in order)

### 1. Convention plugin

- Create (or extend) `build-logic/` as an included build with a `kotlin-conventions` (or similarly named) convention plugin.
- Apply the detekt Gradle plugin there with:
  - Shared `detekt.yml` at repo root (single config file, referenced by all modules).
  - `buildUponDefaultConfig = true`, `allRules = false`.
  - Per-module baseline path convention: `<module>/detekt-baseline.xml`.
  - Reports: enable XML (for Sonar ingestion) and SARIF (for editor/agent tooling); HTML optional.
- Wire plain `detekt` into the `check` lifecycle task so `./gradlew check` and local builds enforce it.
- Apply the convention plugin to every existing Kotlin module. Confirm no module declares detekt directly.

### 2. Rule configuration (`detekt.yml`)

Start from defaults, then explicitly enable/tune rules that matter for this codebase, especially LLM-generated-code failure modes:

- `TooGenericExceptionCaught`, `TooGenericExceptionThrown`
- `CognitiveComplexMethod` / `CyclomaticComplexMethod`, `LongMethod`, `LongParameterList`, `LargeClass`
- `UnusedPrivateMember`, `UnusedParameter`, `UnusedImports` (if not covered by formatting tooling)
- `ForbiddenMethodCall` / `ForbiddenImport` — seed with an initial banned list (e.g., `!!` via `UnsafeCallOnNullableType`, `println`, `Thread.sleep`, direct `java.util.Date`)
- `ReturnCount`, `NestedBlockDepth`
- Keep thresholds pragmatic: the goal is signal, not noise. If a rule fires pervasively on idiomatic code in this repo, tune or baseline it rather than training contributors to ignore failures.

### 3. Baseline

- Run baseline generation per module (`detektBaseline`) and commit the resulting `detekt-baseline.xml` files.
- Verify a clean `./gradlew check` passes on the current codebase afterward.
- Add a note to the contributing docs: baselines are ratchet-only — entries may be removed as debt is paid down, never added to suppress new findings (new suppressions require `@Suppress` with justification in code review).

### 4. Formatting (separate track)

- Apply Spotless with ktlint in the same convention plugin.
- `spotlessCheck` wired into `check`; document `spotlessApply` as the fix command.
- Ensure `.editorconfig` at repo root is the single formatting config ktlint reads.

### 5. Sonar integration

- In the CI Sonar step, set `sonar.kotlin.detekt.reportPaths` to the detekt XML report paths (aggregate across modules).
- Confirm detekt findings appear in Sonar; then review Sonar's native Kotlin rule activation and disable rules that duplicate detekt findings to avoid double-reporting.
- Sonar quality gate remains the merge gate in CI; detekt is the mechanism feeding it Kotlin findings.

### 6. CI wiring

- CI runs `detekt` (fast, all modules) on every PR.
- CI additionally runs type-resolution tasks (`detektMain`, `detektTest`) — these unlock the higher-value rules and are acceptable to pay for in CI but not locally.
- Fail the build on any non-baselined violation.

### 7. Custom architectural rules (high value — do not skip)

Create a `detekt-rules` module in the monorepo (or in `build-logic`) with custom detekt rules encoding the platform's architectural conventions. Initial rule set:

- **Tenant isolation:** a tenant module must not import from another tenant's package namespace. (Define the tenant package convention first if not already formalized.)
- **Resolver constraints:** resolver classes must not invoke downstream API clients directly — only via the sanctioned service/client abstraction layer.
- **Scope/naming conventions:** enforce naming conventions for `@scope`-related types/annotations per the schema governance decisions.
- **Banned platform APIs:** anything the platform team decides tenants must not touch directly.

Ship these with unit tests (detekt provides a test harness — use `detekt-test`). Register the ruleset in the convention plugin so all modules get it automatically. Where a convention isn't yet firmly decided, implement the rule but leave it inactive in `detekt.yml` with a comment, so activation is a one-line change.

### 8. Contributor experience

- Update the repo's contributing/README docs: what the gate checks, how to run it locally (`./gradlew check`), how to auto-fix formatting (`spotlessApply`), how suppressions work, and the baseline policy.
- Optional but recommended: document IDE integration (detekt IntelliJ plugin pointing at the shared `detekt.yml`) so violations surface at edit time, not build time.

---

## Acceptance criteria

- [ ] `./gradlew check` runs detekt + spotlessCheck on all Kotlin modules and passes on a clean checkout.
- [ ] A deliberately introduced violation (e.g., a `!!` or an over-complex function) fails the local build with a clear message.
- [ ] No module configures detekt directly; all config flows from the convention plugin.
- [ ] Baselines are committed; no pre-existing violation blocks the build.
- [ ] CI runs plain detekt on PRs and type-resolved detekt tasks; failures block merge.
- [ ] Detekt XML reports are ingested by Sonar and findings are visible there; no duplicate findings from Sonar's native Kotlin rules.
- [ ] At least one custom architectural rule (tenant isolation) is implemented, tested, and active.
- [ ] Contributing docs updated.

## Out of scope

- Retroactive cleanup of baselined violations (separate, incremental effort).
- Changing the Sonar quality gate thresholds or coverage requirements.
- Any CI pipeline restructuring beyond adding the detekt steps and report paths.

## Open decisions to surface back to me (don't guess)

- Final banned-API list for `ForbiddenMethodCall`/`ForbiddenImport`.
- The tenant package-naming convention, if it isn't already documented, before activating the tenant-isolation rule.
- Which Sonar native Kotlin rules to disable (propose a list after observing duplicate findings on a real PR).

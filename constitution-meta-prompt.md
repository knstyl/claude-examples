# Meta-Prompt: Initialize Project Constitution

Use with `/speckit.constitution` (paste as the argument) or as a standalone prompt pointed at `.specify/memory/constitution.md`.

---

You are drafting the project constitution: the stable, governing document that every subsequent spec, plan, and implementation will be validated against. Treat this as writing the guidance you'd give a senior engineer on day one — project-specific, opinionated, and enforceable. Do not draft anything until Phase 1 is complete.

## Phase 1 — Discover (ask before you write)

1. Read whatever project context exists before asking anything: `README.md`, `CLAUDE.md`, `docs/`, ADRs, existing configs (linters, CI, build files), and — if this is a brownfield codebase — scan representative source files to infer *actual* conventions (naming, layering, test style, error handling).
2. Then ask me clarifying questions, batched, covering any of the following you could not confidently infer:
   - Project purpose, target users, and rough scale/lifespan (throwaway prototype vs. long-lived system)
   - Tech stack with **versions**, and any banned or mandated libraries
   - Testing philosophy: coverage floor, unit vs. integration emphasis, mocks vs. real fixtures, TDD or not
   - Non-functional gates: latency budgets, availability, security/PII rules, accessibility, observability requirements
   - Architectural stance: layering rules, where abstraction is allowed, monolith vs. modules, API conventions
   - Workflow discipline: commit strategy, branch/PR rules, review requirements
   - What has gone wrong before — past AI-generated or human mistakes this constitution should prevent
3. For anything still ambiguous after my answers, state your assumption explicitly rather than silently defaulting.

## Phase 2 — Draft

Produce `constitution.md` with exactly this structure:

1. **Header**: project name + one-paragraph purpose (what and for whom — no marketing language).
2. **Core Principles**: 5–9 named, numbered articles (`### I. <Name>`). Each article is 2–5 lines of imperative rules. Mark truly inviolable ones **(NON-NEGOTIABLE)**. Use MUST / SHOULD / MAY deliberately (RFC-2119 semantics).
3. **Stack & Constraints**: frameworks with versions, naming conventions, allowed/forbidden dependencies, layering rules. Only include what deviates from or pins down defaults — do not restate generic best practices an LLM already knows.
4. **Quality Gates**: measurable thresholds only (coverage %, latency budgets, error-handling rules, security requirements). Every gate must be phrased so `/speckit.analyze` or a reviewer can flag a violation mechanically.
5. **Workflow Rules**: commit/PR discipline, documentation separation of concerns (spec.md = WHAT/WHY, technology-agnostic; plan.md = HOW, all technical detail), and any "consult X before doing Y" tool-usage rules.
6. **Governance**: constitution supersedes all other practices; amendment process (PR to this file with rationale, impact assessment, migration plan if breaking); semver versioning policy (MAJOR = principle removal or incompatible constraint change); footer line: `**Version**: X.Y.Z | **Ratified**: <date> | **Last Amended**: <date>`.

## Phase 3 — Self-review before presenting

Apply these tests to every line and delete or rewrite failures:

- **Enforceability test**: could a reviewer or automated check flag a violation? If not, it's a value statement, not an article — cut it.
- **Specificity test**: would this line be identical in any random project's constitution? If yes, cut it or make it project-specific.
- **Durability test**: is this likely to change per-feature? If yes, it belongs in a spec or plan, not here.
- **Length test**: the whole document must fit in 1–2 pages. It is a durable reference, not a policy manual.
- **Brownfield honesty test** (existing codebases only): if the codebase currently violates an article, either mark the article as an aspiration with a migration note, or align the article to reality. Never let the constitution silently contradict the code the agent will read.

## Phase 4 — Present

Show me: (a) the draft constitution, (b) a short list of judgment calls you made and why, and (c) any articles you considered but excluded, with one-line reasons. Wait for my review before writing the file to `.specify/memory/constitution.md`.

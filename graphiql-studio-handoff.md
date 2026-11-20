# Handoff: GraphiQL Studio for the Viaduct service

**Audience:** a Claude Code agent with full access to the Viaduct monorepo and its context.
**Goal:** replace the stock GraphiQL page served by the Viaduct service with "Studio": a restyled, Viaduct-aware IDE focused on tenant self-service.
**Status:** design approved in direction; nothing built yet. The mockup data is illustrative, not real schema.

## Attachments

| File | What it is |
|---|---|
| `studio-json.png` | Main state: default scope, JSON response view |
| `studio-resolvers.png` | Resolvers tab: resolver timeline and diagnostics |
| `studio-internal-scope.png` | Same screen with the `internal` scope selected |
| `studio-reference.html` | Static HTML of the mockup. Open it in a browser and inspect exact spacing and colors. It is a visual reference, **not** code to ship. |

The mockup shows a made-up banking schema: `Customer`, `Account`, `CreditCardAccount`, `eligibility`. It also shows made-up modules (`profile`, `accounts`, `eligibility`), a made-up build hash and made-up timings. Swap in the real schema, modules and metadata from the repo.

## Ground rules

1. **Verify every Viaduct assumption in this doc against the codebase before building on it.** Flagged items are marked **[verify]**. Where the code disagrees with this doc, the code wins. Note the deviation in your PR.
2. GraphiQL is served **by the service itself** (same origin). No endpoint URL entry, no CORS work, no "connect to server" UI.
3. Everything Viaduct-specific in the UI must degrade gracefully. If the metadata or tracing it needs is missing (e.g. in prod), hide that feature. Never break the page.
4. Diagnostics such as the resolver timeline and internal-scope access must be gated to non-prod environments, or to authorized callers, by server config.

## Layout (desktop, 1440×900 reference)

Read left to right:

1. **Header bar** (full width, ~56px)
   - GraphiQL wordmark.
   - **Service pill:** status dot, service name, build hash (short git SHA), Viaduct version, and the count of loaded tenant modules.
   - **Scope switcher:** a segmented control, `default` | `internal`. It lists whatever scopes the server exposes.
   - **⌘K search:** searches types, fields, resolvers and modules.
   - Environment label (e.g. Staging), share-link button, and the primary **Run** button (⌘↵).
2. **Activity rail** (56px): Schema, Modules, History, Saved queries, Settings (pinned to the bottom).
3. **Schema sidebar** (270–310px)
   - Filter input and a legend for the resolver badges.
   - Tree of root types and fields. Each field has:
     - a checkbox that adds or removes it from the query;
     - its type, in muted text;
     - a **resolver-kind badge**: `N` node, `F` field, `B` batch;
     - a **tenant-module chip**.
   - Fields outside the current scope stay in the tree, locked and struck through with "internal only". They don't disappear, so people can see what their client isn't getting.
   - A docs card pinned to the bottom for the selected field shows: description, module and owning team, resolver class (and whether it batches), scopes, and a link to the field's `.graphqls` source.
4. **Editor column** (flexible)
   - Query tabs, each marked Q or M, with an unsaved-changes dot.
   - Operation breadcrumb and a "touches N modules" pill.
   - Prettify and Copy as cURL buttons.
   - A "Run in {scope} scope" link above the operation.
   - Monospace editor with line numbers.
   - A bottom drawer with two tabs:
     - **Variables:** JSON editor, a signature-match check, and a **Global ID helper** that encodes `Type` + internal ID into an ID and decodes any ID you paste.
     - **Headers:** key/value list. It notes that same-origin session cookies are sent automatically.
5. **Response column** (~420px)
   - Segmented control: **JSON | Table | Resolvers**.
   - Status, latency and payload-size chips.
   - **JSON:** foldable, with long lists collapsed to an "N more" chip and Global IDs shown decoded inline (`Customer:8f2k1`). The footer notice depends on scope:
     - default: "N fields on X are only visible in internal", with a Switch scope link;
     - internal: a reminder that clients served the default schema won't see those fields.
   - **Table:** any list in the response pivots into a table, labelled by `__typename` for unions and interfaces.
   - **Resolvers:** one timeline row per resolver invocation, showing kind badge, coordinate, module, upstream call and duration. Repeated per-parent calls are grouped with an `×N` badge. Two diagnostics cards:
     - **Possible N+1:** a field resolver invoked once per parent, with a suggestion to use `@resolver(isBatching: true)` and the owning module and team.
     - **Re-entrant dependency:** a resolver that starts late because its object value fragment needs another field resolved first.
6. **Status bar:** validity in the current scope, cursor position, which build the schema came from, auto-save state, and a `?` shortcuts hint.

At narrow widths, the panels wrap and stack. They are never clipped.

## Visual tokens

Dark theme only for v1. Use CSS custom properties so a light theme can be added later.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0E1014` | app background, response pane |
| `--surface` | `#111318` | sidebar, editor |
| `--raised` | `#15181E` | inputs, pills, cards |
| `--hover` / `--selected` | `#1C2028` / `#1A1F2A` | row hover, selected row |
| `--border` | `#22262F` (dividers), `#242832` (controls) | |
| `--text` | `#E6E8EC` | primary |
| `--text-2` | `#B9BEC8` | secondary |
| `--muted` | `#9AA1AD` | labels (passes 4.5:1 on all surfaces) |
| `--faint` | `#4A5060` | line numbers, decoration only |
| `--accent` | `#7C9CFF` (text on it `#0B0D12`) | Run button, checkboxes |
| `--accent-text` | `#9DB4FF` | links, focus |
| status | ok `#4ADE80`, warn `#F5B97A`, danger `#FF9DB5` | |

**Resolver badges** are outlined, 10px mono:

| Badge | Text | Border |
|---|---|---|
| N | `#7FD1C7` | `#285B54` |
| F | `#9DB4FF` | `#34437A` |
| B | `#F5B97A` | `#6A4A2A` |

**Syntax colors:**

| Token | Color |
|---|---|
| keyword | `#C3A6FF` |
| operation name | `#7FD1C7` |
| variable | `#FF9DB5` |
| type | `#7FB8FF` |
| argument | `#F5B97A` |
| punctuation | `#7A8291` |
| JSON key | `#9CC8FF` |
| JSON string | `#A8E6A1` |
| JSON number | `#F5B97A` |

**Type, shape and spacing:**
- **Fonts:** Inter for UI (13px base); JetBrains Mono for code (13px / 22px line height) and identifiers. Self-host both. Don't load them from Google Fonts at runtime.
- **Radii:** controls 10px, cards 10–12px, chips 4–6px.
- **Spacing:** multiples of 4px.

**Accessibility:**
- Real `<button>` and `<input>` elements, and `aria-label` on icon-only buttons.
- Tabs and segmented controls use `role="tablist"` / `role="tab"`; the scope switcher uses `role="radiogroup"`.
- Visible focus rings.
- Every control works from the keyboard.

## What each Viaduct feature needs from the server

This is the real engineering work. Standard introspection does **not** return applied directives (`@scope`, `@resolver`) or which module owns a field. So most of the Viaduct-aware UI needs a small metadata endpoint served next to GraphiQL.

| UI feature | Data needed | Likely source | Notes |
|---|---|---|---|
| Service pill | service name, build SHA, Viaduct version, module count | build info and app config | Simple JSON endpoint. **[verify]** what build metadata already exists. |
| Scope switcher | list of available scopes; how a request picks one | Viaduct scoped-serving config | **[verify]** how the service picks a scope per request (header, path, auth claim?). The switcher must set exactly that. If scope is fixed by auth, show it read-only. |
| Out-of-scope fields, "internal only" | per-field and per-type `@scope(to: [...])` | full schema plus applied directives | Return the full SDL with directives, or a precomputed `coordinate → scopes` map. Only expose the full graph to authorized callers. |
| Resolver badges and docs card | per coordinate: resolver kind (node/field), `isBatching`, resolver class, owning module | `@resolver` directives and module registration | **[verify]** where module ownership lives. It may be the per-module ownership YAML from the OpenTelemetry attribution work; reuse it rather than inventing a new source. |
| Owning team | module → team | same per-module YAML | |
| `.graphqls` source link | module → repo path, file per type | build-time index | Optional; link to the repo browser. |
| Global ID helper | encode/decode rules | Viaduct's GlobalID codec | **[verify]** the exact format. The mockup assumes base64 of `Type:internalId`. Don't reimplement it in JS if the format may change: call a tiny server endpoint, or mirror the codec exactly with tests. |
| Resolver timeline | per invocation: coordinate, kind, module, start offset, duration, batch size, upstream HTTP call (method plus templated path) | engine instrumentation or the OpenTelemetry spans already being added | Return it in `extensions.viaductTrace` (name is up to you) **only** when the request asks for it (e.g. a header GraphiQL sends) **and** the environment allows it. Never include upstream payloads. |
| N+1 diagnostic | per-coordinate invocation count within one request where `isBatching` is false | computed from the trace | Client-side heuristic: same field-resolver coordinate invoked more than 1× with distinct parents, and not batching. |
| Re-entrant dependency diagnostic | which resolver waited on which required selection | trace with a parent / "awaited" link | **[verify]** whether the engine exposes this. Drop the card if not. |

Keep metadata endpoints read-only, same-origin, and behind the same auth as `/graphql`. Gate the full-graph and trace data by environment.

## Suggested implementation approach

These are recommendations. Adjust to what the repo already does.

- **Build on GraphiQL's own React packages** (`@graphiql/react` with its plugin API) for editing, validation, execution, history and autocomplete. Write the Studio shell (header, rail, sidebar, response views) as your own components and plugins on top.
  - Don't fork GraphiQL or rebuild the editor and language services.
  - **[verify]** which GraphiQL major version fits the current frontend toolchain, if there is one.
- Ship it as a static bundle the Ktor/Jetty service serves at the existing GraphiQL route, with all assets self-hosted.
- Theme through CSS custom properties that override GraphiQL's variables, so the stock components and Studio's look the same.
- Keep all Viaduct-specific behavior in one client module that reads the metadata endpoint. Every feature checks that its data exists before rendering.

## Suggested phases

1. **Shell and theme.** Restyled layout, service pill, tabs, variables/headers drawer, JSON and Table views. No Viaduct metadata needed.
2. **Schema metadata.** Metadata endpoint; module chips, resolver badges, docs card; out-of-scope fields locked in the tree.
3. **Scope switching.** Wire the switcher to the real scope-selection mechanism; validate against the scoped schema; scope-aware notices.
4. **Global ID helper.** Encode/decode in variables; inline decode in the JSON view.
5. **Resolver timeline.** Trace extension (gated), timeline view, N+1 and re-entrancy diagnostics.

Each phase should merge and ship on its own.

## Acceptance criteria

- With the metadata and trace endpoints disabled, the page still works as a fully functional, restyled GraphiQL.
- The query is validated against the selected scope's schema. A field outside that scope gets an editor error and is locked in the tree.
- Switching scope changes what is actually executed, not just what is displayed. You can show this with a field that appears or disappears.
- Global IDs round-trip: what the helper encodes, the server accepts; what the server returns, the helper decodes.
- The resolver timeline appears only in allowed environments and for authorized callers. A query with a known non-batching per-parent resolver is flagged.
- Keyboard: ⌘↵ runs, ⌘K opens search, and you can Tab through every control in order.
- Text contrast is at least 4.5:1 for all text below 24px.

## Open questions for Sam

- How is the scope chosen per request today, and should GraphiQL users be able to switch to `internal` at all, or only in non-prod?
- Is the per-module ownership YAML the source of truth for module → team, and is it available at runtime?
- Should the trace extension reuse the OpenTelemetry span data or come from separate engine instrumentation?
- Is there an existing frontend build in the monorepo, or does this introduce the first one?

## Out of scope for v1

Light theme; the Explorer and Focus variants from the design canvas; a Modules browser panel (the rail icon can stay disabled); saved queries synced to a server; subscriptions UI.


## Arguments in the field picker

Arguments are part of the picker, but they only appear when needed. Treat the mockup's expanded panels as the *editing* state, not the resting state. Reference screen: "01d · Studio — arguments in the field picker" on the design canvas.

### When argument panels show
- **Unticked field:** no panel. Show a short hint after the name: `statements(year*)`, `spendingSummary(period*, …2)`, `disputes(…1)`. `*` = required with no default; `…N` = number of optional args.
- **Just ticked, or a required arg is missing:** the panel opens and focus moves to the first empty argument. A panel with an unresolved problem stays open.
- **Valid:** the panel collapses to a one-line summary on the field row, e.g. `id: $id`, `first 20 · TRAVEL · since Oct 1`, `window: NEXT_30_DAYS`. Click the summary or press Enter on the row to reopen it.
- **One panel open at a time.** Opening another collapses the previous one, unless it still has a problem.
- **Follows the editor:** placing the cursor inside a field's arguments in the editor opens that field's panel. Moving away collapses it.

### Binding: variable vs. value
- Each arg row has a **$ variable / value** switch. Required args default to **$ variable**:
  - ticking `customer` adds `$id: ID!` to the operation's parameter list and the key to Variables;
  - switching to value writes the literal into the query and removes the variable.
- The Variables drawer is the only place variable values live. An arg bound to a variable shows a `$name` chip that jumps to it. The picker never keeps its own copy.
- Optional args nobody touches stay out of the query. Never write schema defaults into it.

### Controls by type
| Type | Control |
|---|---|
| Enum | Dropdown, deprecated values struck through. "Any" option omits the argument. |
| Boolean | Toggle |
| Int / Float | Number field. Schema default as placeholder. |
| ID | Combo box with the Global ID helper. Type is pre-set from `@idOf` **[verify]**. |
| Date / DateTime | Date input with expected format shown |
| List | Chip input |
| Input object | Collapsible group for shallow inputs. For deep inputs (mutation payloads), show "Edit in Variables →" and use the JSON editor's schema autocomplete instead of generating a form. |

- **Fields with many args:** show required args and any already in use. The rest go behind "+ N optional", with search if N > 5.
- **Pagination** (`first`/`after`/`last`/`before` on connection fields) becomes one control: `first N · from start`, **Next page** and **Start**.
  - Next page copies `pageInfo.endCursor` from the last response into the bound `after` variable and re-runs the query.
  - The result table's footer has the same Next page control.

### Pre-filling required args (no schema default)
Try these in order:
1. **Last value used** for that argument in this environment. Stored in the browser per environment and labelled "last used".
2. **From the last response:** offer IDs of the matching `@idOf` type found in the previous result ("Use Customer:8f2k1 from last result").
3. **Shared test data** per environment, from server config (e.g. a staging test customer per module). Never in prod. **[verify]** whether such data already exists.
4. Otherwise empty, with a placeholder: format example for IDs, chips for enums. **Never pre-select an enum value.**

A non-null argument **with** a schema default (`arg: T! = X`) is not required. Show it pre-filled and marked "default", with no `*`. Leave it out of the query unless changed.

### Validation
- Neutral first: a ticked field with a missing required arg shows a grey "needs a value" hint, not an error.
- It turns red only after a Run attempt, or when the user moves on and leaves it empty.
- **On a failed Run:**
  - the field row gets a marker;
  - the editor line gets a red underline and an inline message;
  - the response pane explains what's missing and offers a one-click fix where obvious;
  - nothing is sent to the server.
- An empty bound variable shows a placeholder in the Variables drawer, never `null`, so the drawer never looks valid when it isn't.

### Two-way sync and limits
- Args typed in the editor show up in the picker.
- Where the editor holds something the picker can't represent, the row shows **"set in query"**, read-only, with "Move to a variable". Examples: a variable reused across fields, a nested input literal, directives.
- **Out of scope for the picker:** `@include`/`@skip`, aliases and fragments. These stay editor-only.

### Acceptance
- Ticking a field with a required arg creates the variable, focuses the input, and shows "needs a value" without an error.
- Collapsed rows show an accurate one-line summary of the arg values.
- Next page round-trips: the cursor goes into the variable, the query re-runs, and the row range advances.
- Switching variable ↔ value updates the parameter list, the query and the Variables drawer together.
- Editing args in the editor updates the picker. Unrepresentable args show "set in query" and are never overwritten.

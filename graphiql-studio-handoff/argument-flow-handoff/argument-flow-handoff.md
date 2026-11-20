# Handoff: field picker argument flow

**Audience:** a Claude Code agent with full access to the Viaduct monorepo and its context.
**Builds on:** `graphiql-studio-handoff.md`, which covers the overall Studio shell, theme tokens and Viaduct metadata. This doc covers one component in depth: **how the schema field picker lets people fill in field arguments.**
**Status:** interaction design is settled and prototyped. The prototype's schema and data are made up.

## Attachments

| File | What it is |
|---|---|
| `argument-flow-reference.html` | A **working prototype**. Open it in a browser, no build or network needed, and click through the whole flow. Its `<script type="text/x-dc">` block holds the reference logic: state model, rules and request building. Use it to settle "what should happen when…" questions. It is **not** production code: it uses a throwaway template runtime, and the fonts fall back offline. |
| `screens/01-initial.png` | Nothing ticked. Unticked fields show argument hints such as `(window*)` and `(year*, …1)`. |
| `screens/02-customer-ticked-prefilled.png` | Ticking `customer` opens its panel. `id` is pre-filled ("last used"), bound to `$id`, and the ID suggestion list is open. |
| `screens/03-required-needs-value.png` | `customer` has collapsed to its summary. `scheduledTransfers` is open with `window*` in the grey "needs a value" state. |
| `screens/04-left-empty-turns-red.png` | The user moved on to `statements` without choosing a window: `scheduledTransfers` turns red and stays open. `statements` shows required `year*` next to `format`, which has a default. |
| `screens/05-run-blocked.png` | Run with missing values: blocked, issues listed with Fix buttons, nothing sent. |
| `screens/06-fixed-ready.png` | Issues resolved. "All fixed. Press Run again." `format` changed from its default, with a reset link. |
| `screens/07-run-passed-summaries.png` | Run passed. Every field collapses to a one-line summary. |
| `screens/08-enum-dropdown.png` | Enum with more than 4 values as a dropdown: "Any (leave out)", deprecated value struck through. |
| `screens/09-pagination-and-optional.png` | Pagination after two Next page clicks (`$txAfter` set), with the optional arguments expanded. |
| `screens/10-id-suggestions-from-result.png` | `account.id` filled in "from last result"; same-name variables get distinct names (`$customerId`, `$accountId`). |
| `screens/11-input-object-and-var-naming.png` | Shallow input object (`payees.filter`) edited in place and written into the query as a value. |

## Scope

**In scope:** the picker's argument UI, its state, its validation, and the **operation model** it produces (selected fields, arguments, variable declarations, variable values).

**Out of scope here:**
- **Syncing with the editor.** The picker must expose an operation model that the editor integration can read from and write to. The rules are in the Studio brief: args typed in the editor show up in the picker; anything the picker can't represent shows "set in query", read-only.
- **The Run check panel, request preview and flow log** in the prototype. These are test scaffolding. In Studio, validation surfaces in the editor, the Run button and the response pane, as the Studio brief describes. The run-blocking rule itself is in scope.

## Inputs from the schema

| Need | Source |
|---|---|
| Arg name, type, nullability | Introspection (`__InputValue.type`) |
| Default value | Introspection (`__InputValue.defaultValue`) |
| Enum values and deprecation | Introspection (`__EnumValue.isDeprecated`) |
| Input object fields | Introspection |
| ID target type for the ID control | Viaduct `@idOf`, which isn't in introspection. Comes from the Studio metadata endpoint. **[verify]** directive name, arguments, and where it can be applied. |
| Connection args (`first`/`after`/`last`/`before`) | Detect by convention: the field returns a type with `edges` and `pageInfo`, and has those args. **[verify]** that this matches how connections are modelled in the repo. |
| Staging test IDs | Optional server config, per environment and per type. Never served in prod. **[verify]** whether this exists. Ship without it if not. |

**Derived rules:**
- **Required** = non-null type **and** no `defaultValue`. Only these get `*`.
- **Has default** = `defaultValue` present, whether nullable or not. Shown pre-filled, marked "default". Never written into the query unless changed.

## State model

The prototype's `initialState()` and `initialFields()` show the exact shape.

**Per field:**
- `selected`
- `vals`: one entry per arg
- `bind`: per arg, true = `$variable`, false = inline value
- `src`: per arg, where a pre-filled value came from: `last used`, `from last result` or `test data`
- `optOpen`: optional args expanded
- `left`: the user moved away with a required value missing

**Global:**
- `open`: the one field whose panel the user opened
- `attempted`: Run has been pressed at least once
- `ran`: a Run has passed, so the cursor and result IDs exist
- `page`: current page
- `lastUsed`: by ID type, stored in the browser per environment
- open dropdown or suggestion list

A child field counts as selected only if its parent is selected too.

## Panel lifecycle

| Event | Result |
|---|---|
| Tick a field with args | Pre-fill required ID args (see below). The panel opens and becomes `open`. Focus moves to the first empty required arg, or the first visible arg. |
| Tick a field without args | Selected. Nothing opens. |
| Click a collapsed row (field ticked) | Its panel opens. Clicking the open row again works like Done. |
| Click an unticked row | Same as ticking it. |
| Open another panel, or Done/Esc, while the current one is **valid** | It collapses to its one-line summary. |
| Open another panel, or Done/Esc, while a required value is **missing** | Set `left = true`. The field turns red and its panel **stays open** alongside the new one. |
| Untick | Deselect and close. If it was `open`, nothing is open now. |
| Run with problems | Set `attempted = true`, mark every problem field `left`, open the first one and focus its first missing arg. **Nothing is sent.** |
| Run passes | Set `ran = true` and close all panels. ID values used in the run become `lastUsed`. The cursor and result IDs become available. |

**Which panels are visible:** the `open` one, plus every selected field in the red state. So at most one panel is open by choice; any others are open because they need fixing.

## Field status

| Status | Condition | Row shows |
|---|---|---|
| ok | All required args set | Summary line (when collapsed) |
| needs | Required missing, and neither `left` nor `attempted` | Grey "needs a value" pill on the row and on the arg. The input border stays neutral. |
| error | Required missing, and `left` or `attempted` | Red dot and "missing ⟨args⟩" on the row. Red left border and tint on the panel, red "required" on the arg, "Required. Pick one." under it. |

Never show red to someone who is still filling a field in for the first time.

## Which args are shown

In an open panel, always show:
- required args;
- **primary** args;
- args with a non-default value;
- nullable booleans that have been set.

Everything else goes behind **"+ N optional"**, which becomes "Show fewer" when expanded.

The prototype marks "primary" args by hand: pagination, a commonly used filter, defaults worth seeing. **[decide]** how real primary args are chosen. Options: a directive or metadata hint, usage stats, or "always show args that have a default".

**Row hint while unticked:** `(` required names with `*`, then `…N` for optional args, then `)`. Examples: `(id*)`, `(year*, …1)`, `(…6)`.

## Controls by type

| Arg type | Control | Notes |
|---|---|---|
| `ID` | Combo box: a fixed chip showing the `@idOf` type, a text input, and a ▾ suggestion list | Focusing the input opens suggestions grouped as LAST USED, FROM LAST RESULT and TEST DATA · STAGING. An empty list explains how to get IDs. Shows "Encodes to ⟨global id⟩" underneath. **[verify]** the encoding: the prototype uses base64 of `Type:id`; use Viaduct's codec or a server endpoint. |
| Enum, ≤ 4 values | Chips (radio) | Required: no pre-selection. Optional: clicking the selected chip clears it. |
| Enum, > 4 values | Dropdown listbox | First option "Any (leave out)" if optional. Deprecated values struck through and labelled. **Don't use a native `<select>`** if templates render options in a loop: browsers drop non-`<option>` children of `<select>` when parsing. |
| List of enum | Multi-select chips | Empty list = argument left out. |
| `Boolean` with default | Switch | Shows `true`/`false`; marked "default" or "changed". |
| `Boolean` nullable, no default | Switch | Cycles unset → true → unset ("not set"). Unset = left out. |
| `Int` / `Float` | Number input | Placeholder: an example, or "default N". |
| `Date` / `DateTime` | Date input | Shows the format. |
| Input object, shallow (scalar/enum/bool fields only) | Bordered group of sub-controls | Any sub-field set = argument set. Unset sub-fields are left out. |
| Input object, deep | Not edited in the picker | Row says "Edit in Variables →". |
| Connection pagination | One control: `first` −/+ in steps of 10 (10–100), "from the start" / "page N · after ⟨cursor⟩", **Start**, **Next page** | Next page is disabled with a hint until a Run passes. It copies `pageInfo.endCursor` from the last response into `$txAfter` and re-runs. Changing `first` goes back to page 1. Always bound to variables. |

**Tags** sit on the right of each arg's header line: "needs a value", "required", "default", "changed" (with a **reset** link), and the pre-fill source ("last used", "from last result", "test data").

## Variable vs. value

- Every arg except pagination has a **$** toggle. Required args start as variables; optional args start as inline values.
- **Bound:** declared in the operation's parameter list, referenced as `$name` in the field's args, and its value sent in Variables.
- **Inline:** the literal is written in the query. IDs are written encoded.
- **Variable naming:** the arg name, unless two *selected* fields bind args with the same name. Then use `fieldName + ArgName` (`$customerId`, `$accountId`). Recompute names as selection changes.
- **Leaving args out:**
  - unset optional args are left out entirely;
  - default args left unchanged are left out;
  - a bound required arg with no value is declared, and appears in Variables as a **placeholder** (`‹needs a value›`), never as `null`.

## Pre-filling required ID args (on tick, only if empty)

1. `lastUsed[type]` → tag "last used"
2. If a Run has passed and the result had IDs of this type → the first one, tagged "from last result"
3. Staging test ID for this type, if configured → "test data"
4. Otherwise empty, with the placeholder "internal id, or paste an encoded ID"

**Never pre-fill enums or other scalars.** Wrong guesses give results that are wrong without looking wrong.

## Summary line (collapsed, selected)

Join these with ` · `:
- **pagination:** `first N · from start|page N`
- **each set, non-default arg:**
  - bound: `name: $var (value)`
  - inline: `name: value`
  - IDs show as `Type:id`, lists as `[A, B]`, inputs as `{ k: "v" }`

If nothing is set, show "no arguments set · N optional", muted. Truncate with an ellipsis. Never wrap.

## Keyboard and accessibility

- **Rows and checkboxes:** the checkbox is a `role="checkbox"` button; the row is a button with `aria-expanded`.
- **Panels:** `role="group"` labelled "Arguments for ⟨field⟩". Esc acts as Done.
- **Chips:** `radiogroup`/`radio`, or `group`/`checkbox` when multi-select. Switches use `role="switch"`. Dropdowns and suggestions use `aria-haspopup="listbox"` with `role="option"` items.
- Focus moves into the panel on open (see lifecycle). When a panel collapses, return focus to its row.
- Picking from the suggestion list must not blur the input first. The prototype calls `preventDefault` on the option's `mousedown`.
- Contrast and colors follow the Studio tokens. Error = `#FF9DB5` family; "needs a value" = neutral grey outline; default/source tags use the blue tint.

## Acceptance criteria

Each criterion maps to a screenshot.

1. **(02)** Ticking a field with a required ID pre-fills it from last used, opens the panel, shows the source tag and focuses the input.
2. **(03)** Ticking a field with a required enum shows grey "needs a value". No red, no pre-selected chip.
3. **(04)** Moving on with a required value missing turns that field red and keeps its panel open. The newly opened panel is also visible.
4. **(05)** Run with problems sends nothing, opens and focuses the first problem, and lists all of them.
5. **(06)** Fixing a problem clears its red state immediately. A changed default shows "changed" and reset; reset restores the default and removes it from the query.
6. **(07)** A passing Run collapses all panels to accurate summaries.
7. **(08)** "Any" removes the arg from the operation. Deprecated values are visibly marked.
8. **(09)** Next page is disabled before a passing Run. After it, each click sets `$txAfter` to the previous `endCursor`. Changing `first` returns to page 1. "+ N optional" reveals the hidden args.
9. **(10)** After a passing Run, a newly ticked `account` pre-fills from the result IDs, and the ID suggestion list offers them. Two bound `id` args get distinct variable names.
10. **(11)** Shallow input objects are edited in place. Only set sub-fields are sent.
11. Switching **$** on an arg moves it between the parameter list + Variables and an inline literal, with no other change to the operation.
12. Unticking a parent hides its children and drops them from the operation and from validation. Their state is kept if the parent is ticked again.

## Edge cases to decide or verify

- **[decide]** Leaving an arg empty after it was pre-filled: should it fall back to a suggestion, or stay empty and become "needs a value"? The prototype keeps it empty.
- **[decide]** Interface/union fields: do inline fragments get their own argument panels? Not prototyped.
- **[verify]** `@scope`: hide args that aren't visible in the current scope, the same way fields are.
- **[verify]** Viaduct mutations: input-heavy, so expect most to hit the "Edit in Variables" path.
- **[decide]** Whether `lastUsed` is stored per user per environment in the browser, or on the server.
- Many-arg fields (more than 10): add search inside "+ N optional".

# Handoff: Studio light theme, exact colors and type

**Goal:** make the implemented light theme match the design exactly, especially the **header bar** (customer-graph pill, scope switcher, search), which was recently changed to have more contrast.
**How to use this doc:** components are identified by **number, role and position**, not class names, because your stylesheet's names will differ. Find the element that plays each role, then make its computed styles match the values below. All values are literal, with no opacity tricks or color mixing, and 1 CSS px = 1 design px.

## Screenshots

| File | What it shows |
|---|---|
| `01-annotated-full.png` | Whole screen with numbered components 1–17 (rendered at 2×) |
| `02-header-annotated.png` | Header strip with components 1–6 numbered underneath |
| `03-header-clean.png` | Header strip, unannotated, for pixel comparison |
| `04-full-clean.png` | Whole screen, unannotated |

The screenshots render JetBrains Mono at weight 400 wherever 500 is specified, because only Regular and Bold were installed on the rendering machine. Your build should load the real 500 weight.

## 1. Fonts (check these first)

| Role | Family stack | Weights to load |
|---|---|---|
| UI text | `Inter, system-ui, sans-serif` | 400, 500, 600 |
| Code, identifiers, IDs, enum values | `'JetBrains Mono', monospace` | 400, 500 |

- **Self-host both fonts** (woff2 with `@font-face` and `font-display: swap`). Don't load them from a CDN at runtime.
- **Base size:** the app root is `font-size: 13px`, using Inter. Everything below is in px, not rem/em, so inherited sizes can't drift.
- **Line height:** single-line controls use `normal`. Use `1.5` for descriptions and paragraphs. Code panes use `13px / 22px`.
- **No letter-spacing** anywhere except the wordmark (`-0.01em`) and the uppercase micro-labels (`0.04–0.06em`).

### Common reasons type comes out wrong
1. **Buttons and inputs don't inherit fonts by default.** Add `button, input, select, textarea { font: inherit; color: inherit; }`. Without it, every button renders in the system font at about 13.33px. This is the most likely cause of "close but not quite".
2. **The mono font is silently falling back.** In devtools, select a code token and check **Computed → Rendered Fonts**. It must say *JetBrains Mono*, not Menlo, Consolas or DejaVu Sans Mono.
3. **GraphiQL's own stylesheet sets font sizes and families on its containers.** Override them on the GraphiQL root, or with matching specificity. **[verify]** which variables or selectors your GraphiQL version uses, e.g. `--font-family`, `--font-size-body`, `--font-family-mono`.
4. **The root size is inherited from `html { font-size: 16px }`.** Set 13px on the app root explicitly.

## 2. Color tokens (light)

```css
:root[data-theme="light"] {
  /* surfaces */
  --bg:            #F6F7F9;  /* app background, request drawer */
  --surface:       #FFFFFF;  /* sidebar, editor, active tab */
  --raised:        #F1F3F6;  /* inputs, docs card, segmented-control track */
  --header-bg:     #EEF0F4;  /* header bar only */
  --hover:         #EBEEF2;
  --selected:      #E8EEFB;  /* selected row, active rail item, active scope/drawer tab */

  /* borders */
  --divider:       #E3E6EB;  /* pane dividers, tab outlines */
  --border:        #DDE1E7;  /* cards, header bottom border */
  --border-strong: #D3D8E0;  /* kbd, dividers inside the service pill */
  --control-edge:  #848D9C;  /* header controls only */
  --checkbox-off:  #B6BDC8;

  /* text */
  --text:          #14171C;
  --text-2:        #3D4350;
  --muted:         #5B6372;  /* labels; 4.5:1 or better on every surface above */
  --faint:         #A3AAB6;  /* line numbers and separators only, never text people need to read */

  /* accent and status */
  --accent:        #3B5BDB;  /* Run, checkboxes; text on it is #FFFFFF */
  --accent-strong: #1E3A8A;  /* text on --selected */
  --ok:            #166534;   --ok-bg:   #E7F6EC;
  --warn:          #B45309;   --warn-bg: #FEF6EC;
  --danger:        #BE185D;   --danger-bg: #FDF2F7;
  --shadow-control: 0 1px 2px rgba(16, 24, 40, 0.06);
  --shadow-seg-on:  0 1px 2px rgba(16, 24, 40, 0.14);
}
```

Syntax and badge colors are unchanged from the main Studio brief: keyword `#7C3AED`, operation `#0F766E`, variable `#BE185D`, type `#1D4ED8`, argument `#B45309`, string `#15803D`, punctuation `#6B7280`, JSON key `#1E5AA8`.

## 3. Header bar (components 1–6). This is the part that changed.

**The bar itself:**
- Background `#EEF0F4`, a step darker than the white panels below; previously it matched the app background. Bottom border `1px solid #DDE1E7`.
- Padding `10px 16px`. Children are a flex row, wrapping, `gap: 10px`, vertically centred. Total height **57px**.
- **Wordmark** (left, not numbered): a 22px hexagon icon with stroke `#3B5BDB` 1.8, then "GraphiQL" in Inter **15px / 600**, `#14171C`, `letter-spacing: -0.01em`, with a 10px gap.

**Every header control (1, 2, 3, 5) shares one shell.** This is the contrast fix:
```
height: 36px; box-sizing: border-box;
background: #FFFFFF;
border: 1px solid #848D9C;
border-radius: 10px;
box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06);
```

| # | Component | Layout | Contents, with type and color |
|---|---|---|---|
| 1 | **Service pill** (customer-graph · build · modules) | Shell above, padding `0 12px`, flex row with `gap: 12px` | Status dot: 7px circle `#166534`.<br>Service name: Inter **13px / 500** `#14171C`.<br>Dividers: 1×16px `#D3D8E0`.<br>Build text: JetBrains Mono **11px / 400** `#5B6372`, no wrapping.<br>Module count: Inter **11px / 400** `#5B6372`. |
| 2 | **Scope switcher** (`default` \| `internal`) | Shell above, padding `3px`, flex row with `gap: 2px` | Label: 13px globe icon (stroke 2) plus "Scope" in Inter **11px / 400** `#5B6372`, padding `0 8px 0 6px`, gap 5px.<br>Options: JetBrains Mono **12px**, height 28px, padding `0 10px`, radius 7px.<br>**Active:** bg `#E8EEFB`, text `#1E3A8A`, weight **500**, no shadow.<br>**Inactive:** transparent, text `#5B6372`, weight 400. |
| 3 | **Search** | Shell above, padding `0 10px 0 12px`, `gap: 8px`, `flex: 1 1 200px; max-width: 320px` | Icon: 15px search, stroke 2, `#5B6372`.<br>Placeholder: Inter **13px / 400** `#5B6372`, **one line with an ellipsis** (`white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0`).<br>Shortcut chip `⌘K`: Inter **11px**, bg `#EBEEF2`, border `1px solid #D3D8E0`, radius 5px, padding `1px 6px`. |
| 4 | **Environment label** (Staging) | **No shell**: transparent, no border. Height 36px, padding `0 10px`, gap 6px | 7px dot `#B45309`, then "Staging" in Inter **12px / 400** `#B45309` |
| 5 | **Share button** (icon only) | Shell above, **36×36px**, icon centred | 16px share icon, stroke 1.8, `#14171C`. Needs `aria-label`. |
| 6 | **Run button** | **Not the shell**: no border, no shadow. Height 36px, padding `0 14px`, gap 8px, radius 10px, bg `#3B5BDB` | 13px filled play icon, then "Run" in Inter **13px / 600** `#FFFFFF`, then "⌘↵" in Inter **11px / 500** `#FFFFFF` at `opacity: 0.75` |

Spacing between groups: a flexible spacer sits between Search (3) and Staging (4). Everything else is separated only by the 10px gap.

**Accessibility:** control outlines are about 3:1 against the white control fill and about 2.9:1 against the bar. All header text is at least 6:1.

## 4. Rest of the screen (components 7–17)

| # | Component | Spec |
|---|---|---|
| 7 | **Left rail, active item** | 40×40px, radius 10px, bg `#E8EEFB`, icon 18px stroke 1.8 `#3B5BDB`. Inactive items: transparent, icon `#5B6372`. Rail: 56px wide, divider on the right `#E3E6EB`, background `#F6F7F9`. |
| 8 | **Schema tree, selected row** | Height 30px, radius 6px, bg `#E8EEFB`. Row text JetBrains Mono **12px / 400**: field name `#14171C`, type `#5B6372`. Checkbox 14px, radius 4px: checked = `#3B5BDB` fill with a white check; unchecked = `1.5px solid #B6BDC8`. Sidebar background `#FFFFFF`; header text "Schema" Inter 13px / 600; filter input bg `#F1F3F6`, border `#DDE1E7`, height 32px, radius 8px. |
| 9 | **Resolver badge and module chip** | Badge (N/F/B): JetBrains Mono **10px / 500**, transparent, 1px border, radius 4px, padding `0 4px`. N `#0F766E` on border `#99D5CC`; F `#3B5BDB` on `#B8C6F5`; B `#B45309` on `#F0C99A`. Module chip: Inter **10px / 400** `#3D4350` on `#EEF0F4`, radius 4px, padding `1px 5px`. |
| 10 | **Docs card** | bg `#F1F3F6`, border `1px solid #DDE1E7`, radius 12px, padding 14px, 12px margin from the sidebar edges, gap 10px. Title line JetBrains Mono 12px (type name `#1D4ED8`, field `#14171C`, return type `#5B6372`). Description Inter 13px / 1.5 `#3D4350`. Metadata grid Inter 12px: labels `#5B6372`, values `#14171C`; resolver/scope values in mono 11px. Link Inter 12px `#3B5BDB`. |
| 11 | **Query tab, active** | Height 36px, padding `0 12px`, gap 8px, bg `#FFFFFF`, border `1px solid #E3E6EB` with no bottom edge, radius `8px 8px 0 0`, sits 1px over the tab strip's bottom border. Label Inter **13px / 400** `#14171C`. Inactive tabs: transparent, `#5B6372`. Q/M tag: JetBrains Mono 10px / 500, padding `1px 4px`, radius 4px (Q `#0F766E` on `#DDF3EF`; M `#BE185D` on `#FCE7F1`). Unsaved dot: 6px `#B45309`. |
| 12 | **Editor** | bg `#FFFFFF`, JetBrains Mono **13px / 22px**. Line numbers `#A3AAB6`, right-aligned in a 44px gutter with a 12px gap. Current line bg `#E8EEFB`, line number on it `#5B6372`. Cursor: 2px `#3B5BDB`. Run link above the code: Inter 11px `#3B5BDB`; "last run" note Inter 11px `#5B6372`. |
| 13 | **Variables / Headers tabs** | Strip bg `#F6F7F9`, top border `#E3E6EB`. Tabs: height 30px, padding `0 12px`, radius 7px, Inter 13px. **Active:** bg `#E8EEFB`, text `#1E3A8A`, weight 500. **Inactive:** transparent, `#5B6372`. Status text on the right: Inter 11px `#166534`. |
| 14 | **Response segmented control** (JSON / Table / Resolvers) | Track: bg `#F1F3F6`, border `1px solid #DDE1E7`, radius 9px, padding 3px. Segments: height 28px, padding `0 14px`, radius 6px, Inter 13px. **Active:** bg `#FFFFFF`, text `#14171C`, weight 500, shadow `0 1px 2px rgba(16,24,40,0.14)`. **Inactive:** transparent, `#5B6372`. A white pill with a shadow is correct here because the track is grey. In the header (2) the active option is the blue tint instead. |
| 15 | **Status chip** (200 OK) | Inter **12px / 500** `#166534` on `#E7F6EC`, radius 6px, padding `3px 8px`, with a 6px dot `#166534` and 6px gap. Neighbours: "88 ms" in 12px `#3D4350`; "2.6 KB" in 12px `#5B6372`. |
| 16 | **Scope notice** (default scope) | bg `#FFF7EB`, border `1px solid #F3DFC2`, radius 10px, padding `10px 12px`, gap 10px. Inter **12px / 1.4** `#7A4510`. Identifiers in mono. Link "Switch scope" underlined, same color. 16px lock icon, stroke 1.8. |
| 17 | **Status bar** | Inter **11px** `#5B6372`, padding `6px 16px`, gap 16px, top border `#E3E6EB`. Validity dot: 6px `#166534`. |

## 5. Checking your work

For each numbered component, compare devtools **Computed** values against the tables above:
- background-color
- border color and width
- font-family (Rendered Fonts)
- font-size
- font-weight
- color
- height and box-sizing

Then lay your build over `03-header-clean.png` at 50% opacity at the same viewport (1440 wide, device pixel ratio 2) to check the header lines up.

**Done when:**
- every header control (1, 2, 3, 5) has a visible white body and a dark-grey outline against the darker bar;
- the active scope option is a blue tint;
- the search placeholder sits on one line;
- every code token renders in JetBrains Mono.

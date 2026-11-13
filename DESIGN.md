---
name: Scholarship Desk
description: A local desk that shows every funded master's and PhD opportunity, deadline and next step on one packed screen, in lilac, white and black.
colors:
  ground: "#ffffff"
  panel: "#ffffff"
  fill: "#f4f2f7"
  fill-2: "#faf8fc"
  line: "#e7e3ee"
  line-2: "#d5cfe0"
  ink: "#111111"
  ink-2: "#2b2b2b"
  mute: "#5c5866"
  lilac: "#c8a8e9"
  lilac-mid: "#e6d9f7"
  lilac-soft: "#f4eefc"
  lilac-deep: "#6a3fa8"
  lilac-deeper: "#55308a"
  on-accent: "#ffffff"
  on-lilac: "#111111"
  on-lilac-2: "#2b2b2b"
  on-lilac-accent: "#4b2384"
  ok: "#111111"
  warn: "#6a3fa8"
  warn-soft: "#f4eefc"
  info: "#2b2b2b"
  violet: "#5c5866"
typography:
  wordmark:
    fontFamily: "Segoe UI, Yu Gothic UI, Hiragino Sans, Helvetica Neue, Noto Sans, system-ui, sans-serif"
    fontSize: "23px"
    fontWeight: 900
    lineHeight: 1
    letterSpacing: "-0.03em"
  numeral-display:
    fontFamily: "Bahnschrift, DIN Alternate, DIN Condensed, Arial Narrow, Roboto Condensed, Segoe UI, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: 0.9
    fontFeature: "tnum"
  numeral-inline:
    fontFamily: "Bahnschrift, DIN Alternate, DIN Condensed, Arial Narrow, Roboto Condensed, Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    fontFeature: "tnum"
  numeral-small:
    fontFamily: "Bahnschrift, DIN Alternate, DIN Condensed, Arial Narrow, Roboto Condensed, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 700
    fontFeature: "tnum"
  headline:
    fontFamily: "Segoe UI, Yu Gothic UI, Hiragino Sans, Helvetica Neue, Noto Sans, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 700
  title:
    fontFamily: "Segoe UI, Yu Gothic UI, Hiragino Sans, Helvetica Neue, Noto Sans, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 700
  body:
    fontFamily: "Segoe UI, Yu Gothic UI, Hiragino Sans, Helvetica Neue, Noto Sans, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  body-dense:
    fontFamily: "Segoe UI, Yu Gothic UI, Hiragino Sans, Helvetica Neue, Noto Sans, system-ui, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.3
  label:
    fontFamily: "Segoe UI, Yu Gothic UI, Hiragino Sans, Helvetica Neue, Noto Sans, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 700
  tag:
    fontFamily: "Segoe UI, Yu Gothic UI, Hiragino Sans, Helvetica Neue, Noto Sans, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    lineHeight: 1.3
rounded:
  none: "0px"
  r: "2px"
spacing:
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "12px"
  gutter: "20px"
components:
  top-bar:
    backgroundColor: "{colors.lilac}"
    textColor: "{colors.on-lilac}"
    typography: "{typography.title}"
    padding: "10px 20px"
  button-primary:
    backgroundColor: "{colors.lilac-deep}"
    textColor: "{colors.on-accent}"
    typography: "{typography.title}"
    rounded: "{rounded.r}"
    padding: "7px 12px"
  button-primary-hover:
    backgroundColor: "{colors.lilac-deeper}"
    textColor: "{colors.on-accent}"
  button-top-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.on-accent}"
    typography: "{typography.title}"
    rounded: "{rounded.r}"
    padding: "7px 12px"
  button-default:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.title}"
    rounded: "{rounded.r}"
    padding: "7px 12px"
  tab:
    backgroundColor: "{colors.lilac-mid}"
    textColor: "{colors.ink-2}"
    typography: "{typography.title}"
    rounded: "{rounded.none}"
    padding: "8px 14px"
  tab-active:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
  module-header:
    backgroundColor: "{colors.lilac-mid}"
    textColor: "{colors.ink}"
    typography: "{typography.title}"
    height: "32px"
  module-sub:
    backgroundColor: "{colors.lilac-soft}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    padding: "6px 10px"
  tag-state:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink-2}"
    typography: "{typography.tag}"
    rounded: "{rounded.r}"
    padding: "1px 6px"
  tag-decided:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.panel}"
    typography: "{typography.tag}"
    rounded: "{rounded.r}"
    padding: "1px 6px"
  tag-urgent:
    backgroundColor: "{colors.lilac-deep}"
    textColor: "{colors.on-accent}"
    typography: "{typography.tag}"
    rounded: "{rounded.r}"
    padding: "1px 6px"
  rank-marker:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.panel}"
    typography: "{typography.numeral-small}"
    rounded: "{rounded.none}"
    size: "20px"
  input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.r}"
    padding: "6px 9px"
---

# Design System: Scholarship Desk

## Overview

**Creative North Star: "The Packed Mosaic"**

Scholarship Desk is a high-density mosaic in the Japanese web-portal tradition (catalog world `japanese-high-density-web`, chosen by the user; seed `ab41c36ee743b8e1`). Everything the applicant must know and do sits on one screen as a grid of hairline-ruled rectangular modules: next deadlines, what needs them, pipeline and fit, documents, drafts, what is coming up, and the full list. Nothing floats, nothing is padded for air. Information is the decoration.

The palette is **lilac, white and black**, the user's choice on 2026-11-12, replacing the original utility red. Lilac owns the shell as fields: the top bar, the tab strip and every module header. Black carries text, the active tab, module tabs and decided tags. Deep lilac is the single accent that carries text and urgency: days-left figures, notes, urgent tags and focus. Numbers are set like prices in a DIN-style face so the eye can scan figures down a column. Text is the platform UI sans at 12 to 13px with tight leading.

The system runs under hard constraints that are part of its identity: system font stacks only (the user declined self-hosting a web font on 2026-11-12), a CSP of `default-src 'self'` (no external fonts, no inline styles), DOM built with `textContent`, and no build step. There is no dark theme: the background is always white, whatever the system setting (the user's choice, 2026-11-12).

**Key Characteristics:**
- 12-column mosaic of bordered modules with 8px gutters, everything above the fold on desktop.
- Lilac shell: lilac top bar, light lilac tab strip and module header bars, each module headed by a black tab at its left edge.
- Heavy tabular DIN-style numerals for days left, counts, dates and KPIs, in deep lilac when urgent.
- Three colours only: lilac, white, black. Status lives in outlined tags; only black (decided) and deep lilac (urgent) fill.
- 2px corners, 1px hairlines, dotted row separators, zero shadows.

## Colors

Lilac fields, a white ground, black ink, and one deep lilac that does the accent's work.

### Lilac family
- **Lilac** (`lilac`): the top bar field and text selection. Always carries black text (`on-lilac`).
- **Lilac Mist** (`lilac-mid`): the tab strip and module header bars.
- **Lilac Wash** (`lilac-soft`): module sub-headers, table heads, the selected item in split lists, dropzone hover, the warning banner, and the row flash after an action.
- **Deep Lilac** (`lilac-deep`): urgent days-left figures (30 days or fewer), module notes, tab counts, overdue figures, urgent and NEW tags, the first-ranked "Needs you" marker, primary buttons inside pages, focus ring, caret, form accent, link hover, errors.
- **Pressed Lilac** (`lilac-deeper`): hover on deep-lilac fills.
- **On Lilac** (`on-lilac`, `on-lilac-2`, `on-lilac-accent`): dark text on the lilac top bar; "Desk" in the wordmark uses `on-lilac-accent`.

### Neutral
- **Paper** (`ground`, `panel`): page and module backgrounds, both white.
- **Lilac Grey** (`fill`): inline code and quiet fills.
- **Row Tint** (`fill-2`): row hover, detail rows, inline forms, dropzone.
- **Hairline** (`line`): table row rules, KPI cell dividers, sub-header rules.
- **Rule** (`line-2`): module, input, button and tag borders; dotted row separators.
- **Ink** (`ink`): all primary text, the 2px rule under the top bar, the active tab, module tabs, decided tags, rank markers, the top bar's primary button, toast.
- **Soft Ink** (`ink-2`): tab labels, table heads, field labels, neutral tag text, body links.
- **Mute** (`mute`): secondary lines (sponsor, country, "days"), placeholders, empty states.

### Status aliases
The former status hues collapse into the three-colour scheme: `ok` is ink (Eligible, No fee, Read, passed requirements), `warn` is deep lilac (Check details, Application fee, Changes asked), `info` is soft ink (Preparing, Draft, links), `violet` is mute (Opens soon, Near miss). All appear only as text with a matching outline.

There is no dark theme. The stylesheet declares `color-scheme: light` and the page carries `<meta name="color-scheme" content="light">`, so the ground, form controls and scrollbars stay white even when the system is in dark mode.

### Named Rules
**The Three-Colour Rule.** Lilac, white and black, nothing else. Lilac is a field (bar, strip, header); black is text and decisions; deep lilac is the only accent and marks urgency and focus. Never add a hue for status.

**The Outline-Only Status Rule.** States appear as text with a 1px outline on the panel colour. The only filled tags are ink (decided) and deep lilac (urgent).

## Typography

**Text Font:** the platform UI sans, `"Segoe UI"` first (then Yu Gothic UI, Hiragino Sans, Helvetica Neue, Noto Sans, system-ui).
**Numeral Font:** the platform DIN-style face, `Bahnschrift` / `"DIN Alternate"` first (then DIN Condensed, Arial Narrow, Roboto Condensed, the UI sans).
**Code:** Consolas, SF Mono, Menlo (inline commands only).

**Character:** a compact gothic sans for words and a condensed engineering face for figures, so numbers read as a separate, louder channel. Both are system fonts by the user's explicit decision (2026-11-12).

### Hierarchy
- **Wordmark** (900, 23px, line-height 1, -0.03em): "Scholarship**Desk**" in black on the lilac bar, with "Desk" in `on-lilac-accent`.
- **Numeral Display** (Bahnschrift 700, 30px, line-height 0.9, tabular): days left in Next deadlines, KPI cells. Ink by default, deep lilac when urgent.
- **Numeral Inline** (Bahnschrift 700, 14px): deadline dates in rows and tables.
- **Numeral Small** (Bahnschrift 700, 12px): tab counts, module notes, due figures, rank markers.
- **Headline** (700, 15px): section headings inside full tabs.
- **Title** (700, 13px): module header titles, tab labels, buttons.
- **Body** (400, 13px, line-height 1.45): the page default; inside the mosaic it tightens to 12.5px / 1.3.
- **Label** (700, 12px): field labels, table heads, module sub-headers.
- **Tag** (700, 11px, line-height 1.3; pills 12px): status, fee and draft tags.

### Named Rules
**The Price Figure Rule.** Every figure the applicant scans (days left, counts, dates, word counts) is set in the numeral face at 700 with tabular figures (`font-variant-numeric: tabular-nums` is on `body`). Words never use the numeral face.

**The Two-Step Size Rule.** Body copy lives between 11px and 15px. Size contrast comes from the 30px numerals, not from big headings.

## Layout

A centered column (max 1560px; padding 12px 20px 60px) under a lilac top bar and a sticky one-row tab strip. The Overview is a 12-column CSS grid with 8px gaps; modules span 3, 4, 6, 8 or 12 columns, and `.stack` columns hold several modules vertically with the same 8px gap. Full tabs use auto-fill grids (`cards` at min 320px, `form-grid` at min 250px, `details` at min 260px) and a 300px + fluid split for list/detail.

Rows are dense: list rows pad 4 to 5px vertically and 10px horizontally, table cells 5px 8px. Every list line stays on one line and ends in an ellipsis before its figure column. The deadline row is a four-column grid (62px days, fluid title, 74px date, tags).

Responsive: at 1180px, 3/4/8-column modules widen to 6 and 6-column modules go full width; the profile line hides. At 760px the mosaic collapses to one column, the search field and meta drop to their own rows, deadline rows become days + stacked content, table columns 3 and 4 hide, and forms go single column.

**The Above-the-Fold Rule.** On a desktop viewport the Overview shows deadlines, needs, pipeline/fit, documents and drafts without scrolling. A new module earns its place by being scannable at this density.

## Elevation & Depth

Completely flat. There are no shadows anywhere in the build. Depth is carried by tone and line: lilac header bars over white bodies, a 1px Rule border around every module, a 2px black rule under the top bar, and a module border that darkens to ink on hover (160ms, `cubic-bezier(.16, 1, .3, 1)`). The only layered element is the toast, an ink block that slides up 8px and fades in.

**The Hairline-Not-Shadow Rule.** Separation is a 1px line or a tone step, never a shadow or blur.

## Shapes

Nearly square. Modules, cards, buttons, inputs and tags take a 2px corner; tabs, KPI cells, rank markers and deadline rows are square. Borders are 1px solid for containers, 1px dotted for row separators inside lists, and 1px dashed only for empty states and the upload dropzone. The module header's black tab is a 5px-wide full-height bar at its left edge.

## Components

### Buttons
Compact and square-shouldered.
- **Shape:** 2px corners, 1px Rule border, 600 weight 13px, 7px 12px padding, optional 15px stroke icon with a 6px gap.
- **Primary (in pages):** Deep Lilac fill and border, white text; hover to Pressed Lilac.
- **Primary (top bar):** black fill, white text; hover to `on-lilac-accent`. Used for "Add link".
- **Top bar default:** transparent with a black border and black text on the lilac field.
- **Default:** panel fill, ink text; hover darkens the border to ink.
- **Ghost / Link / Danger:** ghost is transparent; link buttons are borderless ink text that turns Deep Lilac and underlines on hover; danger is Deep Lilac text.
- **Focus:** a 2px Deep Lilac outline offset 2px on every focusable element.
- **Disabled:** 45% opacity.

### Tags (chips and pills)
The tag grammar is the system's vocabulary: **outlined = state, black filled = decided, deep lilac filled = urgent.**
- **State (outlined):** panel fill with a 1px outline in the text colour: ink (Eligible, No fee, Read), deep lilac (Check details, Application fee, Changes asked), soft ink (Preparing, Draft), mute (Opens soon, Near miss), or neutral Rule grey (Fee unknown).
- **Decided (ink filled):** Shortlisted, Submitted, Closed, Approved.
- **Urgent (deep lilac filled):** Needs you, Awaiting your OK, Apply yourself, Not eligible, Rejected, Start now, Needed, NEW.
- Chips are 11px; pills (status) are 12px with 7px side padding.

### Modules
- **Corner Style:** 2px. **Background:** panel. **Border:** 1px Rule, ink on hover.
- **Header:** 32px min-height Lilac Mist bar with a 5px black left tab, a 13px bold title, an optional deep-lilac numeral note, and a right-aligned "View all" link with an SVG chevron.
- **Body:** zero padding; rows bring their own 10px side padding. Sub-headers are Lilac Wash strips with hairlines above and below.
- **Empty:** a muted line at 14px 10px padding.

### Deadline Row (signature)
Days left set like a price: a 30px Bahnschrift figure right-aligned in a 62px column with "days" under it in muted 11px, deep lilac when 30 days or fewer. Then a bold one-line title with a muted sponsor/country line, the date in numeral face, and status plus fee tags. Rows are full-width buttons separated by dotted rules, Row Tint on hover.

### Needs You list and rank markers
A numbered checklist: a 20px square ink marker with a white numeral (the first marker is deep lilac), a one-line action naming the application, and a right-aligned numeral figure, deep lilac when late.

### KPI cells
Four equal cells divided by hairlines inside a module: a 30px numeral over a 12px muted label; the numeral turns deep lilac for an urgent nonzero count. Cells are buttons that open the matching tab.

### Inputs / Fields
- **Style:** 1px Rule border, 2px corners, panel fill, 6px 9px padding, inherited 13px type.
- **Focus:** border goes to ink; no glow. The search field takes the same treatment on `:focus-within`.
- **Labels:** 12px bold Soft Ink above the field. **Errors:** 12px Deep Lilac, 600.

### Navigation
- **Top bar:** a Lilac field holding the black wordmark, search (max 560px, white), a two-line meta block (profile %, daily-check status) in fixed dark text, Refresh (outlined black) and Add link (black); closed by a 2px black rule.
- **Tabs:** a sticky Lilac Mist strip of square tabs divided by 1px rules, 600 13px, each with a deep-lilac numeral count. The active tab fills black with white text and a lilac count. The strip scrolls horizontally on small screens.

### Tables
Full-width grid with Lilac Wash heads (12px bold), hairline row rules, Row Tint hover, an expandable detail row, and a lilac-wash flash that fades over 1.6s after an update.

### Icons
A small inline SVG set drawn in code (external, chevron, check, x, question, star): 24-unit viewBox at 15px, 1.9 stroke, round caps and joins, `currentColor`.

## Do's and Don'ts

### Do:
- **Do** put every new block of information in a module: Lilac Mist bar, black left tab, title, optional deep-lilac numeral note, "View all" link.
- **Do** set every scannable figure in the numeral face (Bahnschrift / DIN Alternate) at 700 with tabular figures.
- **Do** express status with the tag grammar: outlined for a state, ink filled for decided, deep lilac filled for urgent.
- **Do** keep rows on one line with an ellipsis before the figure column, separated by 1px dotted rules.
- **Do** define every colour as a token on `:root`; there is one (light) theme.
- **Do** keep fonts to system stacks and all styles in `styles.css` (CSP `default-src 'self'`, no inline styles, no build step).

### Don't:
- **Don't** introduce any hue beyond lilac, white and black (red, green, blue, ochre are retired).
- **Don't** put white text on light lilac; lilac fields always carry black text.
- **Don't** add a dark theme or follow the system's dark mode; the background stays white (the user's choice, 2026-11-12).
- **Don't** add shadows, blur or floating cards; separation is hairlines and tone.
- **Don't** load external or self-hosted web fonts; the user declined them on 2026-11-12.
- **Don't** spread the Overview into airy stat cards with large padding; the mosaic is meant to be packed.
- **Don't** round corners beyond 2px.

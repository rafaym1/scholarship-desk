---
version: 1
slug: "dashboard-index-html"
primary_target: "dashboard/index.html"
related_targets: ["dashboard/app.js","dashboard/styles.css"]
---

# Dashboard surface brief

Scope: the whole local dashboard (`dashboard/index.html`, `app.js`, `styles.css`). Mode: Operate.
Audience: applicants running Scholarship Desk locally with Claude Code. Job: see everything at once
(deadlines, what needs them, pipeline, fit, documents, drafts) and act: upload, edit profile,
approve drafts, shortlist, copy `/apply`. Constraints: CSP `default-src 'self'` (no external fonts,
no inline styles), DOM via textContent, every existing feature kept.

## Direction contract

THESIS: Everything the applicant must know and do, on one screen, as a packed mosaic of
hairline-ruled modules. It refuses the airy SaaS shell of stat cards and padding, and the old grey
admin table.

OWN-WORLD:
- Palette: lilac, white and black only. This was the user's choice on 2026-11-12 and replaced
  the original utility red.
- Ground and lines: white ground, ink #111, and 1px hairlines in #E7E3EE / #D5CFE0.
- Lilac fields carry black text: the top bar in lilac #C8A8E9, and the tab strip and module header
  bars in lilac mist #E6D9F7.
- Deep lilac (#6A3FA8) is the only accent. It marks urgent days-left figures, counts and notes,
  urgent and "NEW" tags, primary buttons inside pages, and focus.
- Modules: each is a rectangle with a lilac-mist header bar, a 5px black tab at its left edge and
  "View all ›" at the right.
- Type: a compact gothic sans at 12–13px with tight leading. Numerals are heavy and tabular, set
  like prices.
- Tags: outlined for a state, black filled for decided, deep lilac filled for urgent.
- Fonts: system stacks only. The user declined self-hosting a font on 2026-11-12. Text uses the
  platform UI sans; numerals use the platform's DIN-style face (Bahnschrift / DIN Alternate).

STORY: Opening the desk shows, without scrolling: the next deadlines with days left, what needs
the applicant, pipeline and fit, documents, drafts, what's coming up, and the full list. They see
where they stand, act on the top item, and open a tab for detail.

FIRST VIEWPORT:
- Lilac top bar: the black wordmark ("Desk" in deep purple), a white search field that filters
  opportunities, profile % and daily-check status, and a black "Add link" button.
- Under it: a lilac-mist tab strip with counts. Overview is the default and is filled black when
  active.
- A 12-column mosaic:
  - Next deadlines (6 columns): big days-left figures, deep lilac when urgent.
  - Needs you (3 columns): concrete actions, each naming its application.
  - Pipeline/Fit and newly found (3 columns).
  - Documents (4 columns) beside a stacked Drafts and Coming up (8 columns).
  - All opportunities (12 columns).
- Signature move: days-left set like the world's price figure, heavy tabular numerals anchoring
  each row.

FORM: challenger `japanese-high-density-web`, which the user chose over the assigned Prospectus
Index (not on the grounded list). seed:ab41c36ee743b8e1

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Prospective graduate students applying for **funded master's and PhD places abroad** (scholarships,
funding that comes with admission, salaried PhD positions) who use Claude Code on their own
computer. The first users are the author and a friend. The project
will be open-sourced so that anyone with Claude Code can run it locally with their own data.
Each person runs their own copy; nothing is shared between users.

They use the dashboard in a desktop browser at `127.0.0.1`, a few times a week and daily near
deadlines, while Claude Code does the searching, writing and form-filling in the background.

## Product Purpose

Scholarship Desk finds funded opportunities in Europe, North America, Australia and the Nordics,
checks the applicant's eligibility (including citizenship and residence rules), plans backwards
from deadlines, drafts tailored answers from the applicant's own documents, applies through a
supervised browser agent, and tracks outcomes.

Success: more strong, eligible applications submitted on time, no missed deadlines, no wasted
applications to things the person can't win, and no cost beyond their existing Claude plan.

## Positioning

- Runs on the user's own Claude subscription plus deterministic local Python. There are no API
  costs and no hosted service.
- Eligibility is strict and explained: country rules are copied from the sponsor, and unknowns
  are labelled rather than guessed.
- Only official sources count as verified. Listing sites are only leads.
- A supervised agent fills the real portals. The person keeps logins, payments, ID uploads and the
  final "submit" decision.
- Everything stays on the person's machine.

## Operating Context

- **Dashboard:** a local web page served by `python -m scholar serve` (stdlib HTTP server).
- **Sections today:** Opportunities (with a next-deadlines strip), Apply yourself, This week,
  Near misses, Profile (edit every detail), Documents (upload), Drafts (approve or edit answers),
  Submitted (outcomes), Supervisors (outreach status), Add link.
- **Claude Code skills:** `/profile`, `/ingest`, `/discover`, `/recon`, `/tailor`, `/apply`,
  `/outreach`. A daily watcher diffs official pages for free.
- **Working rhythm:** check the next deadlines, upload documents, approve drafts, shortlist, then
  run `/apply` in Claude.

## Capabilities and Constraints

- **Web first, chat optional:** everything the person provides (profile details, documents,
  draft approvals, links, decisions) can be done in the dashboard or in chat, and both write the
  same local files.
- **No browser control from the page:** the dashboard cannot operate a browser. Claude does the
  applying, and approval to submit is given in Claude, per application.
- **Hard technical constraints:**
  - Content-Security-Policy `default-src 'self'`: no inline styles or scripts, and no external
    fonts, CDNs or images. Fonts must be local files or system stacks.
  - The DOM is built with `textContent`.
  - Write requests need a custom header and same origin.
  - The server listens on localhost only.
  - Plain HTML/CSS/JS with no build step.
- **Private folders, never committed:** `data/`, `documents/` and `submitted/`. The repository
  must never ship personal data.
- **Terminology:** opportunity, deadline, "start by" date, eligible / check details / near miss /
  not eligible, application fee / no fee, shortlist, draft, submit.

## Brand Commitments

Name: **Scholarship Desk**. No other identity assets exist yet.

## Evidence on Hand

- Real opportunity records, profile and documents exist only in each user's private `data/`.
- There are no testimonials, user counts or institutional endorsements. Don't invent any.

## Product Principles

1. **Truth over hope:** show eligibility, fees and uncertainty plainly. A clear "not eligible" beats
   a hopeful maybe.
2. **Deadlines drive everything:** the next dates and the actions they require come first.
3. **The person stays in control:** approvals, logins, payments and submission are theirs, and the
   interface makes that visible.
4. **Web first, chat optional:** anything Claude can be told in chat can also be done on the page.
5. **Local and free:** nothing leaves the machine except into the portal being filled, and nothing
   costs more than the user's Claude plan.

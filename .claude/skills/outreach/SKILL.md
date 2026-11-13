---
name: outreach
description: Find supervisors whose current research matches the applicant (PhD and research master's — mainly Canada, Australia, UK, and anywhere a supervisor must agree first) and draft short, specific emails for the applicant to send. Use "/outreach" or "/outreach <opportunity id>".
---

# Supervisor outreach

Read `CLAUDE.md` first. Quality over volume: a few well-matched emails a week.

1. Gather: `python -m scholar profile show --section target`, `python -m scholar library facts --tag research`,
   and the opportunity (`opp show <id>`) if one is given.
2. Find candidates on **official** university pages (faculty/lab pages). For each, check: recent work
   (last ~3 years) that genuinely connects to the applicant's interests and experience, whether they say
   they're taking students, and any funding route mentioned.
3. Record them — `data/tmp/supervisors.json`:
   `[{"name": "...", "institution": "...", "country": "...", "email": "<from the official page only>",
   "profile_url": "https://<official page>", "match": "2–3 sentences: which papers/projects and how they
   connect to the applicant's specific experience", "opp_id": null}]`
   → `python -m scholar outreach add data/tmp/supervisors.json`.
4. Draft each email in `data/outreach/<contact id>.md`: a specific subject line and at most ~200 words —
   who the applicant is (one line), the concrete connection to one or two of the supervisor's recent
   works, two facts from the bank showing fit, the ask (are they taking students for <term>, and the usual
   funding route), and that a CV is attached. No flattery templates.
   `python -m scholar outreach update <contact id> drafted --draft data/outreach/<contact id>.md`
5. Show the drafts. The applicant sends them from their own email. Only if they ask you to send through a
   connected email tool: show the exact recipient and text and get a yes for each email.
   After sending: `python -m scholar outreach update <contact id> sent`.
6. The CLI warns after 5 sends in a week. Suggest one polite follow-up after about two weeks, no more.
   Record replies with `outreach update <id> replied_positive|replied_negative|no_reply`.

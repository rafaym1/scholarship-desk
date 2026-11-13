---
name: profile
description: Interview the applicant and save their profile — targets, citizenships and residence history, identity/contact for forms, education, tests, experience, referees, narrative in their own words, and documents (all CV variants). Use for first-time setup or whenever details change.
---

# Profile interview

Goal: an accurate, complete profile so eligibility checks and applications never rely on guesses.
Read `CLAUDE.md` (non-negotiables) first.

## Start

1. `python -m scholar profile status` — show the completeness percentage and what is missing.
   If the profile already exists, ask only about missing fields and anything that changed.
   Mention once that every answer can also be typed into the dashboard's **Profile** tab
   (and files dropped into the **Documents** tab) if they prefer the web to chat.
2. Tell the applicant once: answers are stored only on this PC in `data/profile.json`; what they
   type here also goes to Claude as part of the conversation.

## Ask in batches (one message per batch, wait for the reply)

**A. What you're applying for** — levels (`masters`, `phd`), fields of study, research/topic
keywords, regions (`europe`, `north_america`, `australia`, `scandinavia`; default all four),
intended start (YYYY-MM), universities in mind, countries to avoid, fully funded only?

**B. Citizenship and residence** (drives country eligibility) — every citizenship held; country of
residence now and status there (citizen, permanent_resident, study_permit, work_permit, …);
where they've lived over the last 5+ years (country, from, to); country of birth. Explain that some
awards exclude people who already live in the host country, and some treat dual citizens specially.

**C. Identity and contact for forms** — legal given/middle/family names exactly as in the passport,
preferred name, date of birth, email for applications, phone with country code, mailing address.

**D. Education** — each degree: institution, country, degree name, field, start/end, status,
GPA and scale, grade as written on the transcript, honours, thesis title, supervisor,
language of instruction.

**E. Tests** — IELTS/TOEFL/PTE/Duolingo/GRE/GMAT: exact exam name, overall score, date, expiry.

**F. Experience, publications, awards, activities, languages.**

**G. Referees** — name, title, institution, email, relationship, what they can speak to, and whether
they've agreed to write. Entering a referee in a portal often emails them immediately.

**H. Narrative bank (their words)** — motivation, career goals, research experience/ideas, leadership,
a challenge overcome, impact on community/home country. Ask them to write or paste; do not write it
for them. They can skip this if their past essays will be ingested.

**I. Consent** — ask exactly: "May I include your nationality in web searches to find
country-specific scholarships? The search engine will see those queries." Save as
`consent.identity_search` yes/no.

**J. Documents** — ask them to put files in `documents/` (CVs, transcripts, degree certificates,
language certificates, past essays/statements, research proposal, writing samples). Register each:

```
python -m scholar profile doc-add cv "documents/CV - research.pdf" --label "CV - research focus"
python -m scholar profile doc-add cv "documents/CV - industry.pdf" --label "CV - industry focus"
python -m scholar profile doc-add transcript "documents/BSc transcript.pdf"
python -m scholar profile doc-add writing_sample "documents/Chevening essays 2025.docx" --label "Past essays"
```

Register every CV variant as type `cv` with a distinct label. A passport scan is type
`passport_scan`; the applicant uploads it to portals themselves.

## Saving

```
python -m scholar profile keys [identity|target|narrative|consent|lists]   # valid keys and choices
python -m scholar profile set identity.citizenships "Pakistan; Canada"
python -m scholar profile set target.levels "masters, phd"
python -m scholar profile list-add residence country=Canada from=2024-08 status=study_permit
python -m scholar profile list-add education institution="..." degree="BSc Computer Science" status=completed end=2024-05 gpa=3.6 gpa_scale=4
python -m scholar profile list-add tests exam="IELTS Academic" score=7.5 date=2025-03-02 expires=2027-03-02
python -m scholar profile list-update education 1 honours="Dean's list"
python -m scholar profile skip identity.gender
```

- Copy values exactly as given. Ask when unclear (weighted or unweighted GPA? IELTS Academic or General?).
- Use country names, not nationalities ("Pakistan", not "Pakistani"); the CLI suggests fixes.
- If a result says `NOT SAVED`, explain the reason and ask again.
- Never store passwords, SIN/SSN, passport or national-ID numbers, bank or card details. If offered,
  say they'll type those into forms themselves.
- Long text (narrative) with quotes or newlines: write it to `data/tmp/<key>.txt` and pass it with
  `python -m scholar profile set narrative.motivation "$(cat data/tmp/motivation.txt)"`, or keep it
  short and set directly.
- After each batch, confirm briefly what was saved (not every value).

## Finish

`python -m scholar profile status`, then tell them the next steps: `/ingest` (reads their documents),
then `/discover`, and open the dashboard (`python -m scholar serve --open`, `python3` on Mac/Linux, or the
Scholarship Desk desktop shortcut on Windows).

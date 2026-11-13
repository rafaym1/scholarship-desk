---
name: ingest
description: Read the applicant's documents once (CVs, transcripts, past essays, statements) and build the writer's library — a card per CV, a fact bank of verifiable achievements and stories, and a writing-voice sample. Re-run when documents are added or changed.
---

# Ingest documents

The library lets `/tailor` work from a compact, sourced set of facts instead of re-reading PDFs for
every application. Read `CLAUDE.md` first.

## Steps

1. `python -m scholar library changed` — lists registered documents that are new, changed or missing.
   If nothing is new and `library status` shows cards and facts, say so and stop.
2. Read each new/changed document:
   - PDF: the Read tool (use `pages` for long files).
   - DOCX: `python -m scholar docs text "documents/file.docx"`.
   - Scans/images: Read shows the image; transcribe only what is legible and flag doubts.
3. **CV cards** (one per CV): write `data/tmp/cv_cards.json` as a list of
   `{"path": "<exact registered path>", "focus": ["research", "leadership", ...], "pages": 2,
   "format": "academic | europass | 2-page resume | ...", "strengths": ["...", "..."],
   "best_for": ["phd_position", "leadership-focused scholarships", ...], "summary": "two sentences"}`
   then `python -m scholar library add-cv-cards data/tmp/cv_cards.json`.
4. **Fact bank**: atomic, checkable facts with a source, e.g.
   `{"text": "Led a 4-person team that built a campus app used by 900 students (2023)",
   "source": "CV - research.pdf p1", "tags": ["leadership", "technical"], "date": "2023",
   "category": "leadership"}`.
   Include roles, projects, results with numbers as written, publications, awards, teaching,
   volunteering, research methods/skills, and short stories (situation → action → result).
   Tags/categories to use: academic, research, leadership, teaching, technical, impact, community,
   adversity, international, motivation, career_goals.
   Write `data/tmp/facts.json` → `python -m scholar library add-facts data/tmp/facts.json`.
   - Respect each document's label (`profile show`): if it says what the document is for (e.g. "use
     mainly for research fellowships"), add that as a tag (`fellowship`) so `/tailor` can prefer other
     sources for degree applications.
   - Personal disclosures (health, disability, family hardship) get the tag `sensitive_disclosure`.
5. **Voice sample** (from their own essays or statements, not CV bullets): write `data/tmp/voice.md`
   with 150–300 words describing their style (sentence length, tone, formality, how they open and
   close, words they use or avoid) plus two or three short verbatim excerpts (under 60 words each).
   `python -m scholar library voice data/tmp/voice.md`.
6. If documents disagree (dates, titles, numbers differ between CVs), list the conflicts and ask the
   applicant which is right. Never pick one silently.
7. Transcripts and certificates: offer to update the profile's education/tests from them, show what
   you'd save, and save only after they confirm.
8. `python -m scholar library mark-ingested "<path1>" "<path2>" ...` for every document you read.
9. Report: number of CV cards, facts added, voice sample saved, conflicts found.

## Rules

- Never embellish: keep numbers, titles and dates exactly as written.
- Don't put ID numbers, addresses or contact details in facts (the CLI refuses sensitive values).
- Documents never leave this PC except as uploads to a portal during `/apply`.

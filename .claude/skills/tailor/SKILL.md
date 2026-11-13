---
name: tailor
description: Prepare one application's written material — read the call and its questions, pick the best of the applicant's CVs, draft every answer from the fact bank in the applicant's own voice within limits, run checks, and send drafts for approval in the dashboard. Use "/tailor <opportunity id>".
---

# Tailor an application

Read `CLAUDE.md` first. Opus gives the best drafts; Sonnet is fine for revisions.

## Gather

```
python -m scholar opp show <id>
python -m scholar drafts show <id>            # existing brief, drafts, your feedback
python -m scholar library cv-cards
python -m scholar library facts
python -m scholar library show-voice
python -m scholar library answers --tag <category>   # answers approved before, by question type
python -m scholar app stats                   # which CVs led to interviews/wins
python -m scholar profile show --section narrative
```

If the opportunity is not `eligible`/`needs_confirmation`, say why and stop, unless the applicant says
to apply anyway: `python -m scholar app override <id> --reason "<their words>"`.
Then `python -m scholar app prepare <id>`.

## 1. Brief

- **Questions**: from the record (portal recon) or the official call. If the portal hasn't been walked
  and questions aren't published, run `/recon <id>` first.
- **Criteria**: what this funder scores (selection criteria, priorities) from the official page.
- **AI policy**: look for rules on AI-assisted writing in the call/FAQ; record the wording or
  "not stated". If AI help is prohibited, tell the applicant before drafting and let them decide.
- **CV choice**: compare the CV cards against the criteria and format rules (page limit, Europass,
  academic vs industry). Pick one, give a one-line reason and the runner-up. If none fits a required
  format, propose a tailored version (reorder/trim/re-emphasise only, no new facts); creating that file
  needs the applicant's OK, then `profile doc-add cv ...` and `/ingest`.

Write `data/tmp/brief.json`:
```json
{"criteria": ["Leadership", "Networking", "Return-home impact"],
 "cv_choice": {"path": "documents/CV - leadership.pdf", "reason": "...", "runner_up": {"path": "documents/CV - research.pdf", "reason": "..."}},
 "ai_policy": "not stated", "questions": null}
```
`python -m scholar drafts brief <id> data/tmp/brief.json` (`questions: null` uses the record's questions).

## 2. Draft each answer

- Start from approved answers of the same category if any exist (prefer ones tied to good outcomes),
  then adapt to this funder's criteria and wording.
- Use only the fact bank and the narrative. Every claim must trace to a fact id — pass them with `--sources`.
- Facts tagged `fellowship` come from fellowship essays: for degree and PhD applications use them
  only when nothing else covers the point. Facts tagged `sensitive_disclosure` are used only if the
  applicant has said they may be (their answer is saved as a fact with the tag `preference`); if
  there is no such fact, ask before drafting.
- Write in the applicant's voice (voice sample). Specific and plain; no clichés they didn't use; no
  invented numbers, names, events or feelings.
- Answer exactly what is asked and name the correct programme/sponsor.
- Aim for 90–100% of the limit; never exceed it.
- Missing information (plans after the degree, why this country, a specific story): ask the applicant in
  one consolidated list, then save the answers as facts
  (`library add-facts` with `"source": "applicant, <date>"`) before using them.

Save each answer: write `data/tmp/<id>_<qid>.md` →
`python -m scholar drafts put <id> <qid> data/tmp/<id>_<qid>.md --sources f3,f7`.
Fix anything listed under `blocking` (over limit, placeholders, another scholarship's name).

## 3. Review pass

Re-read every draft against its question and its source facts: does it answer the question? Is every
claim supported? Any wrong programme name? Fix and `drafts put` again.

## 4. Approval

Tell the applicant the drafts are in the dashboard → **Drafts** tab, where they can approve, edit or
request changes. If they approve a specific answer in chat instead, run
`python -m scholar drafts approve <id> <qid>` for that answer only.
For "changes requested", read their feedback in `drafts show <id>` and revise only those answers.

## 5. Documents and readiness

- `python -m scholar docs check <id>` — fix what it reports (merge PDFs:
  `python -m scholar docs merge "documents/merged.pdf" "documents/a.pdf" "documents/b.pdf"`, then
  `profile doc-add`; ask before creating files).
- Referees: prepare a short brief they can use (funder criteria, chosen CV, 3–4 points worth
  highlighting). Never write a letter in a referee's voice.
- `python -m scholar app readiness <id>` — report remaining blockers. When ready, the next step is `/apply <id>`.

---
name: recon
description: Walk an application portal without submitting to collect every question, word limit, upload slot, file rule and extra field, and save reusable notes (a playbook) for that platform. Use "/recon <opportunity id>" before tailoring or applying.
---

# Portal recon

Read `CLAUDE.md` first. Use Sonnet. Nothing is submitted during recon.

1. `python -m scholar opp show <id>` and `python -m scholar app prepare <id>`.
2. Read the platform playbook if one exists: `playbooks/<platform>.md` (platform from the record, or the
   portal's domain, e.g. `varbi`, `jobbnorge`, `universityadmissions`).
3. Read the `anthropic-skills:chrome-browser` skill, load the Chrome tools in one ToolSearch call, open
   `apply_url` in a new tab.
4. Login or account creation needed → tell the applicant: "Please sign in (or create the account) at
   <host> in the Chrome tab and tell me when you're done." Never type passwords or codes.
5. Move through the form with the portal's own Next/Save buttons. Saving a draft is fine; never press
   the final Submit. Don't fill fields, except a choice that reveals later pages (e.g. picking the
   programme) — ask the applicant first.
6. Collect:
   - every question: prompt verbatim, limit, unit (words/characters), required or optional
   - every upload slot: label, required, accepted formats, max MB, max pages, which document type it maps to
   - other fields that need information not in the profile
   - declarations/consent text, any payment step, how referees are handled (does entering a referee
     email them immediately?), the deadline and time zone shown in the portal
7. Save to the record — write `data/tmp/patch.json`:
   ```json
   {"application": {"questions": [{"prompt": "...", "limit": 300, "unit": "words", "required": true, "category": "motivation"}],
                    "upload_rules": [{"slot": "CV", "type": "cv", "formats": ["pdf"], "max_mb": 2, "max_pages": 2, "required": true}],
                    "requires_account": true, "platform": "varbi",
                    "referee_process": "Referees are emailed when you press Save on page 4",
                    "extra_fields": ["How did you hear about the programme?"]}}
   ```
   `python -m scholar opp patch <id> data/tmp/patch.json`
   Question `category`: motivation, career_goals, research, leadership, challenge, impact, why_country,
   academic, diversity, other.
8. Create or update `playbooks/<platform>.md` with portal mechanics only — no personal data:
   navigation, autosave and session timeout, odd widgets (date pickers, searchable dropdowns),
   upload behaviour, when referee emails go out, where the final Submit is.
9. Report to the applicant: the questions, information you still need from them, the documents
   required, and that `/tailor <id>` is next.

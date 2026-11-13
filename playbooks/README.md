# Portal playbooks

One file per application platform (`varbi.md`, `jobbnorge.md`, `universityadmissions.md`,
`chevening.md`, ...). `/recon` and `/apply` read the file before using a portal and update it
afterwards, so each later application on the same platform is faster and fails less.

Write portal mechanics only — never personal data:

- how to move between pages; whether it autosaves; session timeout
- unusual widgets (date pickers, searchable dropdowns, rich-text boxes that count characters differently)
- upload behaviour (size limits, one file per slot, PDF only)
- when referee emails are sent
- where the final Submit button is, and what the confirmation looks like

These files are shared through git, so a friend using the same project benefits too.

---
name: job-status
description: Track job applications in data/applications.md. Use when the user reports application progress ("applied to X", "X invited me to a tech interview on 18.09", "X rejected me", "withdraw from X") or asks about the pipeline or status of applications.
---

# Job status

Files in the project folder (the one holding `fetch.py`): `data/applications.md` (one row per application), `data/jobs.yaml` (offers found by /job-search).

IDs: every offer in `data/jobs.yaml` has a numeric `ref`, written as `#42`. The user may refer to an offer as `#42` or `42`.

Statuses, in pipeline order: `applied`, `first-interview`, `tech-interview`, `final`, `offer`, `screening`, then closed: `rejected`, `withdrawn`, `no-response`.
- `first-interview` - first proper conversation about experience and expectations, no coding ("intro call", "HR interview", "call with the manager")
- `tech-interview` - technical round: live coding, system design, deep technical questions
- `final` - last interview round, for example with the hiring manager or a director
- `offer` - offer received or being negotiated
- `screening` - background and reference vetting after the offer (employment history, criminal record, credit checks); the last step before signing, common in fintech and trading
A call described without its content is a `first-interview`; call it `tech-interview` only when the user says it is technical.
Dates: `YYYY-MM-DD`.

## Update (argument given)
1. Find the offer: ID in the `data/applications.md` ID column or `ref` in `data/jobs.yaml`, otherwise company or role in `data/applications.md`, otherwise company, title or url in `data/jobs.yaml`. Several matches or none: ask.
2. New application: add a row. ID (`#` + `ref`), Company, Role, Link, Source, Contract/salary from `data/jobs.yaml`; Updated = today; Set `decision: applied` for that offer in `data/jobs.yaml`. Offer not in `data/jobs.yaml`: ask for the link, fill in what is known, leave ID empty.
   - The user reports an application: Status `applied`, Applied = today.
   - The user reports a later stage first ("Acme invited me to an interview"): Status is that stage, Next step holds the date given, and Applied is the date they say they applied - ask for it, and leave the cell empty if they do not remember. Never invent it.
3. Existing row: set Status, Updated = today, Next step (for example `tech interview 2026-09-18`), Notes when given. Keep the Applied date.
4. Confirm in one line, starting with the ID.

## Pipeline (no argument)
- Every row shows its ID
- Rows grouped by status: active first (screening, offer, final, tech-interview, first-interview, applied), then closed (rejected, withdrawn, no-response)
- Upcoming next steps with dates, soonest first
- Stale: `applied` with Updated older than 14 days - suggest a follow-up or `no-response`. Never call `screening` stale; vetting takes weeks and the user cannot speed it up

## Rules
- Never apply, send messages or contact companies.
- `record.py` and the web UI lock `data/` before writing; editing these files here does not. If `python3 ui.py` is running, make the change in the UI instead, or ask the user to stop it first.
- Keep the table valid Markdown: escape `|` inside cells.

---
name: job-search
description: Search job boards for roles that match data/profile.md, score new offers against the user's CV and record them in data/jobs.yaml. Use when the user asks to "search jobs", "find offers", "any new positions", wants the current shortlist, or passes a job offer URL to score (for example from LinkedIn).
---

# Job search

Work in the project folder (the one holding `fetch.py`). Criteria: `data/profile.md`. Candidate facts: the CV file named by `cv:` in `data/config.yaml`.
Missing `data/config.yaml` or `data/profile.md`: run `/job-profile` first.
Scope: find and score only. No cover letters, no CV changes, never apply.
IDs: `record.py` gives every new offer a numeric `ref` in `data/jobs.yaml`, shown as `#42`. Always show the ID when mentioning an offer; the user may refer to offers by `#42` or `42`.

## Board run (no argument)
1. `python3 fetch.py` - pulls the boards enabled in `data/config.yaml`, drops offers already in `data/jobs.yaml`, writes the rest to `data/inbox.jsonl` sorted by keyword fit (`kw`). Report the per-source counts and any `ERROR` lines.
2. Read `data/profile.md` and the CV once.
3. Read `data/inbox.jsonl` in batches of 100 lines (Read with offset/limit) and score every offer with the rubric below. Use title, skills, languages, location, salary and excerpt. WebFetch an offer page only when a likely 7+ offer has no skills or requirements listed; at most 15 fetches per run. Steps 4-5 run once per batch, so progress is saved.
4. Write `data/scores.jsonl`, one JSON object per line: `{"id": "...", "score": 8, "why": ["..."], "gaps": ["..."], "decision": "shortlist"}`.
   - `decision`: `shortlist` when the score reaches `scoring.shortlist_score` from `data/config.yaml` (default 7), `recheck` when the offer was scored on partial information, otherwise `skip`
   - skip: one short reason in `why`, `gaps` may be empty
   - shortlist: 2-3 `why` bullets, `gaps` = required skills the CV does not show
5. `python3 record.py data/scores.jsonl` - merges the batch into `data/jobs.yaml` and prints its shortlist rows. Continue with the next batch until it reports 0 unscored.
6. `python3 record.py --shortlist` and show that table. Nothing else unless asked.

## Single offer (URL argument)
1. Offer already in `data/jobs.yaml` (same url): show its ID and stored score, do not rescore unless asked. Rescoring one keeps its existing id from `data/jobs.yaml` - never mint a second `manual/...` record for an offer that already has one.
2. WebFetch the URL. LinkedIn authwall or any failure: ask the user to paste the offer text.
3. Score it. Write one line to `data/scores.jsonl` with extra fields `title`, `company`, `url`, `source` (board name or `linkedin`), `location`, `salary`, `skills`, `languages`. Id for an offer not yet stored: `manual/<company>-<title>-<last path segment or numeric id from the url>` in lowercase kebab-case, so two openings with the same title at one company stay separate records.
4. `python3 record.py data/scores.jsonl` and show the result.

## Current shortlist
`python3 record.py --shortlist`

## Rubric
- 9-10: the target role from `data/profile.md`, location fits, nearly all required skills shown in the CV, strong-fit domain or stack
- 7-8: good fit with 1-2 gaps, or location/contract details unclear but likely fine
- 4-6: partial fit - several stack gaps, weak-fit items, unclear level
- 1-3: any deal-breaker from `data/profile.md`

## Rules
- Never count a skill the CV does not show; list it in `gaps`.
- `excerpt` in the inbox is the first 500 characters of the description, so a requirement can be out of sight. Score only what is visible. When a promising offer rests on an unread requirement and the 15-fetch budget is gone, score it as it stands, set `decision: recheck` and say in `why` what is missing. `python3 record.py --recheck` lists them; offer to fetch those pages at the start of the next run, because `fetch.py` will not show them again.
- One `/job-search` at a time: `data/scores.jsonl` and `data/inbox.jsonl` are single shared files, and a second session or a parallel `fetch.py` overwrites the batch being scored.
- Languages: a required language outside `languages.accepted` in `data/config.yaml` is a deal-breaker.
- On Polish boards (justjoin.it, nofluffjobs) `remote` usually means remote within Poland.

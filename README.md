# job-hunt

A job search that runs on your laptop. Three small Python scripts pull offers from public job boards, Claude Code scores each one against your CV, and a local web UI lets you review the shortlist and track applications.

Everything is plain files in one folder: no account, no database, no service to sign up for. The offers and your notes stay on disk; the job boards see the fetch requests, and whatever Claude Code reads - your CV, the offers, your profile - goes to Anthropic like any other Claude conversation.

It does **not** write cover letters, change your CV, or apply anywhere. It finds, scores and tracks.

## What you get

- `/job-profile` - reads your CV and writes your search criteria
- `/cv-review` - reviews that CV like a recruiter and like an ATS parser, scores it, lists what to fix
- `/job-search` - fetches new offers, scores them 1-10 against your CV, prints the shortlist
- `/job-status` - keeps a table of where every application stands
- `python3 ui.py` - a local web page to review offers and update applications without typing

## Quick start

**Before you start**

- Python 3 - check with `python3 --version`. Missing on Windows: [python.org/downloads](https://www.python.org/downloads/), tick **Add python.exe to PATH** in the installer. Linux: `sudo apt install python3 python3-pip`.
- [Claude Code](https://claude.com/claude-code), installed and logged in.
- Your CV as a file: `.pdf`, `.docx`, `.html`, `.md` or `.txt`.
- This project on your disk: green **Code** button → **Download ZIP** → unzip, or `git clone`.
- A terminal open inside that folder. Mac: right-click the folder → Services → **New Terminal at Folder**. Windows: click the address bar in the folder, type `cmd`, Enter. Linux: right-click → **Open in Terminal**.

**1. Install the one library it needs**

```bash
python3 -m pip install --user pyyaml
```

Windows: `py -m pip install --user pyyaml`. On Debian, Ubuntu or any distro that refuses to install into the system Python (`externally-managed-environment`), use a virtual environment instead:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml
```

Activate it (`source .venv/bin/activate`) in the terminal **before** starting `claude`, in every new terminal. The skills call plain `python3`, so an unactivated venv means the scripts run without PyYAML.

**2. Start Claude in that folder**

```bash
claude
```

Started anywhere else, the `/job-...` commands do not exist.

**3. Set up your search from your CV**

```
/job-profile /Users/you/Documents/cv.pdf
```

Type `/job-profile`, a space, then drag the CV file into the terminal window to paste its path. Claude reads it and asks what a CV does not say: city, remote or office, contract types, what you refuse to do. Answers go into a `data` folder.

**4. Find offers**

```
/job-search
```

Downloads what the boards published, drops what does not fit, grades the rest 1-10 against your CV. First run takes a few minutes and ends with a table. Every offer gets a number like `#42`.

**5. Review them in a browser**

Leave Claude with `/exit`, then (Windows: `py ui.py`):

```bash
python3 ui.py
```

Open http://127.0.0.1:8765. Click through the offers, mark interested or not, update applications. Ctrl+C in the terminal closes it.

**6. Every day after that**

Terminal in the folder, `claude`, then:

```
/job-search
/job-status applied to Acme
/job-status #42 tech interview 2026-10-02
/job-status
```

The last one shows where everything stands and what is going stale.

**Something breaks:** paste the error into Claude in the same window and ask.

## Setup, short version

```bash
git clone <this repo> job-hunt
cd job-hunt
python3 -m pip install --user pyyaml   # or a venv, see Quick start
claude
```

```
/job-profile ~/Documents/cv.pdf
```

Claude Code runs the scoring and the skills; `fetch.py` and `record.py` run without it. `/job-profile` writes:

| File | What it holds |
|---|---|
| `data/config.yaml` | The machine filters: which boards, which titles, which city, which languages, which timezones |
| `data/profile.md` | The human criteria Claude scores against: target role, deal-breakers, strong fit, weak fit |
| `data/applications.md` | An empty tracker table, only if you do not have one |

Prefer to do it by hand: `mkdir -p data && cp config.example.yaml data/config.yaml && cp profile.example.md data/profile.md`, then edit both.

`.claude/skills/job-profile/SKILL.md` documents every key in `config.yaml`: what fills it, which board reads it, and how its words are matched. Three matching rules are in play and they are easy to mix up:

| Rule | Keys | Behaviour |
|---|---|---|
| whole word | `role.*`, `location.remote_friendly`, `location.remote_excluded`, `scoring.strong_fit` | `us` does not match "USA", `java` does not match "javascript" |
| stem | `languages.excluded_word_stems` | substring anywhere, and title only: `niemieck` matches "niemieckim" |
| prefix | `location.city_prefixes` | start of the city name: `krak` matches Krakow and Kraków |

`remote_friendly` wins over `remote_excluded`: one friendly word is enough to keep an offer.

Start Claude from this folder, otherwise the project skills do not load.

## Daily use

| Command | What it does |
|---|---|
| `/cv-review` | Score the CV as a recruiter and an ATS would, with a ranked fix list |
| `/job-search` | Fetch new offers, score them, print the shortlist |
| `/job-search <url>` | Score a single offer (LinkedIn or any board) |
| `/job-status applied to <company>` | Add an application |
| `/job-status <company> tech interview 2026-09-18` | Update status and next step |
| `/job-status #42 rejected` | Same, referring to the offer by its ID |
| `/job-status` | Pipeline by status, upcoming steps, stale applications |
| `python3 ui.py` | Web UI on http://127.0.0.1:8765 |

The scripts also work without Claude:

```bash
python3 fetch.py                      # every enabled board, last 30 days
python3 fetch.py --days 7             # last week only
python3 fetch.py --only justjoin      # one board, repeatable
python3 record.py --shortlist         # current shortlist
python3 record.py --recheck           # offers scored on partial information
python3 ui.py --port 9000             # UI on another port
```

## How a run works

1. `python3 fetch.py` calls each enabled board and drops:
   - offers already in `data/jobs.yaml` (by id, or same company and title)
   - offers older than `--days` (30 by default)
   - offers outside your city or remote region from `data/config.yaml`
   - offers below your level (`too-junior` in the output)
   - offers whose title names a language you did not list (`other-language`)
   What is left goes to `data/inbox.jsonl`, best keyword match first.
2. Claude reads `data/inbox.jsonl` in batches of 100, scores every offer against your CV and `data/profile.md` and writes `data/scores.jsonl`.
3. `python3 record.py data/scores.jsonl` merges the batch into `data/jobs.yaml`. Repeat until it reports 0 unscored.
4. `python3 record.py --shortlist` prints everything worth a look.

Scoring rubric:

| Score | Meaning |
|---|---|
| 9-10 | Your target role, location fits, nearly all required skills are in your CV |
| 7-8 | Good fit with 1-2 gaps, or unclear details that are likely fine |
| 4-6 | Partial fit: stack gaps, weak-fit items, unclear level |
| 1-3 | A deal-breaker from `profile.md` |

Score 7 or more (`scoring.shortlist_score`) goes to the shortlist. Skills your CV does not show are listed as `gaps`, never assumed.

## Your data

Everything personal lives in `data/`, which is gitignored, and `.gitignore` also covers `*.pdf`, `*.doc`, `*.docx`, `*.odt` and `*.rtf` so a CV dropped in the project folder stays out too. Gitignore only protects files git is not already tracking: check `git status` before your first commit, and never `git add -f` inside `data/`.

| File | Purpose |
|---|---|
| `data/config.yaml` | Your search filters |
| `data/profile.md` | Your criteria in prose |
| `data/jobs.yaml` | Every offer ever seen: score, why, gaps, decision |
| `data/applications.md` | One row per application: status, dates, next step, notes |
| `data/inbox.jsonl` | New offers from the last fetch (regenerated each run) |
| `data/scores.jsonl` | Scores for the current batch (scratch) |
| `data/cv-notes.md` | CV review history: score per round, what was fixed, open questions |

Your CV stays wherever it is; only its path is stored, in `data/config.yaml`.

Back up `data/` and you have backed up the whole job search. To start over, delete `data/` and run `/job-profile` again.

## Boards

| Board | Access | Market |
|---|---|---|
| justjoin.it | public JSON API | Poland |
| nofluffjobs.com | public JSON API | Poland |
| himalayas.app | public JSON API | remote, worldwide |
| arbeitnow.com | public JSON API | remote, mostly Germany |
| remoteok.com | public JSON API | remote, worldwide |
| LinkedIn | not scraped | use `/job-search <url>` or paste the offer text |
| pracuj.pl, theprotocol.it | block scripts (403) | not included |

Outside Poland: set `sources.justjoin.enabled` and `sources.nofluffjobs.enabled` to `false` in `data/config.yaml`, set `location.country` and `location.city_prefixes` to your own, and keep the three remote boards. Adding a board means a function in `fetch.py` returning `offer(...)` records, an entry in its `SOURCES` dict and a block in `config.yaml` - look at `remoteok()`, the function itself is 20 lines.

## Files

| File | Purpose |
|---|---|
| `config.py` | Paths and config loading shared by the scripts |
| `fetch.py` | Calls the boards, prefilters, writes `data/inbox.jsonl` |
| `record.py` | Merges scores into `data/jobs.yaml`, prints the shortlist |
| `ui.py`, `ui.html` | Local web UI (stdlib http.server plus PyYAML, reads the files on every request) |
| `config.example.yaml`, `profile.example.md`, `applications.example.md` | Templates copied into `data/` |
| `.claude/skills/job-profile/SKILL.md` | Setup from a CV, and the reference for every config key |
| `.claude/skills/cv-review/SKILL.md` | Recruiter, ATS and layout review of the CV |
| `.claude/skills/job-search/SKILL.md` | Search and scoring workflow, rubric |
| `.claude/skills/job-status/SKILL.md` | Application tracker workflow |
| `LICENSE` | MIT |

## IDs and decisions

Every offer gets a short number, written `#42`, assigned once by `record.py` and never reused. The same number appears in the shortlist, in `data/applications.md` and in the UI search box.

Decisions on an offer: `shortlist`, `skip` (set by scoring), `interested`, `not-interested` (set in the UI), `applied`. Rescoring keeps `interested`, `not-interested` and `applied`.

Application statuses, in pipeline order: `applied`, `first-interview`, `tech-interview`, `final`, `offer`, `screening`, then the closed ones `rejected`, `withdrawn`, `no-response`. Dates are `YYYY-MM-DD`.

`first-interview` is the first proper call - experience and expectations, no coding. `tech-interview` is the technical round. `screening` comes last: the background and reference vetting that runs after an offer, standard in fintech and trading.

## Data formats

`data/jobs.yaml` entry:

```yaml
justjoin/acme-senior-backend-engineer-krakow-java-82f1acfa:
  ref: 1
  title: Senior Backend Engineer
  company: Acme
  url: https://justjoin.it/job-offer/acme-senior-backend-engineer-krakow-java-82f1acfa
  source: justjoin
  location: Krakow (hybrid)
  salary: any undisclosed
  skills: [Java, Spring Boot, Apache Kafka]
  languages: [en B2]
  posted: '2026-09-09'
  first_seen: '2026-09-11'
  score: 8
  why: [...]
  gaps: [...]
  decision: shortlist
```

`data/scores.jsonl` line (offers added by URL also need `title`, `company`, `url`, `source`, `location`, `salary`, `skills`, `languages`):

```json
{"id": "justjoin/...", "score": 8, "why": ["..."], "gaps": ["..."], "decision": "shortlist"}
```

## Notes

- The UI binds to `127.0.0.1` only. `--host 0.0.0.0` exposes your applications to the whole network; do not do it on a shared network.
- `/cv-review` uses `pdftotext` (package `poppler-utils`) to check what an ATS actually reads. Without it the review falls back to the CV source and says so.
- Boards change their APIs without warning. A source printing `ERROR` is usually that, not your config.
- Be polite to the boards: the scripts pause between pages, and `/job-search` opens at most 15 individual offer pages per run.
- Run one `/job-search` at a time. Two sessions scoring at once share `data/scores.jsonl` and overwrite each other, and a fetch started mid-scoring replaces the inbox under the batch being scored.
- `record.py` and the UI take a lock on `data/` before writing, but a skill editing `data/applications.md` by hand does not. Either let the UI do status changes while it is running, or stop it first.

## License

MIT - see `LICENSE`.

## Ideas, not built yet

- Salary floor as a filter
- pracuj.pl and theprotocol.it through a browser
- HN "Who is hiring" (Algolia API)
- Scheduled runs

---
name: job-profile
description: Set up or update the job search from a CV - reads the CV, asks the missing questions and writes data/config.yaml, data/profile.md and an empty data/applications.md. Use on first run of job-hunt, when the user says "set up job search", "read my CV", "change my criteria", "I moved city", "I want remote only" or after the CV changed.
---

# Job profile

Turns a CV plus a few answers into the files everything else reads:

- `data/config.yaml` - machine filters used by `fetch.py` (board queries, city, languages, timezones, keywords)
- `data/profile.md` - human criteria used by `/job-search` when scoring (target, deal-breakers, strong and weak fit)
- `data/applications.md` - empty tracker table, only created if missing

Templates: `config.example.yaml`, `profile.example.md`, `applications.example.md` in the project root. Work in the project folder (the one holding `fetch.py`).

## Steps
1. CV path: the skill argument, otherwise ask. `.html`, `.md`, `.txt` and `.pdf` can be read directly. A `.docx` cannot - ask the user to export it as PDF, or convert it yourself if a converter is installed. Never copy CV text into the repo; only the path goes into `config.yaml`, and only facts drawn from it go into `profile.md`.
2. From the CV pull: main role and seniority, core stack, secondary stack, domains, cloud and tooling, spoken languages, current city.
3. Ask the user in one batch, with CV-derived defaults to accept. Ask even when the CV hints at an answer - never decide these alone:
   - city and whether onsite/hybrid/remote, remote countries or timezone band
   - contract types and salary floor (both live in `profile.md` only; there is no config key for them, and a floor is never filtered on)
   - deal-breakers: working languages, levels, role types, regions
   - anything in the CV they do not want to do again
4. `mkdir -p data`, then write `data/config.yaml` using the mapping below. Write **every key of `config.example.yaml`**, even when a list ends up short - the fallbacks are not useful defaults:
   - an empty **exclusion** list (`role.excluded_titles`, `languages.excluded_word_stems`, `location.remote_excluded`) matches nothing, so that filter is silently off
   - an empty **inclusion** list (`role.title_keywords`, `role.main_keyword`, `role.generic_titles`) matches everything instead, so himalayas and arbeitnow stop filtering by role and flood the inbox
   - missing `languages.accepted` means every board language counts as unaccepted
   - missing `location.remote_timezones` means no timezone limit
   - a source missing from `sources` is never fetched at all; `enabled` defaults to true only inside a source block that exists
   - YAML turns unquoted `no`, `yes`, `on`, `off` into booleans; write language codes like `"no"` (Norwegian) in quotes
5. Write `data/profile.md` following `profile.example.md`: Target, Deal-breakers, Strong fit, Weak fit. Strong fit lists only what the CV shows. Scores run 1-10; `scoring.shortlist_score` (default 7) is the shortlist cut-off, read by `record.py` and `/job-search`, not by `fetch.py`.
6. If `data/applications.md` does not exist, copy `applications.example.md` and delete its sample row, keeping the title line, the header row and the `|---|` separator row.
7. Verify: `python3 fetch.py --days 7`. Each source prints `fetched`, `new`, `too-junior` and `other-language`; report the `new` counts, anything filtered in bulk, and any `ERROR` line.
8. Show what was written in one short block: role, location, contract types, sources enabled, deal-breakers, and every answer you assumed rather than got from the user.

A source returning 0 is not always broken:
- `justjoin` and `nofluffjobs` filter board-side, so 0 usually means `category`, `experience_level` or `raw_search` is wrong. Fix those with the user and rerun that source with `--only`.
- `himalayas` and `remoteok` take one query term or tag each - widen it before touching anything else.
- `arbeitnow` has no query at all; it is a small, mostly German remote board filtered by `role.*` keywords, and 0 is a normal result. Raising `max_pages` above 8 gets HTTP 429.

## Updating an existing setup
Read the current `data/config.yaml` and `data/profile.md` first and change only what the user asked about; do not regenerate from the CV and drop their hand edits. Rewriting these files never touches `data/jobs.yaml`, so offers already scored keep their old scores - mention this only if scores exist, and offer a rescore only if asked.

## config.yaml mapping
Match column: **word** = the term with no letter, digit or underscore glued to either end, case-insensitive - `us` does not match `USA`, `java` does not match `javascript`, `c++` does not match `C++Builder`, but a term starting with punctuation stays open on the left, so `.net` does match `ASP.NET`. **stem** = substring anywhere (`niemieck` matches `niemieckim`). **prefix** = start of the city name.

| Key | Match | Used by | Fill with |
|---|---|---|---|
| `cv` | - | `/job-search`, `/job-profile` | Path to the CV, `~` allowed |
| `role.title_keywords` | word | himalayas (title + categories), arbeitnow | Words that mark the role (`java, kotlin, jvm, spring`). justjoin and nofluffjobs filter board-side instead, through their own query keys |
| `role.main_keyword` | word | arbeitnow | The single strongest word, matched against the description when the title is generic |
| `role.generic_titles` | word | arbeitnow | Titles only interesting together with `main_keyword` (`backend, engineer, developer`) |
| `role.seniority_titles` | word | all sources | Levels the user accepts (`senior, lead, staff, principal`). A title carrying one of these survives `excluded_titles` |
| `role.excluded_titles` | word | all sources | Levels below theirs (`junior, intern, graduate, mid`). Counted as `too-junior` in the run output |
| `location.city_prefixes` | prefix | justjoin, nofluffjobs | Lowercase prefixes of home cities, short enough to survive spelling (`krak` matches Krakow and Kraków). Empty list = remote only |
| `location.country` | - | himalayas | Country for boards that filter by country. `sources.himalayas.country` overrides it; leave that key out unless the two should differ |
| `location.remote_timezones` | - | himalayas | `[min, max]` UTC offsets, whole hours only |
| `location.remote_friendly` | word | remoteok | Region words that are always fine (`europe, european, eu, poland, worldwide`). Checked first: one hit here beats every entry in `remote_excluded` |
| `location.remote_excluded` | word | remoteok | Region words that mean the offer is closed to them (`us, usa, united states, canada, latam, apac`). Whole-word, so list both `us` and `usa` |
| `languages.accepted` | - | justjoin, nofluffjobs | Two-letter codes the user works in (`en, pl`), compared against the first token of each board language (`"en B2"` -> `en`). The other boards report no languages, so nothing is filtered there |
| `languages.excluded_word_stems` | stem | all sources, **title only** | Language names and stems that make a title a deal-breaker (`german, deutsch, niemieck`). Use stems without diacritics too when the board writes them both ways |
| `scoring.shortlist_score` | - | `record.py`, `/job-search` | Lowest score that reaches the shortlist, default 7 |
| `scoring.strong_fit` | word | inbox ordering | Stack, domains and ways of working from the CV. Each term hit once pushes an offer up the inbox; short tokens are fine because matching is whole-word, but avoid listing both `spring` and `spring boot` unless double weight is wanted |
| `sources.*.enabled` | - | `fetch.py` | `false` for boards that do not serve the user's market. Missing means true |

## Board queries
| Source | Keys | Notes |
|---|---|---|
| justjoin | `category`, `experience_level` | Category is a justjoin.it slug: `java`, `python`, `javascript`, `php`, `net`, `devops`, `data`, `testing`, ... Level: `junior`, `mid`, `senior`, `c_level`. Polish market |
| nofluffjobs | `raw_search`, `salary_currency`, `salary_period`, `region`, `language` | `raw_search` is their own syntax: `category=backend requirement=java seniority=senior city=krakow,remote`. Polish market |
| himalayas | `query`, `seniority`, `country` | Remote only. `country` falls back to `location.country` |
| arbeitnow | `max_pages` | Remote only, mostly German market, no query of its own |
| remoteok | `tag` | Single tag, lowercase (`java`, `python`, `golang`) |

If the user is not in Poland: set `sources.justjoin.enabled` and `sources.nofluffjobs.enabled` to `false`, keep himalayas, arbeitnow and remoteok, set `location.country` and `city_prefixes` to their own, and say that adding a local board means a new function in `fetch.py`.

## Rules
- Never invent skills or experience the CV does not show.
- Ask rather than guess location, contract type and deal-breakers. Ask once, in the step 3 batch. If the user answers only some of it, fill the rest from the CV, keep those filters wide rather than exclusionary, and list every assumption in step 8 - do not stall the setup waiting for a full answer.
- Keep `data/` out of git; it is gitignored and holds everything personal.

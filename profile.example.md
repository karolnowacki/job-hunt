# Job search profile

Candidate facts: the CV file named by `cv:` in `data/config.yaml` - the only source of truth, never assume skills that are not there.

Offers are scored 1-10 against this file. `scoring.shortlist_score` in `data/config.yaml` (7 by default) is the cut-off for the shortlist.

## Target
- Role: <main role, for example Senior Java / backend engineer; related stacks that are fine>
- Location: <city, onsite/hybrid, remote country, remote timezone band>
- Contracts: <permanent, B2B, contractor, ...>
- Salary: <floor and currency, or "no floor yet - show it, do not filter on it">
- Languages: <languages you can work in>

## Deal-breakers (score 1-3, skip)
- <a working language you do not speak>
- <relocation, or onsite in another city>
- <levels below yours>
- <role types outside your field: frontend, mobile, QA, data science, ...>
- <regions you cannot work from>

## Strong fit
- <core stack from the CV, for example Java 17/21, Spring Boot>
- <messaging, data, cloud tools you have shipped with>
- <domains you know, for example fintech, payments>
- <ways of working you want, for example production ownership, on-call>

## Weak fit (lower score, not skip)
- <stacks next to yours but not in the CV>
- <role shapes you would accept reluctantly, for example fullstack with a big frontend share>
- <for example people management with little hands-on work>

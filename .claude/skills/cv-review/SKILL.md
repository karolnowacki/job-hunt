---
name: cv-review
description: Review a CV like a recruiter and like an ATS parser, score it 1-10 and produce a ranked fix list. Use when the user asks to "review my CV", "score my CV", "is my CV good enough", "will an ATS read this", "why am I getting no replies", or after they changed the CV and want a second pass.
---

# CV review

Reviews the CV named by `cv:` in `data/config.yaml` (or the path given as the argument) against the target role in `data/profile.md`. Three passes: recruiter, ATS, layout. Output is a score, a ranked fix list and a set of questions only the user can answer.

Scope: review and report. Apply fixes only when the user asks, and never invent a fact, a metric or a skill that is not already in the CV.

## Inputs
1. CV path: the argument, otherwise `cv:` in `data/config.yaml`. Ask if neither exists.
2. Target: `data/profile.md`. Missing: ask what role the CV is aimed at, or run `/job-profile` first. A CV is never reviewed in the abstract - every judgement is against that target.
3. Optional signal, only if `data/jobs.yaml` exists: collect the `gaps` of shortlisted offers and count them. A skill demanded by many shortlisted offers and missing from the CV is the strongest possible finding - if the user has it, it belongs on the CV; if not, it is a learning list, not a CV fix.
4. Source files: if the CV is generated (HTML to PDF, LaTeX, Markdown), work on the source and note the export command. Two variants (designed + ATS) are common - every content finding applies to both.

## Pass 1 - recruiter, in a fresh subagent
Run this in a **separate agent with no memory of writing the CV**. A reviewer that helped write the text cannot see it cold, and its score is worth nothing.

Give the subagent: the CV text (and page images if available), the target role, and this task:
- First, a **6-second scan**: report only what stuck - current title, seniority, stack, one selling point. If the target role is not obvious in 6 seconds, that is finding number one.
- Then a full read as a hiring recruiter for the target role: would this get an interview, yes or no, and what kills it.
- Score 1-10 with the scale below, and a one-line verdict: ready to send, or not.
- Top 5 problems, most damaging first, each with a concrete rewrite.
- Nothing about taste, fonts or colours unless it costs the candidate an interview.

Score scale: **9-10** send today, nothing material to fix. **7-8** ready to send, a handful of wording fixes left. **5-6** real gaps (unclear level, missing keywords, weak first third) - fix before applying. **1-4** the role is not readable from the CV, or the parse is broken.

If a second independent reviewer is available (another model or CLI the user has configured), run the same prompt there and report both scores. Skip this silently when there is none - one fresh reviewer is enough.

## Pass 2 - ATS
Machine readability, checked on the file that actually gets uploaded - nearly always a PDF:
- The CV is a source file (HTML, Markdown, LaTeX) and no PDF exists yet: ask the user for the exported PDF, or use the project's own export script if it has one. Never review an export you cannot produce - say the ATS pass was skipped and why.
- Extract text in reading order: `pdftotext -raw <cv.pdf> -` (poppler-utils). No pdftotext: say so and review the source markup instead, and mark the reading-order finding as unverified.
- Reading order must match the visual order. Two-column layouts commonly emit the sidebar or a later section first - that is what scrambles parsers. Check every page, not just page 1.
- Every section heading must survive extraction as plain text: Experience, Education, Skills.
- Dates: one format, `MM.YYYY` or `Month YYYY`, consistent everywhere, no gaps left unexplained.
- Contact line: email, phone and links must come out as text, never as an image or an icon-only link.
- Keyword coverage: compare against `role.title_keywords` and `scoring.strong_fit` in `data/config.yaml` plus the target role in `data/profile.md`. Literal terms matter - a parser looking for `SQL`, `CI/CD` or `Git` does not infer them from `PostgreSQL`, `GitLab CI` or `GitHub`.
- Nothing load-bearing inside a table, text box, header or footer.
- Report as: what parsed, what did not, which expected keywords are absent.

## Pass 3 - layout
- Page count, and whether the last page is nearly empty.
- Clipping: fixed-height designed layouts hide overflow, so page count alone does not prove nothing is cut. Render each page to an image and look at it: `pdftoppm -png -r 110 <cv.pdf> <prefix>` (poppler-utils), then read the images. Neither tool available: skip this pass and say so rather than guessing from the source.
- Page breaks: a job title must not sit at the bottom of a page with its bullets on the next.
- The top third of page 1 is the only part guaranteed to be read - check what occupies it.
- After any change to a generated CV: re-export, re-extract, re-check. The PDF, not the source, is what gets read.

## Output
One report, in this order:
1. Score, verdict, and the 6-second scan result verbatim.
2. **Blockers** - costs interviews, fix before sending.
3. **Worth doing** - clear improvement, no risk.
4. **Opinion** - reviewers may reasonably disagree; say which reviewer wanted it.
5. **Questions for the user** - anything that needs a fact the CV does not contain. Never fill these in yourself.

Then write decisions, applied fixes and open questions to `data/cv-notes.md` (gitignored, created if missing) so the next review starts where this one stopped. Keep the per-round history short: date, score, what was fixed.

## Re-review
After fixes: export again, then run pass 1 in a **new** fresh subagent - never the one that produced the previous findings. Stop when the score stops moving or the reviewer says ready to send; two rounds usually reach that, and a third rarely changes anything.

## Rules
- Never invent metrics, team sizes, dates or outcomes. Missing numbers are a question for the user, not a gap to fill.
- Never move a fact the user marked as not public (unreleased products, internal incidents, layoffs) onto the CV.
- Content changes go into every CV variant, then re-export both.
- Do not touch the CV files unless the user asks for the fixes to be applied.
- Report the reviewer's score as given, including a bad one.

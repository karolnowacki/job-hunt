#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import yaml

from config import INBOX_FILE, JOBS_FILE, load_config, locked, write_text

STORED_FIELDS = ["title", "company", "url", "source", "location", "salary", "skills", "languages", "posted"]
KEPT_DECISIONS = {"applied", "interested", "not-interested"}
SHORTLIST_DECISIONS = {"shortlist", "interested"}
RECHECK_DECISION = "recheck"


def read_jsonl(path, required=False):
    if not path.exists():
        if required:
            sys.exit(f"no such scores file: {path}")
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_jobs():
    if not JOBS_FILE.exists():
        return {}
    return yaml.safe_load(JOBS_FILE.read_text(encoding="utf-8")) or {}


def shortlist_score():
    return int((load_config().get("scoring") or {}).get("shortlist_score", 7))


def save_jobs(jobs):
    write_text(JOBS_FILE, yaml.safe_dump(jobs, allow_unicode=True, sort_keys=False, width=120))


def next_ref(jobs):
    return max((entry.get("ref", 0) for entry in jobs.values()), default=0) + 1


def default_decision(score):
    return "shortlist" if score >= shortlist_score() else "skip"


def cell(value):
    return str(value or "").replace("|", "\\|")


def print_table(entries):
    if not entries:
        print("No matching offers.")
        return
    print("| ID | Score | Company | Role | Salary | Location | Link | Why |")
    print("|---|---|---|---|---|---|---|---|")
    for entry in sorted(entries, key=lambda item: item["score"], reverse=True):
        why = (entry.get("why") or [""])[0]
        print(
            f"| #{entry.get('ref', '')} | {entry['score']} | {cell(entry.get('company'))} | {cell(entry.get('title'))} | {cell(entry.get('salary'))} "
            f"| {cell(entry.get('location'))} | {entry.get('url', '')} | {cell(why)} |"
        )


def record_scores(scores_file):
    scores = read_jsonl(scores_file, required=True)
    inbox = {record["id"]: record for record in read_jsonl(INBOX_FILE)}
    jobs = load_jobs()
    today = date.today().isoformat()
    recorded = []
    for score in scores:
        offer_id = score["id"]
        value = score.get("score")
        if type(value) is not int or not 1 <= value <= 10:
            sys.exit(f"invalid score for {offer_id}: expected an integer from 1 to 10, got {value!r}")
        known = jobs.get(offer_id) or {}
        source = {**known, **(inbox.get(offer_id) or {}), **{field: score[field] for field in STORED_FIELDS if score.get(field)}}
        if not source.get("title"):
            print(f"skipped {offer_id}: not in inbox.jsonl, not in jobs.yaml and no title given", file=sys.stderr)
            continue
        entry = known or {"ref": next_ref(jobs)}
        entry.update({field: source[field] for field in STORED_FIELDS if source.get(field)})
        entry.setdefault("first_seen", today)
        entry["score"] = value
        entry["why"] = score.get("why") or []
        entry["gaps"] = score.get("gaps") or []
        if entry.get("decision") not in KEPT_DECISIONS:
            entry["decision"] = score.get("decision") or default_decision(value)
        jobs[offer_id] = entry
        recorded.append(entry)

    save_jobs(jobs)
    unscored = [offer_id for offer_id in inbox if offer_id not in jobs]
    print(f"recorded {len(recorded)}, unscored in inbox {len(unscored)}, total in jobs.yaml {len(jobs)}")
    print_table([entry for entry in recorded if entry["score"] >= shortlist_score()])


def main():
    parser = argparse.ArgumentParser(description="Merge scores into jobs.yaml and print the shortlist")
    parser.add_argument("scores", nargs="?", type=Path, help="JSONL with id, score, why, gaps, decision")
    parser.add_argument("--shortlist", action="store_true", help="print every shortlisted or interesting offer in jobs.yaml")
    parser.add_argument("--recheck", action="store_true", help="print offers scored on partial information, waiting for a second look")
    args = parser.parse_args()
    if args.shortlist:
        print_table([entry for entry in load_jobs().values() if entry.get("decision") in SHORTLIST_DECISIONS])
    elif args.recheck:
        print_table([entry for entry in load_jobs().values() if entry.get("decision") == RECHECK_DECISION])
    elif args.scores:
        with locked():
            record_scores(args.scores)
    else:
        parser.error("give a scores file, --shortlist or --recheck")


if __name__ == "__main__":
    main()

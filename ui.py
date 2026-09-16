#!/usr/bin/env python3
import argparse
import json
import re
import threading
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from config import APPLICATIONS_FILE, HERE, locked, write_text
from record import cell, default_decision, load_jobs, save_jobs

PAGE_FILE = HERE / "ui.html"
STATUSES = ["applied", "first-interview", "tech-interview", "final", "offer", "screening", "rejected", "withdrawn", "no-response"]
REVIEW_DECISIONS = {"interested", "not-interested"}
EDITABLE_COLUMNS = {"status": "Status", "next_step": "Next step", "notes": "Notes"}
CELL_SEPARATOR = re.compile(r"(?<!\\)\|")
APPLICATIONS_HEADER = [
    "# Applications",
    "",
    "| ID | Company | Role | Link | Source | Contract/salary | Applied | Updated | Status | Next step | Notes |",
    "|---|---|---|---|---|---|---|---|---|---|---|",
]
file_lock = threading.Lock()


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def split_row(line):
    return [value.strip().replace("\\|", "|") for value in CELL_SEPARATOR.split(line.strip())[1:-1]]


def read_applications():
    if not APPLICATIONS_FILE.exists():
        write_text(APPLICATIONS_FILE, "\n".join(APPLICATIONS_HEADER) + "\n")
    lines = APPLICATIONS_FILE.read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("|"))
    end = next((index for index in range(start, len(lines)) if not lines[index].startswith("|")), len(lines))
    header = split_row(lines[start])
    rows = [dict(zip(header, split_row(line))) for line in lines[start + 2:end]]
    return lines[:start], header, rows, lines[end:]


def write_applications(prefix, header, rows, suffix):
    table = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    table += ["| " + " | ".join(cell(row.get(column)) for column in header) + " |" for row in rows]
    write_text(APPLICATIONS_FILE, "\n".join(prefix + table + suffix) + "\n")


def row_key(row):
    return row.get("Link") or f"{row.get('Company')} / {row.get('Role')}"


def public_row(header, row):
    return {"key": row_key(row), **{column: row.get(column) or "" for column in header}}


def find_job(jobs, offer_id):
    if offer_id not in jobs:
        raise ApiError(HTTPStatus.NOT_FOUND, f"unknown offer {offer_id}")
    return jobs[offer_id]


def snapshot(_body=None):
    _, header, rows, _ = read_applications()
    return {
        "jobs": [{"id": offer_id, **entry} for offer_id, entry in load_jobs().items()],
        "applications": [public_row(header, row) for row in rows],
        "statuses": STATUSES,
    }


def set_decision(body):
    jobs = load_jobs()
    entry = find_job(jobs, body.get("id"))
    decision = body.get("decision")
    if decision not in REVIEW_DECISIONS | {"reset"}:
        raise ApiError(HTTPStatus.BAD_REQUEST, f"unknown decision {decision}")
    if entry.get("decision") == "applied":
        raise ApiError(HTTPStatus.CONFLICT, "already applied, change the application status instead")
    entry["decision"] = default_decision(entry["score"]) if decision == "reset" else decision
    save_jobs(jobs)
    return {"id": body["id"], **entry}


def apply(body):
    jobs = load_jobs()
    entry = find_job(jobs, body.get("id"))
    prefix, header, rows, suffix = read_applications()
    row = next((row for row in rows if entry.get("url") and row.get("Link") == entry["url"]), None)
    if row is None:
        today = date.today().isoformat()
        row = {
            "ID": f"#{entry['ref']}",
            "Company": entry.get("company"),
            "Role": entry.get("title"),
            "Link": entry.get("url"),
            "Source": entry.get("source"),
            "Contract/salary": entry.get("salary"),
            "Applied": today,
            "Updated": today,
            "Status": "applied",
        }
        rows.append(row)
        write_applications(prefix, header, rows, suffix)
    entry["decision"] = "applied"
    save_jobs(jobs)
    return {"job": {"id": body["id"], **entry}, "application": public_row(header, row)}


def update_application(body):
    prefix, header, rows, suffix = read_applications()
    row = next((row for row in rows if row_key(row) == body.get("key")), None)
    if row is None:
        raise ApiError(HTTPStatus.NOT_FOUND, f"unknown application {body.get('key')}")
    if "status" in body and body["status"] not in STATUSES:
        raise ApiError(HTTPStatus.BAD_REQUEST, f"unknown status {body['status']}")
    for field, column in EDITABLE_COLUMNS.items():
        if field in body:
            row[column] = " ".join(str(body[field]).split())
    row["Updated"] = date.today().isoformat()
    write_applications(prefix, header, rows, suffix)
    return public_row(header, row)


POST_ACTIONS = {"/api/decision": set_decision, "/api/apply": apply, "/api/application": update_application}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.respond(HTTPStatus.OK, PAGE_FILE.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/data":
            self.run(snapshot, None)
        else:
            self.respond_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self):
        action = POST_ACTIONS.get(self.path)
        if action is None:
            return self.respond_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        if self.headers.get("Content-Type") != "application/json":
            return self.respond_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "expected application/json"})
        length = int(self.headers.get("Content-Length") or 0)
        self.run(action, json.loads(self.rfile.read(length) or b"{}"))

    def run(self, action, body):
        try:
            with file_lock, locked():
                result = action(body)
        except ApiError as error:
            return self.respond_json(error.status, {"error": str(error)})
        self.respond_json(HTTPStatus.OK, result)

    def respond_json(self, status, payload):
        self.respond(status, json.dumps(payload, default=str).encode("utf-8"), "application/json")

    def respond(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="Review offers from jobs.yaml and track applications.md in the browser")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"job-hunt UI on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

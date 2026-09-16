#!/usr/bin/env python3
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None

import yaml

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CONFIG_FILE = DATA / "config.yaml"
EXAMPLE_FILE = HERE / "config.example.yaml"
JOBS_FILE = DATA / "jobs.yaml"
INBOX_FILE = DATA / "inbox.jsonl"
SCORES_FILE = DATA / "scores.jsonl"
PROFILE_FILE = DATA / "profile.md"
APPLICATIONS_FILE = DATA / "applications.md"
LOCK_FILE = DATA / ".lock"
NEVER = re.compile(r"(?!x)x")
ALWAYS = re.compile("")
YAML_BOOLEANS = {True: "yes", False: "no"}


def load_config():
    if not CONFIG_FILE.exists():
        sys.exit(
            f"no {CONFIG_FILE}\n"
            f"run /job-profile in Claude Code, or copy {EXAMPLE_FILE.name} to data/config.yaml and edit it"
        )
    return yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}


def clean(words):
    values = [YAML_BOOLEANS.get(word, word) if isinstance(word, bool) else word for word in words or []]
    return [str(value).strip() for value in values if str(value).strip()]


@contextmanager
def locked():
    DATA.mkdir(parents=True, exist_ok=True)
    if fcntl is None:
        yield
        return
    with open(LOCK_FILE, "a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def word_pattern(word):
    start = r"(?<!\w)" if word[0].isalnum() else ""
    return rf"{start}{re.escape(word)}(?!\w)"


def words_regex(words, when_empty=NEVER):
    terms = clean(words)
    return re.compile("|".join(word_pattern(term) for term in terms), re.I) if terms else when_empty


def stems_regex(stems, when_empty=NEVER):
    terms = clean(stems)
    return re.compile("|".join(re.escape(term) for term in terms), re.I) if terms else when_empty


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def word_regexes(words):
    return [re.compile(word_pattern(term), re.I) for term in clean(words)]


def cv_path(config):
    return Path(str(config.get("cv") or "")).expanduser()

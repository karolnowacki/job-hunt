#!/usr/bin/env python3
import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import yaml

from config import ALWAYS, INBOX_FILE, JOBS_FILE, clean, load_config, stems_regex, word_regexes, words_regex, write_text

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) job-hunt/1.0"
PAGE_PAUSE_SECONDS = 0.3
EXCERPT_LENGTH = 500
UNITS = {"hour": "h", "month": "month", "year": "year", "day": "day"}


class Criteria:
    def __init__(self, config):
        role = config.get("role") or {}
        location = config.get("location") or {}
        languages = config.get("languages") or {}
        scoring = config.get("scoring") or {}
        self.title = words_regex(role.get("title_keywords"), ALWAYS)
        self.main_keyword = words_regex([role.get("main_keyword") or ""], ALWAYS)
        self.generic_title = words_regex(role.get("generic_titles"), ALWAYS)
        self.senior_title = words_regex(role.get("seniority_titles"))
        self.excluded_title = words_regex(role.get("excluded_titles"))
        self.other_language = stems_regex(languages.get("excluded_word_stems"))
        self.accepted_languages = {code.lower() for code in clean(languages.get("accepted"))}
        self.city_prefixes = tuple(prefix.lower() for prefix in location.get("city_prefixes") or [])
        self.country = location.get("country") or ""
        zones = location.get("remote_timezones") or [-24, 24]
        self.timezone_range = range(int(zones[0]), int(zones[-1]) + 1)
        self.remote_friendly = words_regex(location.get("remote_friendly"))
        self.remote_excluded = words_regex(location.get("remote_excluded"))
        self.strong_fit = word_regexes(scoring.get("strong_fit"))

    def is_home_city(self, cities):
        return any(city.lower().startswith(self.city_prefixes) for city in cities) if self.city_prefixes else False

    def region_allowed(self, location):
        if not location or self.remote_friendly.search(location):
            return True
        return not self.remote_excluded.search(location)

    def timezone_allowed(self, zones):
        return not zones or any(zone in self.timezone_range for zone in zones)

    def too_junior(self, title):
        return bool(self.excluded_title.search(title)) and not self.senior_title.search(title)

    def wrong_language(self, record):
        codes = {language.split()[0].lower() for language in record["languages"] if language.strip()}
        return bool(self.other_language.search(record["title"]) or codes - self.accepted_languages)

    def keyword_hits(self, record):
        haystack = " ".join([record["title"], " ".join(record["skills"]), record["excerpt"]])
        return sum(bool(term.search(haystack)) for term in self.strong_fit)


def http_json(url, body=None):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def plain_text(markup):
    text = re.sub(r"<[^>]+>", " ", markup or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()[:EXCERPT_LENGTH]


def epoch_date(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).date().isoformat() if seconds else ""


def salary_text(kind, low, high, currency, unit):
    unit = UNITS.get((unit or "").lower(), unit or "")
    if not low and not high:
        return f"{kind or ''} undisclosed".strip()
    amounts = [round(value) for value in (low, high) if value]
    span = "-".join(str(value) for value in sorted(set(amounts)))
    period = f"{currency}/{unit}" if unit else (currency or "")
    return " ".join(part for part in (kind, span, period) if part)


def location_text(cities, workplace):
    places = ", ".join(cities)
    return f"{places} ({workplace})" if places else workplace


def offer(source, slug, **fields):
    record = {
        "id": f"{source}/{slug}",
        "source": source,
        "url": "",
        "title": "",
        "company": "",
        "location": "",
        "salary": "",
        "skills": [],
        "languages": [],
        "excerpt": "",
        "posted": "",
    }
    record.update(fields)
    return record


def justjoin(criteria, settings, _oldest):
    offers = []
    cursor = 0
    query = {
        "categories": settings.get("category", ""),
        "experienceLevels": settings.get("experience_level", ""),
        "itemsCount": 100,
    }
    while cursor is not None:
        page = http_json(
            "https://justjoin.it/api/candidate-api/offers?"
            + urllib.parse.urlencode({**query, "from": cursor})
        )
        items = page.get("data") or []
        for item in items:
            cities = sorted({place["city"] for place in item.get("locations") or [] if place.get("city")})
            workplace = item.get("workplaceType") or "unknown"
            if workplace != "remote" and not criteria.is_home_city(cities):
                continue
            salaries = [
                salary_text(kind.get("type"), kind.get("fromPerUnit"), kind.get("toPerUnit"), kind.get("currency"), kind.get("unit"))
                for kind in item.get("employmentTypes") or []
                if kind.get("currencySource") == "original"
            ]
            offers.append(offer(
                "justjoin",
                item["slug"],
                url=f"https://justjoin.it/job-offer/{item['slug']}",
                title=item.get("title") or "",
                company=item.get("companyName") or "",
                location=location_text(cities, workplace),
                salary="; ".join(dict.fromkeys(salaries)),
                skills=[skill["name"] for skill in item.get("requiredSkills") or []]
                + [f"nice: {skill['name']}" for skill in item.get("niceToHaveSkills") or []],
                languages=[f"{language['code']} {language.get('level', '')}".strip() for language in item.get("languages") or []],
                posted=(item.get("publishedAt") or "")[:10],
            ))
        next_cursor = ((page.get("meta") or {}).get("next") or {}).get("cursor")
        total = (page.get("meta") or {}).get("totalItems") or 0
        cursor = next_cursor if items and next_cursor is not None and next_cursor < total else None
        time.sleep(PAGE_PAUSE_SECONDS)
    return offers


def nofluffjobs(criteria, settings, _oldest):
    offers = []
    page = 1
    pages = 1
    query = {
        "salaryCurrency": settings.get("salary_currency", "PLN"),
        "salaryPeriod": settings.get("salary_period", "month"),
        "region": settings.get("region", "pl"),
        "language": settings.get("language", "en-GB"),
    }
    while page <= pages:
        result = http_json(
            "https://nofluffjobs.com/api/search/posting?" + urllib.parse.urlencode({**query, "page": page}),
            {"rawSearch": settings.get("raw_search", "")},
        )
        pages = result.get("totalPages") or 1
        for item in result.get("postings") or []:
            location = item.get("location") or {}
            cities = sorted({
                place["city"] for place in location.get("places") or []
                if place.get("city") and place["city"].lower() != "remote"
            })
            remote = item.get("fullyRemote") or location.get("fullyRemote")
            if not remote and not criteria.is_home_city(cities):
                continue
            workplace = "remote" if remote else ("hybrid" if location.get("hybridDesc") else "office")
            salary = item.get("salary") or {}
            tiles = (item.get("tiles") or {}).get("values") or []
            offers.append(offer(
                "nofluffjobs",
                item["url"],
                url=f"https://nofluffjobs.com/pl/job/{item['url']}",
                title=item.get("title") or "",
                company=item.get("name") or "",
                location=location_text(cities, workplace),
                salary=salary_text(salary.get("type"), salary.get("from"), salary.get("to"), salary.get("currency"), salary.get("period")),
                skills=[tile["value"] for tile in tiles if tile.get("type") == "requirement"],
                languages=[tile["value"] for tile in tiles if tile.get("type") == "jobLanguage"],
                posted=epoch_date((item.get("posted") or 0) / 1000),
            ))
        page += 1
        time.sleep(PAGE_PAUSE_SECONDS)
    return offers


def himalayas(criteria, settings, _oldest):
    offers = []
    page = 1
    query = {
        "q": settings.get("query", ""),
        "seniority": settings.get("seniority", ""),
        "country": settings.get("country") or criteria.country,
    }
    while page <= 20:
        result = http_json(
            "https://himalayas.app/jobs/api/search?" + urllib.parse.urlencode({**query, "page": page})
        )
        jobs = result.get("jobs") or []
        for job in jobs:
            title = job.get("title") or ""
            if not criteria.title.search(" ".join([title, *(job.get("categories") or [])])):
                continue
            if not criteria.timezone_allowed(job.get("timezoneRestrictions") or []):
                continue
            countries = job.get("locationRestrictions") or []
            link = job.get("applicationLink") or job.get("guid") or ""
            offers.append(offer(
                "himalayas",
                "/".join(link.rstrip("/").split("/")[-3::2]),
                url=link,
                title=title,
                company=job.get("companyName") or "",
                location=f"remote: {', '.join(countries[:6])}{' +more' if len(countries) > 6 else ''}" if countries else "remote: worldwide",
                salary=salary_text(job.get("employmentType"), job.get("minSalary"), job.get("maxSalary"), job.get("currency"), job.get("salaryPeriod")),
                excerpt=plain_text(job.get("excerpt") or job.get("description")),
                posted=epoch_date(job.get("pubDate")),
            ))
        limit = result.get("limit") or 20
        if not jobs or page * limit >= (result.get("totalCount") or 0):
            break
        page += 1
        time.sleep(PAGE_PAUSE_SECONDS)
    return offers


def arbeitnow(criteria, settings, oldest):
    offers = []
    url = "https://www.arbeitnow.com/api/job-board-api"
    pages = 0
    while url and pages < int(settings.get("max_pages", 8)):
        result = http_json(url)
        pages += 1
        jobs = result.get("data") or []
        for job in jobs:
            title = job.get("title") or ""
            description = job.get("description") or ""
            if not job.get("remote"):
                continue
            if not (criteria.title.search(title)
                    or (criteria.main_keyword.search(description) and criteria.generic_title.search(title))):
                continue
            offers.append(offer(
                "arbeitnow",
                job["slug"],
                url=job.get("url") or "",
                title=title,
                company=job.get("company_name") or "",
                location=location_text([job["location"]] if job.get("location") else [], "remote"),
                salary=", ".join(job.get("job_types") or []),
                skills=job.get("tags") or [],
                excerpt=plain_text(description),
                posted=epoch_date(job.get("created_at")),
            ))
        if jobs and epoch_date(jobs[-1].get("created_at")) < oldest:
            break
        url = (result.get("links") or {}).get("next")
        time.sleep(PAGE_PAUSE_SECONDS)
    return offers


def remoteok(criteria, settings, _oldest):
    offers = []
    for job in http_json("https://remoteok.com/api?" + urllib.parse.urlencode({"tag": settings.get("tag", "")})):
        title = job.get("position") or ""
        location = job.get("location") or ""
        if "id" not in job or not criteria.region_allowed(location):
            continue
        offers.append(offer(
            "remoteok",
            str(job["id"]),
            url=job.get("url") or "",
            title=title,
            company=job.get("company") or "",
            location=f"remote: {location or 'unspecified'}",
            salary=salary_text("", job.get("salary_min"), job.get("salary_max"), "USD", "year"),
            skills=job.get("tags") or [],
            excerpt=plain_text(job.get("description")),
            posted=epoch_date(job.get("epoch")),
        ))
    return offers


SOURCES = {
    "justjoin": justjoin,
    "nofluffjobs": nofluffjobs,
    "himalayas": himalayas,
    "arbeitnow": arbeitnow,
    "remoteok": remoteok,
}


def dedupe_key(company, title):
    return re.sub(r"[^a-z0-9+#]", "", company.lower()) + "|" + re.sub(r"[^a-z0-9+#]", "", title.lower())


def load_jobs():
    if not JOBS_FILE.exists():
        return {}
    return yaml.safe_load(JOBS_FILE.read_text(encoding="utf-8")) or {}


def load_inbox():
    if not INBOX_FILE.exists():
        return []
    return [json.loads(line) for line in INBOX_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description="Fetch job offers that are not in jobs.yaml into inbox.jsonl")
    parser.add_argument("--days", type=int, default=30, help="skip offers posted earlier than this many days ago")
    parser.add_argument("--only", action="append", choices=sorted(SOURCES))
    args = parser.parse_args()

    config = load_config()
    criteria = Criteria(config)
    configured = config.get("sources") or {}
    oldest = (datetime.now(timezone.utc) - timedelta(days=args.days)).date().isoformat()
    jobs = load_jobs()
    seen_keys = {dedupe_key(job.get("company", ""), job.get("title", "")) for job in jobs.values()}

    selected = args.only or [name for name, settings in configured.items() if (settings or {}).get("enabled", True)]
    if not selected:
        sys.exit("no sources selected: every source in data/config.yaml is disabled or missing")
    inbox = []
    succeeded = 0
    failed = []
    for name in selected:
        if name not in SOURCES:
            print(f"{name:12} SKIPPED unknown source")
            failed.append(name)
            continue
        try:
            fetched = SOURCES[name](criteria, configured.get(name) or {}, oldest)
        except Exception as error:
            print(f"{name:12} ERROR {error}")
            failed.append(name)
            continue
        succeeded += 1
        fresh = 0
        junior_filtered = 0
        language_filtered = 0
        for record in fetched:
            key = dedupe_key(record["company"], record["title"])
            if record["id"] in jobs or key in seen_keys or (record["posted"] and record["posted"] < oldest):
                continue
            if criteria.too_junior(record["title"]):
                junior_filtered += 1
                continue
            if criteria.wrong_language(record):
                language_filtered += 1
                continue
            seen_keys.add(key)
            record["kw"] = criteria.keyword_hits(record)
            inbox.append(record)
            fresh += 1
        print(f"{name:12} fetched {len(fetched):4}  new {fresh:4}  too-junior {junior_filtered:3}  other-language {language_filtered:3}")

    if not succeeded:
        sys.exit(f"every source failed, {INBOX_FILE.name} left untouched")
    if failed:
        fetched_ids = {record["id"] for record in inbox}
        kept = [record for record in load_inbox() if record["id"] not in fetched_ids and record["id"] not in jobs]
        inbox += kept
        print(f"{'kept':12} {len(kept)} unscored from the previous inbox ({', '.join(failed)} failed)")
    inbox.sort(key=lambda record: (record["kw"], record["posted"]), reverse=True)
    write_text(INBOX_FILE, "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in inbox))
    print(f"{'total':12} new {len(inbox)} -> {INBOX_FILE.name}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

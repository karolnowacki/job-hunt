import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

import fetch


class FetchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.inbox = self.root / "inbox.jsonl"
        self.jobs = self.root / "jobs.yaml"
        for name, value in (("INBOX_FILE", self.inbox), ("JOBS_FILE", self.jobs)):
            patcher = patch.object(fetch, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def offer(self, slug, source="first", **fields):
        return fetch.offer(
            source, slug,
            **{"title": "Senior Java Engineer", "company": "Acme",
               "url": f"https://example.com/{slug}", "kw": 0, **fields},
        )

    def write_inbox(self, offers):
        self.inbox.write_text("".join(json.dumps(offer) + "\n" for offer in offers), encoding="utf-8")

    def run_fetch(self, sources, *args):
        adapters = {
            name: Mock(side_effect=result) if isinstance(result, Exception) else Mock(return_value=result)
            for name, result in sources.items()
        }
        config = {"sources": {name: {"enabled": True} for name in sources}}
        with patch.object(fetch, "SOURCES", adapters), patch.object(fetch, "load_config", return_value=config), \
                patch.object(sys, "argv", ["fetch.py", *args]), contextlib.redirect_stdout(io.StringIO()):
            fetch.main()
        return fetch.load_inbox()

    def test_distinct_openings_with_same_company_and_title_are_kept(self):
        offers = [self.offer("krakow", location="Krakow (hybrid)"), self.offer("remote", location="remote")]
        self.assertEqual(self.run_fetch({"first": offers}), offers)

    def test_distinct_opening_survives_a_scored_company_title_match(self):
        self.jobs.write_text(yaml.safe_dump({"first/old": self.offer("old")}), encoding="utf-8")
        new = self.offer("new")
        self.assertEqual(self.run_fetch({"first": [new]}), [new])

    def test_duplicate_id_in_one_response_is_only_added_once(self):
        first = self.offer("same")
        duplicate = self.offer("same", title="Updated title", url="https://example.com/another")
        self.assertEqual(self.run_fetch({"first": [first, duplicate]}), [first])

    def test_duplicate_url_across_sources_is_only_added_once(self):
        first = self.offer("shared")
        duplicate = self.offer("other-id", source="second", title="Another title", url=first["url"])
        self.assertEqual(self.run_fetch({"first": [first], "second": [duplicate]}), [first])

    def test_scored_ids_and_urls_are_not_added_again(self):
        known = self.offer("scored")
        self.jobs.write_text(yaml.safe_dump({known["id"]: known}), encoding="utf-8")
        duplicate_url = self.offer("other-id", title="Another title", url=known["url"])
        self.assertEqual(self.run_fetch({"first": [known, duplicate_url]}), [])

    def test_empty_urls_do_not_collapse_distinct_openings(self):
        offers = [self.offer("one", url=""), self.offer("two", url="")]
        self.assertEqual(self.run_fetch({"first": offers}), offers)

    def test_refreshing_one_source_keeps_pending_offers_from_another(self):
        pending = self.offer("pending", source="second", company="Other")
        self.write_inbox([pending])
        fresh = self.offer("fresh")
        self.assertEqual(self.run_fetch({"first": [fresh], "second": []}, "--only", "first"), [fresh, pending])

    def test_successful_empty_refresh_keeps_unscored_offer(self):
        pending = self.offer("pending")
        self.write_inbox([pending])
        self.assertEqual(self.run_fetch({"first": []}), [pending])

    def test_refresh_uses_latest_details_without_repeating_pending_id(self):
        pending = self.offer("pending")
        self.write_inbox([pending])
        fresh = {**pending, "salary": "20000 PLN/month", "title": "Updated title"}
        self.assertEqual(self.run_fetch({"first": [fresh]}), [fresh])

    def test_recorded_pending_offers_are_removed_on_refresh(self):
        pending = self.offer("pending")
        self.write_inbox([pending])
        self.jobs.write_text(yaml.safe_dump({pending["id"]: pending}), encoding="utf-8")
        self.assertEqual(self.run_fetch({"first": []}), [])

    def test_partial_failure_keeps_pending_offers_and_returns_failure(self):
        pending = self.offer("pending", source="second")
        self.write_inbox([pending])
        with self.assertRaises(SystemExit) as raised:
            self.run_fetch({"first": [], "second": RuntimeError("board unavailable")})
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(fetch.load_inbox(), [pending])

    def test_total_failure_leaves_inbox_untouched(self):
        self.write_inbox([self.offer("pending")])
        before = self.inbox.read_bytes()
        with self.assertRaises(SystemExit):
            self.run_fetch({"first": RuntimeError("board unavailable")})
        self.assertEqual(self.inbox.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

import record


class RecordTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.jobs = self.root / "jobs.yaml"
        self.scores = self.root / "scores.jsonl"
        for name, value in (("JOBS_FILE", self.jobs), ("INBOX_FILE", self.root / "inbox.jsonl")):
            patcher = patch.object(record, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(record, "load_config", return_value={"scoring": {"shortlist_score": 7}})
        patcher.start()
        self.addCleanup(patcher.stop)

    def score(self, offer_id="manual/one", **fields):
        return {"id": offer_id, "title": "Engineer", "score": 8, "why": ["Skill match"], "gaps": [], **fields}

    def record_scores(self, scores):
        self.scores.write_text("".join(json.dumps(score) + "\n" for score in scores), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            record.record_scores(self.scores)

    def test_integer_scores_at_both_boundaries_are_accepted(self):
        self.record_scores([self.score("manual/low", score=1), self.score("manual/high", score=10)])
        jobs = record.load_jobs()
        self.assertEqual(jobs["manual/low"]["score"], 1)
        self.assertEqual(jobs["manual/low"]["decision"], "skip")
        self.assertEqual(jobs["manual/high"]["score"], 10)
        self.assertEqual(jobs["manual/high"]["decision"], "shortlist")

    def test_invalid_scores_reject_batch_without_changing_existing_jobs(self):
        original = {"manual/one": {"title": "Original", "ref": 1, "score": 7, "decision": "interested"}}
        for invalid in (0, 11, 99, -1, 7.5, 8.0, True, False, "8", "invalid", None):
            with self.subTest(score=invalid):
                self.jobs.write_text(yaml.safe_dump(original), encoding="utf-8")
                before = self.jobs.read_bytes()
                with self.assertRaisesRegex(SystemExit, "expected an integer from 1 to 10"):
                    self.record_scores([self.score(), self.score("manual/two", score=invalid)])
                self.assertEqual(self.jobs.read_bytes(), before)

    def test_invalid_first_batch_does_not_create_jobs_file(self):
        with self.assertRaisesRegex(SystemExit, "manual/one"):
            self.record_scores([self.score(score=99)])
        self.assertFalse(self.jobs.exists())

    def test_missing_score_is_rejected_with_clear_error(self):
        score = self.score()
        del score["score"]
        with self.assertRaisesRegex(SystemExit, "expected an integer from 1 to 10"):
            self.record_scores([score])
        self.assertFalse(self.jobs.exists())

    def test_valid_rescoring_preserves_user_decisions_and_refs(self):
        for decision in ("interested", "not-interested", "applied"):
            with self.subTest(decision=decision):
                self.jobs.write_text(yaml.safe_dump({"manual/one": {
                    "ref": 42, "title": "Engineer", "score": 8, "decision": decision,
                }}), encoding="utf-8")
                self.record_scores([self.score(score=2, decision="skip")])
                updated = record.load_jobs()["manual/one"]
                self.assertEqual(updated["score"], 2)
                self.assertEqual(updated["decision"], decision)
                self.assertEqual(updated["ref"], 42)


if __name__ == "__main__":
    unittest.main()

"""Offline regression tests for backend hardening fixes.

Covers:
  * the dashboard "/" route no longer leaking job/profile data without a token
  * Flask JSON endpoints tolerating a missing/non-JSON request body
  * applied-jobs dedup state surviving concurrent writers
  * main.py / instahyre_engine.py importing under playwright-stealth 2.x

No network, no Telegram sends, no applications are performed.
"""
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import main  # noqa: E402  (importing main is itself part of the compat test)
import instahyre_engine  # noqa: E402,F401


class DashboardAuthTests(unittest.TestCase):
    def setUp(self):
        self._token = main.DASHBOARD_TOKEN
        main.DASHBOARD_TOKEN = "test-token"
        self.client = main.app.test_client()

    def tearDown(self):
        main.DASHBOARD_TOKEN = self._token

    def test_root_without_token_does_not_leak_dashboard(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("service"), "myjob-ai-bot")
        body = resp.data.lower()
        self.assertNotIn(b"channel-chip", body)
        self.assertNotIn(b"<table", body)

    def test_root_with_valid_token_serves_dashboard(self):
        resp = self.client.get("/?token=test-token")
        self.assertEqual(resp.status_code, 200)
        health = {"service": "myjob-ai-bot", "status": "up", "dashboard": "locked"}
        self.assertNotEqual(resp.get_json(), health)

    def test_healthz_still_public(self):
        resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json().get("service"), "myjob-ai-bot")

    def test_json_endpoint_tolerates_missing_body(self):
        resp = self.client.post("/api/add_channel",
                                headers={"X-Admin-Token": "test-token"})
        self.assertNotEqual(resp.status_code, 500)
        self.assertEqual(resp.get_json().get("status"), "error")


class AppliedJobsDedupTests(unittest.TestCase):
    def setUp(self):
        self._state = main.STATE_FILE
        self._cache = main._APPLIED_JOBS_CACHE
        self._mtime = main._APPLIED_JOBS_MTIME
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)
        main.STATE_FILE = path
        main._APPLIED_JOBS_CACHE = None
        main._APPLIED_JOBS_MTIME = 0
        self.path = path

    def tearDown(self):
        main.STATE_FILE = self._state
        main._APPLIED_JOBS_CACHE = self._cache
        main._APPLIED_JOBS_MTIME = self._mtime
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_concurrent_saves_do_not_lose_updates(self):
        urls = ["https://example.com/job/%d" % i for i in range(40)]
        threads = [threading.Thread(target=main.save_applied_job, args=(u,))
                   for u in urls]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(set(main.safe_load_json(self.path, [])), set(urls))

    def test_blank_url_is_ignored(self):
        main.save_applied_job("")
        self.assertEqual(main.safe_load_json(self.path, []), [])


class StealthCompatTests(unittest.TestCase):
    def test_stealth_sync_is_callable(self):
        self.assertTrue(callable(main.stealth_sync))
        self.assertTrue(callable(instahyre_engine.stealth_sync))


if __name__ == "__main__":
    unittest.main()

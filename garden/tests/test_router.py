import json
import os
from pathlib import Path
import tempfile
import unittest

from garden.router import empty_state, scan, save_events, context, load_state, routes_for, atomic_json

BASE = "the-static-collective"
HEAD1 = "a" * 40
HEAD2 = "b" * 40


class FakeAPI:
    def __init__(self):
        self.head = HEAD1
        self.status = "open"
        self.updated = "2026-11-19T18:00:00Z"
        self.visible = True
        self.pr_count = 1
        self.fail_private = False

    def pages(self, path, **kwargs):
        assert path == "/user/repos"
        return iter([{"full_name": BASE + "/GHoT", "owner": {"login": BASE},
                      "visibility": "public", "default_branch": "main", "html_url": "https://github.com/the-static-collective/GHoT"},
                     *([{"full_name": BASE + "/MEMENTO", "owner": {"login": BASE},
                         "visibility": "private", "default_branch": "main", "html_url": "https://github.com/the-static-collective/MEMENTO"}] if self.visible else [])])

    def get(self, path, **kwargs):
        if "/MEMENTO/" in path and self.fail_private:
            raise RuntimeError("token scope missing")
        if "/commits/" in path:
            return {"sha": self.head}
        if path.endswith("/pulls"):
            if "/MEMENTO/" in path:
                return []
            return [{"number": 17, "state": self.status, "draft": False,
                     "updated_at": self.updated, "merged_at": self.updated if self.status == "closed" else None,
                     "head": {"sha": self.head}, "html_url": "https://github.com/the-static-collective/GHoT/pull/17"}]
        raise AssertionError(path)


class RouterTests(unittest.TestCase):
    def test_baseline_does_not_pretend_pr_was_changed(self):
        api = FakeAPI()
        state, events, coverage = scan(api, empty_state(), BASE, now="t1")
        self.assertEqual(coverage["visible_to_token"], 2)
        self.assertEqual(len(events), 2)
        self.assertTrue(all(x["kind"] == "repo_observed" for x in events))
        self.assertEqual(state["repos"][BASE + "/MEMENTO"]["visibility"], "private")

    def test_noop_change_then_merge_and_no_repeat(self):
        api = FakeAPI()
        a, _, _ = scan(api, empty_state(), BASE, now="t1")
        b, ev, _ = scan(api, a, BASE, now="t2")
        self.assertEqual(ev, [])
        api.status = "closed"
        api.updated = "2026-11-19T19:00:00Z"
        c, ev, _ = scan(api, b, BASE, now="t3")
        self.assertEqual([e["kind"] for e in ev], ["pr_changed"])
        self.assertEqual(ev[0]["after"]["status"], "MERGED")
        self.assertEqual(ev[0]["admission"], "none")
        _, again, _ = scan(api, c, BASE, now="t4")
        self.assertEqual(again, [])

    def test_private_scope_failure_is_held_not_deletion(self):
        api = FakeAPI()
        a, _, _ = scan(api, empty_state(), BASE, now="t1")
        api.visible = False
        b, events, cover = scan(api, a, BASE, now="t2")
        self.assertEqual(events, [])
        self.assertIn(BASE + "/MEMENTO", cover["previously_seen_not_visible_to_token_now"])
        self.assertIn(BASE + "/MEMENTO", b["repos"])
        api.visible = True
        api.fail_private = True
        c, _, cover = scan(api, b, BASE, now="t3")
        self.assertEqual(len(cover["scan_failures"]), 1)
        self.assertIn(BASE + "/MEMENTO", c["repos"])

    def test_round_robin_and_local_receipts_replay(self):
        api = FakeAPI()
        a, ev1, cover = scan(api, empty_state(), BASE, max_repos=1, now="t1")
        self.assertEqual(cover["scanned"], 1)
        b, ev2, cover = scan(api, a, BASE, max_repos=1, now="t2")
        self.assertEqual(cover["scanned"], 1)
        self.assertEqual(set(b["repos"]), {BASE + "/GHoT", BASE + "/MEMENTO"})
        cfg = {"routes": [{"inbox": "garden-reentry", "repos": [BASE + "/*"],
                           "kinds": ["repo_observed"], "visibility": ["public", "private"]}]}
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(save_events(home, ev1 + ev2, b, cfg), 2)
            self.assertEqual(save_events(home, ev1 + ev2, b, cfg), 0)
            self.assertEqual(len(list(Path(home, "outbox/garden-reentry").glob("*.json"))), 2)
            self.assertEqual(len(Path(home, "events.jsonl").read_text().splitlines()), 2)
            self.assertEqual(len(context(home, "MEMENTO")["project_roots"]), 1)
            self.assertEqual(load_state(home)["schema"], "ghot.garden-router/v1")

    def test_no_public_routing_and_not_assumed_exec(self):
        event = {"kind": "pr_changed", "repository": BASE + "/MEMENTO", "visibility": "private"}
        cfg = {"routes": [{"inbox": "garden-reentry", "repos": [BASE + "/*"],
                           "kinds": ["pr_changed"], "visibility": ["public", "private"]},
                          {"inbox": "public-site", "repos": [BASE + "/*"],
                           "kinds": ["pr_changed"], "visibility": ["public"]}]}
        self.assertEqual(routes_for(event, cfg), ["garden-reentry"])
        self.assertEqual(routes_for({**event, "visibility": "public"}, cfg), ["garden-reentry", "public-site"])

    def test_private_data_mode(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home, "state.json")
            atomic_json(path, empty_state())
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()

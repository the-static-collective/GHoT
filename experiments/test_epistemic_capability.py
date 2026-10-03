#!/usr/bin/env python3
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ghot"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


ep = load("epistemic_capability", ROOT / "ghot" / "epistemic_capability.py")
policy = load("epistemic_policy", ROOT / "ghot" / "epistemic_policy.py")


class EpistemicCapabilityTests(unittest.TestCase):
    def test_scheduler_offer_filter_distinguishes_posture_before_scoring(self):
        body = {
            "offers": [
                ep.fake_offer("fresh-worker", "fresh"),
                ep.fake_offer("archive-worker", "lineage-enabled"),
            ]
        }
        all_offers, fresh = policy.posture_matching_offers(
            body,
            "listen.analyze",
            "fresh",
        )
        self.assertEqual(len(all_offers), 2)
        self.assertEqual(len(fresh), 1)
        self.assertEqual(fresh[0]["node_id"], "fresh-worker")
        self.assertEqual(fresh[0]["context_posture"], "fresh")

    def test_fresh_receipt_binds_exact_context_digest(self):
        context = {"current_track": {"id": "song-1", "title": "Arrival"}}
        offer = ep.fake_offer("fresh-worker", "fresh")
        task = ep.make_task(posture="fresh", context=context)
        receipt = ep.execute_fake(offer, task)
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(
            receipt["context_audit"]["supplied_context_sha256"],
            ep.context_sha256(context),
        )
        self.assertEqual(
            receipt["context_audit"]["supplied_context_keys"],
            ["current_track"],
        )

    def test_fresh_worker_rejects_catalog_contamination(self):
        offer = ep.fake_offer("fresh-worker", "fresh")
        task = ep.make_task(
            posture="fresh",
            context={
                "current_track": {"id": "song-1"},
                "catalog_history": [{"id": "old-song"}],
            },
        )
        receipt = ep.execute_fake(offer, task)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(
            receipt["context_audit"]["forbidden_context_keys_present"],
            ["catalog_history"],
        )

    def test_archive_worker_requires_lineage_sources(self):
        offer = ep.fake_offer("archive-worker", "lineage-enabled")
        task = ep.make_task(
            posture="lineage-enabled",
            context={"current_track": {"id": "song-1"}},
        )
        receipt = ep.execute_fake(offer, task)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(
            receipt["context_audit"]["required_context_keys_missing"],
            ["lineage_sources"],
        )

    def test_demo_proves_fresh_archive_and_contaminated_paths(self):
        demo = ep.demo()
        self.assertEqual(demo["fresh"]["receipt"]["status"], "ok")
        self.assertEqual(demo["archive"]["receipt"]["status"], "ok")
        self.assertEqual(demo["contaminated_fresh"]["receipt"]["status"], "rejected")


if __name__ == "__main__":
    unittest.main()

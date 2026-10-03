#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


ep = load("epistemic_capability", ROOT / "ghot" / "epistemic_capability.py")
cc = load("capability_composer", ROOT / "ghot" / "capability_composer.py")


class EpistemicCapabilityTests(unittest.TestCase):
    def candidate(self, node_id, posture, *, location="remote", memory=8 * 1024**3):
        return {
            "node_id": node_id,
            "location": location,
            "url": f"http://{node_id}.invalid",
            "body": {
                "node_id": node_id,
                "system": {"memory_bytes": memory},
                "power": {"willingness": "normal"},
                "offers": [ep.fake_offer(node_id, posture)],
            },
            "field_state": "awake",
            "last_seen": None,
            "age_seconds": 0,
            "consecutive_failures": 0,
            "quarantine_until": None,
        }

    def evaluate(self, candidate, posture):
        return cc.evaluate_candidate(
            candidate,
            "listen.analyze",
            min_battery=None,
            prefer_local=False,
            prefer_plugged_in=False,
            prefer_memory=True,
            context_posture=posture,
        )

    def test_scheduler_rejects_wrong_posture_even_when_worker_has_more_memory(self):
        fresh = self.evaluate(
            self.candidate("fresh-worker", "fresh", memory=4 * 1024**3),
            "fresh",
        )
        archive = self.evaluate(
            self.candidate("archive-worker", "lineage-enabled", memory=64 * 1024**3),
            "fresh",
        )
        self.assertTrue(fresh["eligible"])
        self.assertFalse(archive["eligible"])
        self.assertIn("required context posture not offered: fresh", archive["rejected"])

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

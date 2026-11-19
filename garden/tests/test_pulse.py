import unittest
from garden.pulse import inventory, generate


class Fake:
    def pages(self, path, **kwargs):
        if path == "/user/repos":
            return iter([
                {"full_name": "the-static-collective/Public", "owner": {"login": "the-static-collective"}, "visibility": "public"},
                {"full_name": "the-static-collective/Private", "owner": {"login": "the-static-collective"}, "visibility": "private"},
                {"full_name": "elsewhere/Unrelated", "owner": {"login": "elsewhere"}, "visibility": "private"},
            ])
        if path.endswith("/pulls"):
            return iter([{"number": 12, "html_url": "https://github.com/test/pull/12", "title": "Fix thing", "draft": True, "updated_at": "2026-11-19"}])
        raise AssertionError(path)

    def get(self, path, **kwargs):
        if path.endswith("/commits"):
            return [{"sha": "a" * 40}]
        if path.endswith("/pulls"):
            return [{"number": 10, "html_url": "https://github.com/test/pull/10", "title": "Already merged", "merged_at": "2026-11-18"}]
        if path == "/repos/the-static-collective/Private":
            return {"full_name": "the-static-collective/Private", "visibility": "private", "html_url": "https://github.com/the-static-collective/Private", "default_branch": "main"}
        raise AssertionError(path)


class ContinuityTests(unittest.TestCase):
    def test_private_is_included(self):
        data = inventory(Fake(), "the-static-collective")
        self.assertEqual(len(data["repositories"]), 2)
        self.assertEqual({r["visibility"] for r in data["repositories"]}, {"public", "private"})
        self.assertIn("VISIBLE_TO_SUPPLIED_TOKEN", data["scope"])

    def test_does_not_promote_pr_to_deployment(self):
        text = generate(Fake(), "the-static-collective", "Private", {
            "project": "Garden", "purpose": "Keep building", "foundations": [{"id": "f1", "text": "No shadow authority", "source": "https://example.com"}],
            "next": "Resume and verify", "unknowns": ["field test"]
        })
        self.assertIn("PRIVATE", text)
        self.assertIn("**DRAFT**", text)
        self.assertIn("Deployment: **UNKNOWN**", text)
        self.assertIn("No shadow authority", text)
        self.assertIn("Recently merged (sample", text)


if __name__ == "__main__":
    unittest.main()

import unittest
from garden.pulse import GitHub, inventory, generate


class Fake:
    def pages(self, path, **kwargs):
        if path == "/user/repos":
            return iter([
                {"full_name": "the-static-collective/Public", "owner": {"login": "the-static-collective"}, "visibility": "public"},
                {"full_name": "the-static-collective/Private", "owner": {"login": "the-static-collective"}, "visibility": "private"},
                {"full_name": "elsewhere/Unrelated", "owner": {"login": "elsewhere"}, "visibility": "private"},
            ])
        if path.endswith("/commits"):
            return iter([
                {"sha": "b" * 40, "commit": {"message": "chore(continuity): refresh source-linked GHoT handoff", "committer": {"date": "2026-11-19T21:00:00Z"}}},
                {"sha": "a" * 40, "commit": {"message": "fix: actual code", "committer": {"date": "2026-11-19T19:00:00Z"}}},
            ])
        if path.endswith("/pulls"):
            return iter([{"number": 12, "html_url": "https://github.com/test/pull/12", "title": "Fix thing", "draft": True, "updated_at": "2026-11-19"}])
        raise AssertionError(path)

    def get(self, path, **kwargs):
        if path.endswith("/pulls"):
            return [{"number": 10, "html_url": "https://github.com/test/pull/10", "title": "Already merged", "merged_at": "2026-11-18"}]
        if path == "/repos/the-static-collective/Private":
            return {"full_name": "the-static-collective/Private", "visibility": "private", "html_url": "https://github.com/the-static-collective/Private", "default_branch": "main"}
        raise AssertionError(path)


class ContinuityTests(unittest.TestCase):
    def test_paginates_past_one_hundred_including_private(self):
        class Many(GitHub):
            def __init__(self): pass
            def get(self, path, **kwargs):
                start = (kwargs["page"] - 1) * 100
                if start >= 110: return []
                return [{"full_name": f"the-static-collective/repo-{n}", "owner": {"login": "the-static-collective"}, "visibility": "private" if n < 18 else "public"} for n in range(start, min(start + 100, 110))]

        repos = inventory(Many(), "the-static-collective")["repositories"]
        self.assertEqual(len(repos), 110)
        self.assertEqual(sum(x["visibility"] == "private" for x in repos), 18)

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
        self.assertIn("Last non-pulse code commit", text)
        self.assertNotIn("b" * 40, text)
        self.assertEqual(text, generate(Fake(), "the-static-collective", "Private", {
            "project": "Garden", "purpose": "Keep building", "foundations": [{"id": "f1", "text": "No shadow authority", "source": "https://example.com"}],
            "next": "Resume and verify", "unknowns": ["field test"]
        }))
        self.assertIn("Recently merged (sample", text)


if __name__ == "__main__":
    unittest.main()

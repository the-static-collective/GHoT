"""Hostile local tests of GHoT AI RECOMPOSITION 001. No external model or network."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "ghot" / "ai_recomposition.py"
MANIFEST = ROOT / "integrations" / "ai-recomposition-001" / "adapter-manifest.json"


class TestThinkingWorkbench(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.env = dict(os.environ,
                        GHOT_HOME=str(self.home / "state"),
                        GHOT_ADAPTER_MANIFESTS=str(MANIFEST))
        self.text_file = self.home / "input.txt"
        self.text_file.write_text("Rosemary grows. Rosemary remembers. Sky is blue.\n", encoding="utf-8")

    def cmd(self, *args, expect=0):
        proc = subprocess.run([sys.executable, str(CLI), *map(str, args)],
                              cwd=ROOT, env=self.env, capture_output=True, text=True,
                              timeout=130)
        self.assertEqual(proc.returncode, expect, proc.stderr + proc.stdout)
        return proc

    def plan(self, mode="profile", name="plan.json"):
        path = self.home / name
        self.cmd("plan", "--mode", mode, "--text-file", self.text_file,
                 "--out", path)
        return path

    def run_plan(self, plan, report="report.json", approval=True, source="human-test"):
        args = ["run", "--text-file", self.text_file,
                "--plan-file", plan, "--out", self.home / report,
                "--dispatch-source", source]
        if approval:
            args.append("--approve-exact-plan")
        self.cmd(*args, expect=0 if approval else 1)
        return self.home / report

    def test_profile_is_real_native_rack_dispatch_and_replay(self):
        plan = self.plan()
        self.assertFalse(list((self.home / "state").glob("instrument-rack/dispatches/*.json")))
        self.run_plan(plan)
        report = json.loads((self.home / "report.json").read_text())
        self.assertEqual(len(report["attempts"]), 1)
        self.assertEqual(report["attempts"][0]["status"], "EXECUTED")
        result = report["attempts"][0]["packet"]["donor_result"]["result"]
        self.assertEqual(result["word_count"], 8)
        self.assertEqual(result["unique_words"], 7)
        self.assertEqual(result["source_text_sha256"],
                         hashlib.sha256(self.text_file.read_bytes()).hexdigest())
        self.assertEqual(report["quality_assessment"], "NOT_PERFORMED")
        self.cmd("verify", "--report-file", self.home / "report.json")
        self.run_plan(plan, report="replay.json")
        replay = json.loads((self.home / "replay.json").read_text())
        self.assertEqual(report["attempts"][0]["dispatch_id"], replay["attempts"][0]["dispatch_id"])
        self.assertEqual(report["attempts"][0]["packet"]["packet_id"],
                         replay["attempts"][0]["packet"]["packet_id"])
        self.assertEqual(len(list((self.home / "state").glob("instrument-rack/dispatches/*.json"))), 1)

    def test_explicit_approval_and_changed_input_gate(self):
        plan = self.plan()
        self.run_plan(plan, approval=False)
        self.assertFalse((self.home / "report.json").exists())
        self.text_file.write_text("changed", encoding="utf-8")
        self.cmd("run", "--text-file", self.text_file, "--plan-file", plan,
                 "--out", self.home / "change.json", "--dispatch-source", "test",
                 "--approve-exact-plan", expect=1)
        self.assertFalse((self.home / "change.json").exists())

    def test_tampered_plan_and_report_refuse(self):
        plan = self.plan()
        obj = json.loads(plan.read_text())
        obj["input_sha256"] = "0" * 64
        plan.write_text(json.dumps(obj))
        self.cmd("run", "--text-file", self.text_file, "--plan-file", plan,
                 "--out", self.home / "tamper.json", "--dispatch-source", "test",
                 "--approve-exact-plan", expect=1)
        plan.unlink()
        plan = self.plan()
        self.run_plan(plan)
        report = json.loads((self.home / "report.json").read_text())
        report["attempts"][0]["packet"]["donor_result"]["result"]["word_count"] = 9999
        (self.home / "bad.json").write_text(json.dumps(report))
        self.cmd("verify", "--report-file", self.home / "bad.json", expect=1)

    def test_no_model_means_no_dual_execution(self):
        self.env.pop("GHOT_AI_MODEL_PATH", None)
        self.cmd("plan", "--mode", "both", "--text-file", self.text_file,
                 "--out", self.home / "both.json", expect=1)
        self.assertFalse((self.home / "both.json").exists())

    def test_both_uses_fake_local_cli_only_after_approval(self):
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "llama-cli"
        fake.write_text("#!/usr/bin/env python3\n"
                        "import pathlib,sys,os\n"
                        "args=sys.argv\n"
                        "assert '-f' in args and '-m' in args and '-n' in args\n"
                        "assert '--temp' in args and args[args.index('--temp')+1]=='0'\n"
                        "assert pathlib.Path(args[args.index('-f')+1]).exists()\n"
                        "with open(os.environ['GHOT_FAKE_COUNT'], 'a') as out: out.write('one\\n')\n"
                        "print('Candidate theme: endurance. Not verified.')\n")
        fake.chmod(0o755)
        model = self.home / "test.gguf"
        model.write_bytes(b"FAKE MODEL, NOT A REAL GGUF")
        count = self.home / "calls.txt"
        self.env["PATH"] = str(bin_dir) + os.pathsep + self.env["PATH"]
        self.env["GHOT_AI_MODEL_PATH"] = str(model)
        self.env["GHOT_FAKE_COUNT"] = str(count)
        plan = self.plan(mode="both")
        self.assertFalse(count.exists())
        self.run_plan(plan)
        report = json.loads((self.home / "report.json").read_text())
        self.assertEqual([x["capability"] for x in report["attempts"]],
                         ["analysis.text.profile", "ai.text.infer.local"])
        self.assertTrue(all(x["status"] == "EXECUTED" for x in report["attempts"]))
        llm = report["attempts"][1]["packet"]["donor_result"]["result"]
        self.assertEqual(llm["model_content_sha256"], hashlib.sha256(model.read_bytes()).hexdigest())
        self.assertIn("Candidate theme", llm["output_text"])
        self.assertEqual(count.read_text().count("one"), 1)
        self.cmd("verify", "--report-file", self.home / "report.json")
        self.run_plan(plan, report="replay.json")
        self.assertEqual(count.read_text().count("one"), 1)

    def test_adapter_rejects_undeclared_capability(self):
        env = dict(self.env, GHOT_EXTERNAL_CAPABILITY="shell.run")
        proc = subprocess.run([sys.executable, str(CLI), "adapter"],
                              input=json.dumps({"schema":"ghot.ai-recomposition-input/v0",
                                                "text":"hello"}), text=True,
                              capture_output=True, env=env)
        self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()

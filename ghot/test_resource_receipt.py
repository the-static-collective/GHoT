"""GHoT real compute meters are unit-checked; no fabricated joule totals."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from resource_receipt import (
  SOURCE_BLOB,Inspect,HOLD,meter,validate_and_summarize,
  native_ghot_advice,rapl_delta,one_trial,
)

HERE=Path(__file__).resolve().parents[1]
SOURCE=HERE/"integrations/motif-019/physical-witness.json"

def power(state):
 return {"willingness":state,"source":"battery","charging":False,
         "renewable_surplus":False,"willingness_reasons":["TEST_FIXTURE"]}

class ResourceMeterTests(unittest.TestCase):
 def test_real_pinned_report_produces_identical_answers_after_repeated_ask(self):
  report=meter(SOURCE,trials=2,repeats=12,power=power("normal"))
  self.assertEqual(report["schema"],"ghot.resource-witness/v1")
  self.assertEqual(report["source"]["source_kind"],
                   "motif.question-kind-physical-test/v1")
  self.assertTrue(report["benchmark"]["all_answers_bitwise_equal"])
  x=report["benchmark"]["observed"]
  self.assertEqual(x["reparse"]["parses_per_trial"],12)
  self.assertEqual(x["reuse"]["parses_per_trial"],1)
  self.assertEqual(x["reuse"]["hashes_per_trial"],12)
  self.assertEqual(x["reparse"]["bytes_read_per_trial"],
                   x["reuse"]["bytes_read_per_trial"])
  self.assertEqual(len(report["benchmark"]["raw_trials"]),4)
  self.assertEqual(report["real_remote_tasks_executed"],0)
  self.assertFalse(report["automatic_model_promotion"])
  self.assertFalse(report["resource_accounting"]["actual_energy_usage_attributed_to_this_task"])

 def test_changed_content_revalidates_and_invalid_hold_is_not_reused(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/"source.json"
   original=SOURCE.read_bytes()
   path.write_bytes(original)
   watcher=Inspect(path)
   ok=watcher.answer("reuse")
   self.assertEqual(ok,watcher.answer("reuse"))
   self.assertEqual(watcher.json_parses,1)
   corrupt=json.loads(original)
   corrupt["automatic_admission"]=True
   path.write_text(json.dumps(corrupt))
   with self.assertRaisesRegex(HOLD,"UNVERIFIED_OR_PROMOTED"):
    watcher.answer("reuse")
   self.assertEqual(watcher.json_parses,1)

 def test_native_ghot_willingness_respected_without_offering_real_capability(self):
  normal=native_ghot_advice(power("normal"))
  critical=native_ghot_advice(power("critical"))
  self.assertEqual(normal["native_ghot_scheduler_action"],"run_here")
  self.assertEqual(critical["native_ghot_scheduler_action"],"hold")
  self.assertTrue(critical["offer_withdrawn_by_power"])
  self.assertFalse(normal["real_task_dispatched"])
  self.assertFalse(critical["real_energy_budget_reserved"])

 def test_rapl_counter_wrap_does_not_make_fake_negative_joules(self):
  self.assertEqual(rapl_delta((999000,1000000),(1000,1000000)),.002)
  self.assertIsNone(rapl_delta(None,None))
  self.assertIsNone(rapl_delta((10,100),(20,200)))

 def test_refuse_unknown_mode_and_gauge_schema(self):
  watcher=Inspect(SOURCE)
  with self.assertRaisesRegex(HOLD,"UNKNOWN_RESEARCH_MODE"):
   watcher.answer("dispatch.to_remote")
  corrupted=json.loads(SOURCE.read_text())
  corrupted["schema"]="user.token.credit"
  with self.assertRaisesRegex(HOLD,"WRONG_SOURCE_REPORT_KIND"):
   validate_and_summarize(json.dumps(corrupted).encode())

 def test_no_meaningful_result_without_actual_source(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaisesRegex(HOLD,"SOURCE_NOT_LOCAL_FILE"):
    meter(Path(tmp)/"not_here.json",trials=2,repeats=10,power=power("normal"))

 def test_resource_counter_receipt_is_numeric_but_not_conflated_with_energy(self):
  r=one_trial(SOURCE,"reuse",10)
  self.assertGreater(r["cpu_time_ns"],0)
  self.assertGreater(r["wall_time_ns"],0)
  self.assertEqual(r["json_validation_parses"],1)
  self.assertEqual(r["repetitions"],10)
  self.assertIn(r["package_energy_scope"],("NO_ENERGY_SENSOR",
                   "LINUX_INTEL_RAPL_WHOLE_CPU_PACKAGE_NOT_PER_PROCESS"))

if __name__=="__main__":unittest.main()

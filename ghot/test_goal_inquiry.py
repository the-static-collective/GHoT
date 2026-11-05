import importlib.util
from pathlib import Path
from datetime import datetime, timezone,timedelta
import unittest

spec=importlib.util.spec_from_file_location("g4",Path(__file__).with_name("goal_inquiry.py"))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
T=datetime(2026,11,5,15,tzinfo=timezone.utc)
def power(w="normal"):
 return {"willingness":w,"source":None}
def record(site,ok=True):
 return {
  "kind":m.VERSION,"site":site,"valid_source_response":ok,
  "observation":({"station":site,"fresh_source_witness":True,
    "latest_flow_cfs":100.,"latest_observation_utc":"2026-11-05T14:00:00Z",
    "age_seconds":3600} if ok else None),
  "request_start_utc":"2026-11-05T15:00:00Z",
  "response_end_utc":"2026-11-05T15:00:00Z",
  "http_status":200 if ok else 503,"body_sha256":"a"*64 if ok else None,
  "latency_wall_ns":100000000,"local_cpu_ns":1000000,
  "body_bytes_received":1000 if ok else 0,
  "wire_network_bytes_total":None
 }
class GoalInquiryTests(unittest.TestCase):
 def test_goal_aware_any_stops_at_one_actual_query(self):
  calls=[]
  def fetch(url,site):
   calls.append(site);return record(site)
  x=m.trial("any_fresh","goal_aware",fetch,lambda:T,power())
  self.assertEqual(calls,["blue"])
  self.assertTrue(x["task_contract_completed"])
  self.assertEqual(x["stop_reason"],"STOP_GOAL_MET")
  self.assertEqual(x["actual_resource_units"]["actual_get_requests"],1)
  self.assertEqual(x["actual_steps"][0]["decision"],"STOP_GOAL_MET")
  self.assertIn("datetime=",x["actual_steps"][0]["public_request_url"])
  self.assertIsNone(x["actual_resource_units"]["attributable_joules"])

 def test_two_named_does_not_claim_success_on_one_fresh_source(self):
  calls=[]
  def fetch(url,site):
   calls.append(site);return record(site)
  x=m.trial("two_named_fresh","goal_aware",fetch,lambda:T,power())
  self.assertEqual(calls,["blue","sueur"])
  self.assertTrue(x["task_contract_completed"])
  self.assertFalse(x["actual_steps"][0]["original_goal_satisfied_after_this_step"])
  self.assertTrue(x["actual_steps"][1]["original_goal_satisfied_after_this_step"])

 def test_failed_required_source_means_stop_unreachable(self):
  names=[]
  def fetch(url,site):
   names.append(site);return record(site,ok=(site!="blue"))
  x=m.trial("two_named_fresh","goal_aware",fetch,lambda:T,power())
  self.assertEqual(names,["blue"])
  self.assertFalse(x["task_contract_completed"])
  self.assertEqual(x["stop_reason"],"HOLD_GOAL_UNREACHABLE_WITH_ALLOWED_SOURCES")

 def test_any_can_fallback_after_missing_record(self):
  names=[]
  def fetch(url,site):
   names.append(site);return record(site,ok=(site=="mankato"))
  x=m.trial("any_fresh","goal_aware",fetch,lambda:T,power())
  self.assertEqual(names,["blue","sueur","mankato"])
  self.assertTrue(x["task_contract_completed"])

 def test_explicit_exhaustive_control_really_runs_all_three(self):
  calls=[]
  def fetch(url,site):
   calls.append(site);return record(site)
  x=m.trial("any_fresh","exhaustive",fetch,lambda:T,power())
  self.assertEqual(calls,["blue","sueur","mankato"])
  self.assertTrue(x["task_contract_completed"])
  self.assertEqual(x["actual_resource_units"]["actual_get_requests"],3)

 def test_four_live_but_mocked_arms_are_actual_calls_not_inferred(self):
  calls=[]
  def fetch(url,site):
   calls.append(site);return record(site)
  x=m.compare_two_tasks(fetch,lambda:T,power())
  self.assertEqual(calls,["blue","blue","sueur","mankato",
                          "blue","sueur","mankato","blue","sueur"])
  self.assertEqual(x["actual_network_requests_sent"],9)
  self.assertTrue(all(z["task_contract_completed"] for z in x["actually_executed_trials"]))
  self.assertFalse(x["two_goal_comparisons"]["any_fresh"]["comparison_can_prove_general_causal_savings"])

 def test_critical_power_means_zero_actual_queries_even_for_exhaustive(self):
  def fail(url,site):raise AssertionError("critical dispatched")
  x=m.compare_two_tasks(fail,lambda:T,power("critical"))
  self.assertEqual(x["actual_network_requests_sent"],0)
  self.assertFalse(any(z["task_contract_completed"] for z in x["actually_executed_trials"]))

 def test_goal_contract_rejects_unknown_goal(self):
  with self.assertRaises(m.HOLD):
   m.trial("tell_me_if_river_safe","goal_aware",lambda u,s:record(s),lambda:T,power())

 def test_forged_future_or_wrong_site_success_is_not_completion(self):
  def wrong(url,site):
   x=record(site);x["observation"]["station"]="mankato"
   return x
  with self.assertRaises(m.HOLD):
   m.trial("any_fresh","goal_aware",wrong,lambda:T,power())

if __name__=="__main__":unittest.main()

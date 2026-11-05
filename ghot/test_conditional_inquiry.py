from datetime import datetime,timezone,timedelta
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location("ghot003",Path(__file__).with_name("conditional_inquiry.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
NOW=datetime(2026,11,5,15,tzinfo=timezone.utc)

def power(willingness="normal"):
    return {"willingness":willingness,"source":None}

def reading(site,fresh):
    return {"kind":m.VERSION,"site":site,
            "valid_source_response":True,"observation":{
              "station":site,"fresh_source_witness":fresh,
              "latest_flow_cfs":1200.,"latest_observation_utc":"2026-11-05T14:00:00Z",
              "age_seconds":3600
            },"body_sha256":"a"*64,
            "body_bytes_received":300,"latency_wall_ns":5000000,
            "local_cpu_ns":200000,
            "wire_network_bytes_total":None}

class ActualConditional(unittest.TestCase):
    def test_first_fresh_truly_sends_exactly_one_request(self):
        observed=[]
        def fetch(url,site):
            observed.append((url,site))
            return reading(site,True)
        r=m.execute_question(fetch,lambda:NOW,power())
        self.assertEqual(len(observed),1)
        self.assertEqual(r["requests_sent"],1)
        self.assertEqual(r["actually_executed_sites"],["blue"])
        self.assertEqual(r["skipped_sites"],["sueur","mankato"])
        self.assertTrue(r["source_witness_found"])
        self.assertTrue(r["stopped_early"])
        self.assertEqual(r["body_payload_bytes_received"],300)
        self.assertIsNone(r["electrical_energy_joules"])
        self.assertFalse(r["credit_cost_used"])

    def test_stale_first_then_second_fresh_stops_before_third(self):
        names=[]
        def fetch(url,site):
            names.append(site)
            return reading(site,site=="sueur")
        r=m.execute_question(fetch,lambda:NOW,power())
        self.assertEqual(names,["blue","sueur"])
        self.assertEqual(r["witness"]["site"],"sueur")
        self.assertEqual(r["requests_sent"],2)

    def test_all_absent_requires_exactly_three_no_false_truth(self):
        names=[]
        def fetch(url,site):
            names.append(site)
            x=reading(site,False);x["valid_source_response"]=False
            x["observation"]=None
            return x
        r=m.execute_question(fetch,lambda:NOW,power())
        self.assertEqual(names,["blue","sueur","mankato"])
        self.assertEqual(r["status"],"HOLD_NO_RECENT_SOURCE_IN_FIXED_THREE")
        self.assertFalse(r["source_witness_found"])
        self.assertFalse(r["stopped_early"])

    def test_critical_power_does_not_access_network(self):
        def bad(url,site):raise AssertionError("critical power leaked network")
        r=m.execute_question(bad,lambda:NOW,power("critical"))
        self.assertEqual(r["requests_sent"],0)
        self.assertEqual(r["status"],"HOLD_GHOT_CRITICAL_POWER_NO_NETWORK_REQUESTS")

    def test_fake_success_without_witness_refused(self):
        def forged(url,site):
            x=reading(site,True)
            del x["observation"]["latest_flow_cfs"]
            return x
        with self.assertRaises(m.HOLD):
            m.execute_question(forged,lambda:NOW,power())

    def test_full_utc_interval_in_actual_url(self):
        seen=[]
        def f(url,site):
            seen.append(url)
            return reading(site,True)
        x=m.execute_question(f,lambda:NOW,power())
        self.assertEqual(x["recorded_query_windows"][0]["end_utc"],"2026-11-05T14:00:00Z")
        self.assertIn("T14%3A00%3A00Z",seen[0])
        self.assertEqual(len(seen),1)

if __name__=="__main__":unittest.main()

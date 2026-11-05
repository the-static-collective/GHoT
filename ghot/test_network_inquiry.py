import unittest
import importlib.util
import json
from pathlib import Path
from datetime import datetime,timezone,timedelta

spec=importlib.util.spec_from_file_location("network002",Path(__file__).with_name("network_inquiry.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
TIME=datetime(2026,11,5,15,tzinfo=timezone.utc)

def valid_receipt(site,ago_seconds=3600,fail=False):
    snap=TIME-timedelta(seconds=ago_seconds)
    return {
        "kind":m.VERSION,"site":site,"request_start_utc":m.iso(TIME),
        "response_end_utc":m.iso(TIME+timedelta(milliseconds=100)),
        "http_status":200 if not fail else 503,
        "latency_wall_ns":100_000_000,
        "local_cpu_ns":1_000_000,
        "body_bytes_received":200 if not fail else 0,
        "wire_network_bytes_total":None,"body_sha256":"a"*64 if not fail else None,
        "content_type_header":"application/json","error":None if not fail else "HTTPError",
        "valid_source_response":not fail,
        "observation":({
          "station":site,"latest_observation_utc":m.iso(snap),
          "age_seconds":ago_seconds,"latest_flow_cfs":1223.,
          "parsed_source_points":5,"fresh_source_witness":ago_seconds<=m.FRESH_SECONDS,
          "evidence_is":"USGS_REPORTED_VALUE_NOT_INDEPENDENTLY_AUTHENTICATED"
        } if not fail else None)
    }

def power(willingness="normal"):
    return {"willingness":willingness,"source":"battery",
            "battery_percent":17,"temperature_c":50,
            "probe":{"manual_hints":{"battery_percent":True}}}

class Network002(unittest.TestCase):
    def test_short_circuit_when_first_source_provides_real_fresh_witness(self):
        rs=[valid_receipt(site) for site,_ in m.STATIONS]
        report=m.summarize(rs,m.iso(TIME),power())
        x=report["strategy_comparison"]["alternative_policies_NOT_ACTUALLY_RUN"]
        self.assertTrue(x["first_source_only"]["physical_source_witness"])
        self.assertEqual(x["until_first_witness"]["inferred_query_count"],1)
        self.assertEqual(x["all_three"]["inferred_query_count"],3)
        self.assertEqual(report["actual_network_activity"]["requests_sent"],3)
        self.assertIsNone(report["actual_network_activity"]["actual_on_wire_network_bytes"])
        self.assertIsNone(report["actual_network_activity"]["energy_joules_attributable_to_requests"])
        self.assertFalse(report["electrical_energy_measured"])

    def test_fallback_requires_next_query_if_source_stale_or_unavailable(self):
        receipts=[
          valid_receipt("blue",ago_seconds=100000),
          valid_receipt("sueur",fail=True),
          valid_receipt("mankato",ago_seconds=500)
        ]
        report=m.summarize(receipts,m.iso(TIME),power())
        x=report["strategy_comparison"]["alternative_policies_NOT_ACTUALLY_RUN"]
        self.assertFalse(x["first_source_only"]["physical_source_witness"])
        self.assertEqual(x["until_first_witness"]["inferred_query_count"],3)
        self.assertEqual(x["until_first_witness"]["witness_site"],"mankato")
        self.assertEqual(report["actual_network_activity"]["source_failures"],1)

    def test_no_observed_witness_does_not_assert_no_physical_water(self):
        receipts=[valid_receipt(s,ago_seconds=100000) for s,_ in m.STATIONS]
        result=m.summarize(receipts,m.iso(TIME),power())
        self.assertEqual(result["disposition"],"HOLD_NO_FRESH_SOURCE_WITNESS_OBSERVED")
        self.assertEqual(result["actual_network_activity"]["fresh_public_source_count"],0)

    def test_bad_destination_cannot_use_private_host_or_http(self):
        start=TIME-timedelta(hours=2)
        url=m.query_url("blue",start,TIME)
        m.preflight_url(url,"blue")
        for attack in ("http://127.0.0.1:8080/","https://api.waterdata.usgs.gov.evil.invalid/",
                       "https://api.waterdata.usgs.gov@127.0.0.1/"):
            with self.assertRaises(m.HOLD):m.preflight_url(attack,"blue")

    def test_wrong_sensor_payload_holds_and_missing_records_remain_missing(self):
        raw={"type":"FeatureCollection","links":[],"features":[{
            "type":"Feature","properties":{
                "monitoring_location_id":"USGS-05320000",
                "parameter_code":"00060","unit_of_measure":"ft3/s",
                "time":m.iso(TIME-timedelta(hours=1)),"value":123.3}}]}
        result=m.latest_observation(raw,"blue",TIME)
        self.assertTrue(result["fresh_source_witness"])
        raw["features"][0]["properties"]["monitoring_location_id"]="USGS-00000000"
        with self.assertRaises(m.HOLD):m.latest_observation(raw,"blue",TIME)
        self.assertFalse(m.latest_observation({"type":"FeatureCollection",
                     "features":[],"links":[]},"blue",TIME)["fresh_source_witness"])

    def test_power_critical_refuses_extra_work(self):
        self.assertFalse(m.budget_guard(power("critical")))
        self.assertTrue(m.budget_guard(power("normal")))

    def test_negative_future_timestamp_is_rejected(self):
        raw={"type":"FeatureCollection","features":[{
            "properties":{"monitoring_location_id":"USGS-05320000",
            "parameter_code":"00060","unit_of_measure":"ft3/s",
            "time":m.iso(TIME+timedelta(hours=2)),"value":55}}]}
        with self.assertRaises(m.HOLD):m.latest_observation(raw,"blue",TIME)

if __name__=="__main__":unittest.main()

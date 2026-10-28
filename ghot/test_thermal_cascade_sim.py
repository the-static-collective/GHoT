"""Energy-conservation and authority-boundary tests for THERMAL-DOMINO-CASCADE-002."""
import unittest
from thermal_cascade_sim import Scenario, simulate


class ThermalCascadeTests(unittest.TestCase):
    def test_one_burn_several_outputs_without_double_counting(self):
        r=simulate()
        d=r["first_law_kwh"]
        self.assertEqual(d["fuel_input"], 40)
        self.assertEqual(d["heating_energy_available"], 30)
        self.assertAlmostEqual(d["heat_engine_shaft_work"], 0.8)
        self.assertAlmostEqual(d["pressure_buffer_input_work_not_new_energy"], 0.2)
        self.assertAlmostEqual(d["potential_delivered_work_from_buffer"], 0.13)
        self.assertAlmostEqual(d["battery_energy_after_conversion"], 0.432)
        self.assertAlmostEqual(d["heat_to_home_after_work_extraction"], 28.48)
        self.assertAlmostEqual(d["unutilized_energy"], 10.958)
        self.assertAlmostEqual(d["sum_of_useful_outputs"]+d["unutilized_energy"],d["fuel_input"],places=5)
        self.assertEqual(r["hypothetical_schedule"]["optional_compute"],"HOLD")

    def test_taking_work_reduces_heat_delivery(self):
        baseline=simulate(Scenario(hot_stage_kwh=0))
        with_engine=simulate()
        self.assertGreater(
            baseline["first_law_kwh"]["heat_to_home_after_work_extraction"],
            with_engine["first_law_kwh"]["heat_to_home_after_work_extraction"])
        self.assertGreater(
            with_engine["first_law_kwh"]["battery_energy_after_conversion"],0)
        self.assertEqual(baseline["first_law_kwh"]["battery_energy_after_conversion"],0)

    def test_buffer_only_stores_an_allocation_of_shaft_work(self):
        a=simulate(Scenario(proposed_buffer_share_of_shaft=0))
        b=simulate(Scenario(proposed_buffer_share_of_shaft=1))
        self.assertEqual(a["first_law_kwh"]["potential_delivered_work_from_buffer"],0)
        self.assertEqual(b["first_law_kwh"]["battery_energy_after_conversion"],0)
        self.assertAlmostEqual(b["first_law_kwh"]["potential_delivered_work_from_buffer"],0.52)
        for x in (a,b):
            self.assertEqual(x["first_law_kwh"]["energy_closure_error"],0)

    def test_compute_timing_only_is_not_combustion_control(self):
        r=simulate(Scenario(proposed_optional_compute_kwh=0.1))
        self.assertEqual(r["hypothetical_schedule"]["optional_compute"],"RUN_ELIGIBLE")
        self.assertIs(r["hypothetical_schedule"]["pressure_is_a_second_fuel"],False)
        self.assertIs(r["hypothetical_schedule"]["source_is_measured"],False)
        self.assertTrue(any("No pump" in x for x in r["non_goals"]))

    def test_invalid_or_impossible_assumptions_are_rejected(self):
        for s in (
            Scenario(hot_stage_kwh=100),
            Scenario(house_load_kw=0),
            Scenario(generator_fraction=1.2),
            Scenario(heat_available_fraction=float("nan")),
            Scenario(hypothetical_buffer_roundtrip_fraction=-0.2),
        ):
            with self.assertRaises(ValueError):
                simulate(s)


if __name__=="__main__":
    unittest.main()

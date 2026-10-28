"""Feedback and conservation checks for THERMAL-FLOW-FEEDBACK-003."""
import unittest
from flow_feedback_sim import FlowPolicy, simulate
from thermal_cascade_sim import Scenario as CascadeScenario


class FlowFeedbackTests(unittest.TestCase):
    def test_one_source_and_energy_closure(self):
        r=simulate()
        e=r["cumulative_energy_kwh"]
        self.assertEqual(len(r["hours"]),24)
        self.assertEqual(e["energy_closure_error"],0)
        self.assertAlmostEqual(e["total_ledger_energy"],40,places=4)
        self.assertEqual(r["mode"],"offline_only_synthetic_no_controls")
        self.assertTrue(r["physics"]["recovered_heat_is_never_double_counted"])
        self.assertTrue(all(h["sensor_data"]=="synthetic_model_only" for h in r["hours"]))

    def test_electronic_heat_recovery_helps_room_but_adds_no_energy(self):
        warmed=simulate(FlowPolicy(electronics_heat_captured_indoors=0.90))
        dissipated_outside=simulate(FlowPolicy(electronics_heat_captured_indoors=0.0))
        warm=warmed["cumulative_energy_kwh"]
        cold=dissipated_outside["cumulative_energy_kwh"]
        self.assertGreater(warm["room_heat_from_electronics"],cold["room_heat_from_electronics"])
        self.assertGreater(cold["electronics_heat_lost_outdoors"],warm["electronics_heat_lost_outdoors"])
        self.assertAlmostEqual(warm["total_ledger_energy"],cold["total_ledger_energy"],places=5)

    def test_feedback_respects_battery_reserve_and_changes_decision(self):
        r=simulate(FlowPolicy(house_heat_demand_kwh_per_hour=2.0))
        self.assertGreater(r["service_feedback_not_energy"]["optional_tasks_run"],0)
        self.assertGreaterEqual(
            r["cumulative_energy_kwh"]["remaining_battery"],0.20-1e-9
        )
        blocked=simulate(FlowPolicy(battery_reserve_kwh=0.43))
        self.assertEqual(blocked["service_feedback_not_energy"]["optional_tasks_run"],0)
        self.assertTrue(all(h["ghot_optional_compute_advice"]=="HOLD" for h in blocked["hours"]))

    def test_no_heat_means_no_magic_loop(self):
        r=simulate(source=CascadeScenario(fuel_kwh=0,hot_stage_kwh=0))
        self.assertEqual(r["cumulative_energy_kwh"]["total_ledger_energy"],0)
        self.assertEqual(r["service_feedback_not_energy"]["optional_tasks_run"],0)
        self.assertGreater(r["service_feedback_not_energy"]["heat_demand_unmet_during_modeled_hours_kwh"],0)

    def test_passive_mass_release_cannot_be_actuated_by_ghot(self):
        r=simulate(FlowPolicy(hours=3,passive_mass_release_per_hour=0))
        self.assertEqual(r["cumulative_energy_kwh"]["room_heat_from_mass"],0)
        self.assertEqual(r["cumulative_energy_kwh"]["remaining_mass_bank"],r["initial_energy_kwh"]["mass_bank"])
        self.assertTrue(r["physics"]["mass_discharge_is_not_programmable_by_ghot"])
        self.assertIn("no combustion/valves/pumps/pressure",r["read_only_loops"][2]["control"])

    def test_invalid_scenarios_rejected(self):
        for p in (FlowPolicy(hours=0),FlowPolicy(hours=1.5),
                  FlowPolicy(passive_mass_release_per_hour=1.01),
                  FlowPolicy(house_heat_demand_kwh_per_hour=0),
                  FlowPolicy(battery_reserve_kwh=float("inf")),
                  FlowPolicy(optional_task_electric_kwh=-0.1)):
            with self.assertRaises(ValueError):
                simulate(p)


if __name__ == "__main__":
    unittest.main()

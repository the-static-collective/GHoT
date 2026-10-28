"""Zero-hardware checks for THERMAL-DOMINO-HOUSE-001."""
import unittest
from thermal_domino_sim import Scenario, simulate


class ThermalDominoTests(unittest.TestCase):
    def test_nominal_budget_is_conservative_and_optional_work_holds(self):
        r = simulate()
        self.assertEqual(r["mode"], "offline_hypothetical_only")
        self.assertEqual(r["thermal_budget"]["wood_energy_kwh"], 40.0)
        self.assertEqual(r["thermal_budget"]["assumed_mass_stored_kwh"], 20.972)
        self.assertEqual(r["thermal_budget"]["bank_duration_at_assumed_load_h"], 20.97)
        self.assertEqual(r["electric_budget"]["assumed_teg_raw_wh"], 40.0)
        self.assertEqual(r["electric_budget"]["battery_above_reserve_wh"], 12.0)
        self.assertEqual(r["electric_budget"]["optional_compute"], "HOLD")

    def test_cold_house_uses_heat_bank_faster(self):
        a = simulate(Scenario(house_heat_demand_kw=1))
        b = simulate(Scenario(house_heat_demand_kw=2))
        self.assertAlmostEqual(a["thermal_budget"]["bank_duration_at_assumed_load_h"] / 2,
                               b["thermal_budget"]["bank_duration_at_assumed_load_h"], delta=0.011)

    def test_no_energy_creation(self):
        with self.assertRaises(ValueError):
            simulate(Scenario(teg_watts_while_firing=200000))
        with self.assertRaises(ValueError):
            simulate(Scenario(assumed_useful_heat_fraction=1.5))
        with self.assertRaises(ValueError):
            simulate(Scenario(battery_initial_wh=140))
        with self.assertRaises(ValueError):
            simulate(Scenario(house_heat_demand_kw=0))

    def test_separate_safety_and_computing(self):
        r = simulate()
        self.assertEqual(r["ghot_observations"]["renewable_surplus"], False)
        self.assertIn("actuator.pressure_relief.set", r["ghot_observations"]["forbidden"])
        self.assertIn("advisory_compute_routing", r["scope"])
        self.assertIn("not_inferred", r["ghot_observations"]["renewable_claim"])
        self.assertIn("Independent certified heating appliance", r["safety_boundary"])


if __name__ == "__main__":
    unittest.main()

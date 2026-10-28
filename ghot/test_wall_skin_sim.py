"""Wall skin 004 closes the energy budget and blocks false claims."""
import unittest
from wall_skin_sim import PanelAssumptions, simulate

class TestWallSkin(unittest.TestCase):
    def test_default_energy_conservation_and_three_branches(self):
        r=simulate()
        self.assertEqual(r["mode"],"synthetic_no_hardware_no_installations")
        self.assertEqual(len(r["hourly"]),24)
        self.assertEqual(r["energy_kwh"]["closure_error"],0)
        self.assertAlmostEqual(r["energy_kwh"]["fuel_initial"],40)
        self.assertGreater(r["room_heat_from_branches_kwh"]["radiant"],0)
        self.assertGreater(r["room_heat_from_branches_kwh"]["pcm"],0)
    def test_teg_is_not_a_magic_wall_generator(self):
        r=simulate()
        v=r["energy_kwh"]
        self.assertLess(v["experimental_teg_wall_battery_recovered"],
                        v["experimental_teg_wall_heat_diverted"])
        self.assertGreater(v["experimental_teg_wall_loss_outdoors"],0)
        self.assertIn("thermal gradient",r["panel_meanings"]["experimental_teg"])
    def test_zero_teg_share_yields_zero_new_battery(self):
        r=simulate(PanelAssumptions(masonry_share=.65,experimental_teg_share=0))
        v=r["energy_kwh"]
        self.assertEqual(v["experimental_teg_wall_battery_recovered"],0)
        self.assertEqual(v["initial_battery_before_wall_teg"],v["initial_battery_after_wall_teg"])
        self.assertEqual(v["closure_error"],0)
    def test_panel_splits_cannot_generate_extra_energy(self):
        for p in (PanelAssumptions(radiant_share=.8),
                  PanelAssumptions(pcm_indoor_capture=1.2),
                  PanelAssumptions(hours=0),
                  PanelAssumptions(masonry_discharge_hourly=-.1),
                  PanelAssumptions(background_task_wh=0)):
            with self.assertRaises(ValueError): simulate(p)
    def test_pcm_delays_heat_and_more_storage_reduces_initial_release(self):
        a=simulate(PanelAssumptions(pcm_discharge_hourly=.03))
        b=simulate(PanelAssumptions(pcm_discharge_hourly=.3))
        self.assertGreater(a["hourly"][0]["pcm_wall_kwh"],b["hourly"][0]["pcm_wall_kwh"])
        self.assertLess(a["room_heat_from_branches_kwh"]["pcm"],b["room_heat_from_branches_kwh"]["pcm"])
        self.assertEqual(a["energy_kwh"]["closure_error"],0)
        self.assertEqual(b["energy_kwh"]["closure_error"],0)
    def test_feedback_advises_optional_compute_no_hardware_control(self):
        r=simulate(PanelAssumptions(existing_battery_reserve_kwh=0.6))
        self.assertTrue(all(h["ghot_nonessential_compute_advice"]=="HOLD" for h in r["hourly"]))
        self.assertTrue(any("No wall piping" in s for s in r["safety_rules"]))

if __name__=="__main__":unittest.main()

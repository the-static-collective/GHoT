import unittest
from fuel_commons_006 import ROUTES,REQUIRED,route,validate
class FuelCommonsTests(unittest.TestCase):
 def test_entire_registry_unverified(self):
  self.assertTrue(validate()["research_only"])
  for r in ROUTES:
   p=route(r.source,r.output)
   self.assertEqual(p["status"],"HOLD_MISSING_EVIDENCE")
   self.assertFalse(p["dispatch_authorized"])
   self.assertFalse(p["actual_transfer"])
   self.assertFalse(p["output_energy_measured"])
 def test_material_is_not_qualified_fuel(self):
  for inp,out in [("plastic","home_plastic_fuel"),
                  ("cooking_oil","raw_cooking_oil_burner"),
                  ("used_motor_oil","specified_biodiesel"),
                  ("edible","qualified_biogas")]:
   self.assertEqual(route(inp,out)["status"],"REJECT_UNSUPPORTED_OR_UNSAFE")
 def test_only_legitimate_routes_for_special_cases(self):
  self.assertEqual(route("edible","donated_food")["proposal"]["priority"],"FOOD_FIRST")
  self.assertEqual(route("plastic","recycled_material")["proposal"]["processor"],"qualified_recycler")
  self.assertEqual(route("cooking_oil","specified_biodiesel")["proposal"]["processor"],"professional_refiner")
 def test_forged_self_attestation_does_not_dispatch(self):
  claims={k:True for k in REQUIRED}
  p=route("manure","qualified_biogas",claims)
  self.assertEqual(p["status"],"HOLD_INDEPENDENT_REVIEW")
  for k in ("actual_inventory","fuel_certified","operator_enrolled","dispatch_authorized"):
   self.assertFalse(p[k])
 def test_unknowns_and_wrong_shape_rejected(self):
  with self.assertRaises(ValueError):route("unknown","anything")
  with self.assertRaises(ValueError):route("manure","qualified_biogas",[])
if __name__=="__main__":unittest.main()

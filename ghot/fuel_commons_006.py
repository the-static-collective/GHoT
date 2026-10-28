#!/usr/bin/env python3
"""Fuel Commons 006: research-only, no-network resource-bank route guard.

Material ownership, licensed conversion, qualified fuel, and metered output
are distinct. Neither evidence claims nor an available path authorize transfer.
No equipment controls, quantities, fuel processing, or energy yields.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
import json

@dataclass(frozen=True)
class Route:
    source: str
    bank: str
    processor: str
    output: str
    destination: str
    priority: str

ROUTES=(
 Route("edible","food","food_rescue","donated_food","people","FOOD_FIRST"),
 Route("scraps","organics","authorized_compost","compost","soil","ORGANICS_RECOVERY"),
 Route("scraps","organics","permitted_digester","qualified_biogas","approved_facility","ORGANICS_RECOVERY"),
 Route("manure","farm_organics","permitted_digester","qualified_biogas","approved_facility","OPERATED_BY_SPECIALISTS"),
 Route("cooking_oil","refinery_feedstock","professional_refiner","specified_biodiesel","compatible_approved_burner","REFINER_ONLY"),
 Route("clean_wood","solid_fuel","quality_movement_review","verified_dry_wood","approved_wood_heater","LOCAL_LEGAL_FUEL"),
 Route("crop_residue","biomass_feedstock","authorized_biomass_processor","specified_biomass","rated_facility","SPECIALIST_ONLY"),
 Route("plastic","materials_recovery","qualified_recycler","recycled_material","materials_receiver","NOT_DOMESTIC_FUEL"),
 Route("used_motor_oil","regulated_waste","regulated_recycler","recovered_oil_material","qualified_recycler","NEVER_MIX_WITH_FOOD_OIL"),
 Route("solar","measured_energy","rated_controller","metered_electricity","approved_storage_or_electric_load","NOT_FUEL"),
)
REQUIRED=("owner_consent","material_identity","authorized_processor",
          "permits_checked","qualified_receiver","output_specified","destination_compatible")
REJECTED=("home_pyrolysis_oil","home_plastic_fuel","raw_cooking_oil_burner",
          "home_biogas_burner","mixed_waste_oil","unapproved_appliance")

def route(source:str,output:str,claimed:dict|None=None)->dict:
    if not isinstance(source,str) or not isinstance(output,str):
        raise ValueError("Source and output must be known strings.")
    if source not in {r.source for r in ROUTES}:
        raise ValueError("Unknown source.")
    match=next((r for r in ROUTES if (r.source,r.output)==(source,output)),None)
    if not match:
        return {"status":"REJECT_UNSUPPORTED_OR_UNSAFE","source":source,"output":output,
                "reason":"No appropriate qualified pathway in registry.",
                "dispatch_authorized":False}
    if claimed is None: claimed={}
    if not isinstance(claimed,dict):raise ValueError("Claims must be a dictionary.")
    missing=[x for x in REQUIRED if claimed.get(x) is not True]
    # Self-attestation does not convert into a real independent permission or fuel certificate.
    return {"schema":"ghot.resource-bank-proposal/v0","proposal":asdict(match),
            "status":"HOLD_MISSING_EVIDENCE" if missing else "HOLD_INDEPENDENT_REVIEW",
            "missing":missing,"actual_inventory":False,"actual_transfer":False,
            "operator_enrolled":False,"fuel_certified":False,"output_energy_measured":False,
            "dispatch_authorized":False}

def validate()->dict:
    unique={(r.source,r.output) for r in ROUTES}
    if len(unique)!=len(ROUTES) or any(r.output in REJECTED for r in ROUTES):
        raise AssertionError("Unsafe or duplicated route.")
    if any(r.source=="edible" and r.destination!="people" for r in ROUTES):
        raise AssertionError("Food rescue must come first.")
    if any(r.source=="plastic" and r.output!="recycled_material" for r in ROUTES):
        raise AssertionError("Plastic is not a household heating fuel.")
    if any(r.source=="cooking_oil" and r.processor!="professional_refiner" for r in ROUTES):
        raise AssertionError("Raw cooking oil is not specified biodiesel.")
    return {"schema":"ghot.resource-bank-registry/v0",
            "route_count":len(ROUTES),"research_only":True,
            "verified_inventory_count":0,"enrolled_operators":0,
            "actual_deliveries":0,"no_hardware_controls":True}

if __name__=="__main__":
    print(json.dumps({"registry":validate(),"samples":[
        route("edible","qualified_biogas"),
        route("scraps","qualified_biogas"),
        route("cooking_oil","specified_biodiesel"),
        route("plastic","home_plastic_fuel"),
        route("solar","metered_electricity")]},indent=2))

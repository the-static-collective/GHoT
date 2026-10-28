#!/usr/bin/env python3
"""THERMAL-WALL-SKIN-004 | illustrative closed-energy wall-panel routing.

Three distinct branches: radiant wall heat distribution, PCM storage wall,
and an experimental low-gradient wall TEG. NEVER a hardware design.
No wall cutting, plumbing, pump, pressure, combustion, or building controls.
GHoT receives synthetic observations only; no device command is issued.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
import math
from thermal_cascade_sim import simulate as upstream_simulate

@dataclass(frozen=True)
class PanelAssumptions:
    hours: int = 24
    masonry_share: float = 0.60
    radiant_share: float = 0.20
    pcm_share: float = 0.15
    experimental_teg_share: float = 0.05
    masonry_discharge_hourly: float = 0.065
    radiant_discharge_hourly: float = 0.28
    pcm_discharge_hourly: float = 0.085
    masonry_indoor_capture: float = 0.90
    radiant_indoor_capture: float = 0.95
    pcm_indoor_capture: float = 0.92
    wall_teg_electric_conversion: float = 0.005
    wall_teg_charge_efficiency: float = 0.80
    assumed_heat_demand_kwh_hourly: float = 0.9
    background_task_wh: float = 30.0
    existing_battery_reserve_kwh: float = 0.20

def check(p: PanelAssumptions) -> None:
    d=asdict(p)
    if type(p.hours) is not int or not 1 <= p.hours <= 168:
        raise ValueError("hours must be integer 1..168")
    for name,val in d.items():
        if name=="hours": continue
        if isinstance(val,bool) or not isinstance(val,(int,float)) or not math.isfinite(val) or val<0:
            raise ValueError("numeric assumptions must be finite nonnegative")
    fractions = ("masonry_share","radiant_share","pcm_share","experimental_teg_share")
    if abs(sum(d[k] for k in fractions)-1.0)>1e-9:
        raise ValueError("Every joule must be allocated exactly once among branches")
    rates = ("masonry_discharge_hourly","radiant_discharge_hourly","pcm_discharge_hourly",
             "masonry_indoor_capture","radiant_indoor_capture","pcm_indoor_capture",
             "wall_teg_electric_conversion","wall_teg_charge_efficiency")
    if any(d[k]>1 for k in rates):
        raise ValueError("Discharge/transfer/conversion rates cannot exceed 1")
    if p.assumed_heat_demand_kwh_hourly<=0 or p.background_task_wh<=0:
        raise ValueError("heat demand and optional task cost must be positive")

def simulate(p: PanelAssumptions=PanelAssumptions()) -> dict:
    check(p)
    source=upstream_simulate()["first_law_kwh"]
    fuel=source["fuel_input"]
    mass=source["heat_to_mass_bank"]*p.masonry_share
    radiant=source["heat_to_mass_bank"]*p.radiant_share
    pcm=source["heat_to_mass_bank"]*p.pcm_share
    teg_heat=source["heat_to_mass_bank"]*p.experimental_teg_share

    # A TEG would consume an indoor-to-outdoor gradient; treating all
    # residual wall heat as OUTDOOR LOSS is conservative and highlights
    # how it can cause a thermal-bridge penalty instead of useful recovery.
    teg_gross=teg_heat*p.wall_teg_electric_conversion
    teg_battery=teg_gross*p.wall_teg_charge_efficiency
    teg_charge_loss=teg_gross-teg_battery
    teg_outdoor_loss=teg_heat-teg_gross+teg_charge_loss

    room=source["direct_heat"]
    outdoors=source["unutilized_energy"]+teg_outdoor_loss
    battery=source["battery_energy_after_conversion"]+teg_battery
    mechanical=source["potential_delivered_work_from_buffer"]
    initial_battery=battery
    delivered={"masonry":0.0,"radiant":0.0,"pcm":0.0}
    rows=[]
    for hour in range(1,p.hours+1):
        hr={}
        for name in ("masonry","radiant","pcm"):
            stored=mass if name=="masonry" else radiant if name=="radiant" else pcm
            rate=getattr(p,f"{name}_discharge_hourly")
            capture=getattr(p,f"{name}_indoor_capture")
            release=stored*rate
            gained=release*capture
            lost=release-gained
            delivered[name]+=gained
            room+=gained
            outdoors+=lost
            hr[name+"_indoor_kwh"]=round(gained,6)
            if name=="masonry": mass=stored-release
            elif name=="radiant": radiant=stored-release
            else: pcm=stored-release

        hourly_delivered=sum(hr[k] for k in hr)
        unmet=max(0.0,p.assumed_heat_demand_kwh_hourly-hourly_delivered)
        # This is GHoT decision SUPPORT, not a command to HVAC or heater.
        spend=p.background_task_wh/1000
        reserve=p.existing_battery_reserve_kwh
        action="RUN_ELIGIBLE" if unmet>0 and battery+1e-10>=reserve+spend else "HOLD"
        if action=="RUN_ELIGIBLE":
            # Assume optional computing runs inside conditioned envelope;
            # electricity becomes indoor low-grade heat, counted ONCE.
            battery-=spend
            room+=spend
        rows.append({"hour":hour,"synthetic_observation":True,"mass_kwh":round(mass,6),
                     "radiant_wall_kwh":round(radiant,6),"pcm_wall_kwh":round(pcm,6),
                     "battery_kwh":round(battery,6),"room_heat_from_wall_panels_kwh":round(hr["radiant_indoor_kwh"]+hr["pcm_indoor_kwh"],6),
                     "ghot_nonessential_compute_advice":action,
                     "heating_need_before_compute_kwh":round(unmet,6)})
    stock_remaining=mass+radiant+pcm
    closure=room+outdoors+battery+mechanical+stock_remaining
    if not math.isclose(closure,fuel,rel_tol=0,abs_tol=1e-7):
        raise AssertionError("energy conservation failure")
    return {"schema":"ghot.thermal-wall-skin/v0",
            "mode":"synthetic_no_hardware_no_installations",
            "inputs":asdict(p),
            "panel_meanings":{
                "radiant":"redistributes existing heat, no new energy or electricity",
                "pcm":"delays and buffers existing heat, needs appropriate thermal cycles",
                "experimental_teg":"uses a thermal gradient, could increase envelope heat loss; no measured output",
            },
            "energy_kwh":{
                "fuel_initial":fuel,
                "initial_battery_before_wall_teg":source["battery_energy_after_conversion"],
                "initial_battery_after_wall_teg":round(initial_battery,8),
                "experimental_teg_wall_heat_diverted":round(teg_heat,8),
                "experimental_teg_wall_battery_recovered":round(teg_battery,8),
                "experimental_teg_wall_loss_outdoors":round(teg_outdoor_loss,8),
                "room_heat_total":round(room,8),
                "outdoors_lost_total":round(outdoors,8),
                "battery_remaining":round(battery,8),
                "mechanical_work_remaining":round(mechanical,8),
                "all_panels_and_mass_heat_remaining":round(stock_remaining,8),
                "closure_error":round(fuel-closure,9),
            },
            "room_heat_from_branches_kwh":{k:round(v,8) for k,v in delivered.items()},
            "safety_rules":[
                "No wall piping, pressurized circuits, fire, pumps, wall penetrations or actuators modeled.",
                "No automatic space-heating controls; appliance life safety remains independent.",
                "A wall TEG requires engineering review for electrical isolation, thermal bridging, moisture, and fire ratings.",
                "PCM panel installation requires building fire/moisture code review; no self-heating or endless storage.",
                "No human household, site, utility or project partner is enrolled.",
            ],
            "hourly":rows}
if __name__=="__main__":
    print(json.dumps(simulate(),indent=2,sort_keys=True))

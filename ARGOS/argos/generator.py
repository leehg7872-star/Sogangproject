from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .geo import point_to_route_km
from .graph import OntologyGraph


BASES = [
    ("K-2", "Daegu AB", 35.894, 128.659),
    ("K-3", "Gunsan AB", 35.904, 126.616),
    ("K-5", "Osan AB", 37.090, 127.030),
    ("K-6", "Seoul AB", 37.445, 127.114),
    ("K-7", "Gwangju AB", 35.126, 126.810),
    ("K-8", "Suwon AB", 37.239, 127.007),
    ("K-9", "Gangneung AB", 37.753, 128.943),
    ("K-10", "Jungwon AB", 37.030, 127.887),
]

AIRFRAMES = ["F-35A", "F-15K", "KF-16", "FA-50", "KC-330", "E-737"]
MISSION_TYPES = ["strike", "recon", "cap", "tanker", "escort", "airlift"]
SENSOR_TYPES = ["RADAR", "EO-IR", "SIGINT"]
SATELLITES = ["KOMPSAT-3A", "KOMPSAT-5", "KOMPSAT-6", "ANASIS-II", "SAR-1", "SAR-2", "SAR-3", "SAR-4", "EO-1", "EO-2", "IR-1", "IR-2"]
START = datetime(2026, 7, 4, 0, 0, tzinfo=timezone.utc)


def iso(minutes: int) -> str:
    return (START + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def add_obj(objects: dict[str, dict[str, dict[str, Any]]], object_type: str, object_id: str, **props: Any) -> dict[str, Any]:
    record = {"id": object_id, "type": object_type, **props, "marking": "SYNTHETIC"}
    objects.setdefault(object_type, {})[object_id] = record
    return record


def add_link(links: list[dict[str, Any]], link_type: str, from_type: str, from_id: str, to_type: str, to_id: str, **props: Any) -> None:
    links.append({"type": link_type, "fromType": from_type, "fromId": from_id, "toType": to_type, "toId": to_id, **props})


def jitter(rng: random.Random, value: float, spread: float) -> float:
    return round(value + rng.uniform(-spread, spread), 5)


SCENARIO_SEEDS = {
    "S0": 20260704,
    "S1": 20260711,
    "S2": 20260718,
    "S3": 20260725,
}


def build_graph(seed: int = 20260704, scenario: str = "S0") -> OntologyGraph:
    scenario = scenario.upper()
    if scenario not in SCENARIO_SEEDS:
        raise ValueError(f"unknown scenario {scenario}; expected one of {', '.join(SCENARIO_SEEDS)}")
    rng = random.Random(seed)
    objects: dict[str, dict[str, dict[str, Any]]] = {}
    links: list[dict[str, Any]] = []

    for base_id, name, lat, lon in BASES:
        add_obj(objects, "AirBase", base_id, name=name, lat=lat, lon=lon, protection=rng.choice(["A", "B", "C"]), capacity=rng.randint(48, 96))
        for r in range(2):
            rwy_id = f"{base_id}-RWY-{r + 1}"
            add_obj(objects, "Runway", rwy_id, baseId=base_id, heading=rng.choice([90, 180, 270, 360]), lengthM=rng.randint(2400, 3400), surfaceStatus=rng.choice(["open", "open", "open", "maintenance"]))
            add_link(links, "HAS_RUNWAY", "AirBase", base_id, "Runway", rwy_id)

    squadron_ids = []
    for idx in range(16):
        base_id = BASES[idx % len(BASES)][0]
        sqdn_id = f"SQ-{idx + 1:02d}"
        airframe = AIRFRAMES[idx % len(AIRFRAMES)]
        mission_type = MISSION_TYPES[idx % len(MISSION_TYPES)]
        squadron_ids.append(sqdn_id)
        add_obj(objects, "Squadron", sqdn_id, name=f"{idx + 1:02d} Tactical Squadron", airframe=airframe, baseId=base_id, manning=rng.randint(85, 115), missionType=mission_type)
        add_link(links, "BASED_AT", "Squadron", sqdn_id, "AirBase", base_id)

    aircraft_ids = []
    for idx in range(240):
        sqdn_id = squadron_ids[idx % len(squadron_ids)]
        sqdn = objects["Squadron"][sqdn_id]
        tail_no = f"{sqdn['airframe'].replace('-', '')}-{idx + 1:03d}"
        status = rng.choices(["ready", "maintenance", "flying"], weights=[68, 18, 14], k=1)[0]
        readiness = 0 if status == "maintenance" else rng.randint(65, 100)
        aircraft_ids.append(tail_no)
        add_obj(objects, "Aircraft", tail_no, airframe=sqdn["airframe"], status=status, loadout=rng.choice(["A2A", "A2G", "ISR", "TANKER", "TRAINING"]), fuelPct=rng.randint(35, 100), readiness=readiness)
        add_link(links, "ASSIGNED_TO", "Aircraft", tail_no, "Squadron", sqdn_id)

    for idx in range(360):
        pilot_id = f"PLT-{idx + 1:04d}"
        sqdn_id = squadron_ids[idx % len(squadron_ids)]
        tail_no = aircraft_ids[idx % len(aircraft_ids)]
        quals = sorted(rng.sample(["night", "low-level", "instructor", "tanker", "strike", "recon"], k=rng.randint(2, 4)))
        add_obj(objects, "Pilot", pilot_id, callsign=f"P{idx + 1:03d}", quals=quals, flightHours=rng.randint(240, 2100), status=rng.choice(["available", "available", "crew-rest", "assigned"]))
        add_link(links, "PILOT_IN_SQUADRON", "Pilot", pilot_id, "Squadron", sqdn_id)
        add_link(links, "PILOT_ASSIGNED", "Pilot", pilot_id, "Aircraft", tail_no)

    issues = ["hydraulic", "avionics", "engine trend", "radar cooling", "tire wear", "scheduled inspection"]
    for idx in range(1200):
        tail_no = aircraft_ids[idx % len(aircraft_ids)]
        status = rng.choices(["open", "closed", "deferred"], weights=[16, 70, 14], k=1)[0]
        severity = rng.choice(["low", "medium", "high"])
        maint_id = f"MX-{idx + 1:05d}"
        add_obj(objects, "MaintRecord", maint_id, tailNo=tail_no, issue=rng.choice(issues), severity=severity, status=status, openedAt=iso(rng.randint(0, 1380)))
        add_link(links, "MAINT_TARGET", "MaintRecord", maint_id, "Aircraft", tail_no)

    for idx in range(3):
        ato_id = f"ATO-D{idx}"
        add_obj(objects, "ATO", ato_id, day=f"D{idx}", status="published")

    target_ids = []
    for idx in range(300):
        tgt_id = f"T-{idx + 1:03d}"
        base = BASES[idx % len(BASES)]
        target_ids.append(tgt_id)
        add_obj(objects, "Target", tgt_id, name=f"Target {idx + 1:03d}", lat=jitter(rng, base[2] + rng.uniform(-1.2, 1.2), 0.12), lon=jitter(rng, base[3] + rng.uniform(-1.2, 1.2), 0.12), category=rng.choice(["radar", "logistics", "bridge", "air-defense", "command"]), priority=rng.randint(1, 5), bdaStatus=rng.choice(["unknown", "planned", "assessed"]))

    zone_ids = []
    for idx in range(64):
        base = BASES[idx % len(BASES)]
        zone_id = f"Z-{idx + 1:03d}"
        zone_ids.append(zone_id)
        add_obj(objects, "AirspaceZone", zone_id, name=f"Corridor {idx + 1:03d}", lat=jitter(rng, base[2], 1.1), lon=jitter(rng, base[3], 1.1), radiusKm=rng.randint(25, 90), floorFt=rng.choice([0, 5000, 10000]), ceilingFt=rng.choice([18000, 26000, 40000]), status=rng.choice(["active", "active", "restricted"]))

    mission_ids = []
    mission_total = 2400 if scenario == "S1" else 1800
    for idx in range(mission_total):
        msn_id = f"MSN-{idx + 1:04d}"
        mission_ids.append(msn_id)
        dep = BASES[idx % len(BASES)]
        rec = BASES[(idx + 2) % len(BASES)]
        tgt_id = target_ids[idx % len(target_ids)]
        tgt = objects["Target"][tgt_id]
        mid = {"lat": jitter(rng, (dep[2] + tgt["lat"]) / 2, 0.35), "lon": jitter(rng, (dep[3] + tgt["lon"]) / 2, 0.35)}
        route = [{"lat": dep[2], "lon": dep[3]}, mid, {"lat": tgt["lat"], "lon": tgt["lon"]}, {"lat": rec[2], "lon": rec[3]}]
        start_min = rng.randint(300, 1260)
        end_min = start_min + rng.randint(70, 240)
        mission_type = MISSION_TYPES[idx % len(MISSION_TYPES)]
        add_obj(objects, "Mission", msn_id, callsign=f"{rng.choice(['VIPER', 'HAWK', 'EAGLE', 'BONE', 'RAVEN'])}-{idx % 99 + 1:02d}", missionType=mission_type, route=route, start=iso(start_min), end=iso(end_min), status=rng.choice(["planned", "planned", "active", "complete"]))
        add_link(links, "TASKS", "ATO", "ATO-D0", "Mission", msn_id)
        add_link(links, "STRIKES", "Mission", msn_id, "Target", tgt_id)
        add_link(links, "DEPARTS_FROM", "Mission", msn_id, "AirBase", dep[0])
        add_link(links, "RECOVERS_AT", "Mission", msn_id, "AirBase", rec[0])
        add_link(links, "TRANSITS", "Mission", msn_id, "AirspaceZone", zone_ids[idx % len(zone_ids)])
        for offset in range(2):
            tail_no = aircraft_ids[(idx * 2 + offset) % len(aircraft_ids)]
            add_link(links, "FLOWN_BY", "Mission", msn_id, "Aircraft", tail_no)
        if idx % 9 == 0:
            add_link(links, "ESCORTS", "Mission", msn_id, "Mission", mission_ids[max(0, idx - 1)])
        if idx % 13 == 0:
            add_link(links, "REFUELS", "Mission", msn_id, "Mission", mission_ids[max(0, idx - 2)])

    sam_ids = []
    for idx in range(28):
        base = BASES[idx % len(BASES)]
        sam_id = f"SAM-{idx + 1:03d}"
        sam_ids.append(sam_id)
        add_obj(objects, "SAMSite", sam_id, system=rng.choice(["SA-20", "SA-21", "SA-17", "KN-06"]), lat=jitter(rng, base[2], 1.7), lon=jitter(rng, base[3], 1.7), rangeKm=rng.choice([90, 150, 220, 300, 380]), status=rng.choice(["active", "mobile", "suspected"]))
        zone_id = zone_ids[idx % len(zone_ids)]
        add_link(links, "THREAT_RING", "SAMSite", sam_id, "AirspaceZone", zone_id)

    for idx in range(1000):
        trk_id = f"TRK-{idx + 1:05d}"
        base = BASES[idx % len(BASES)]
        add_obj(objects, "Track", trk_id, lat=jitter(rng, base[2], 2.0), lon=jitter(rng, base[3], 2.0), speedKt=rng.randint(90, 560), heading=rng.randint(0, 359), identity=rng.choice(["unknown", "friendly", "suspect", "neutral"]), lastSeen=iso(rng.randint(0, 1430)))

    for idx in range(80):
        base = BASES[idx % len(BASES)]
        snsr_id = f"SNSR-{idx + 1:03d}"
        add_obj(objects, "Sensor", snsr_id, sensorType=SENSOR_TYPES[idx % len(SENSOR_TYPES)], lat=jitter(rng, base[2], 0.25), lon=jitter(rng, base[3], 0.25), rangeKm=rng.randint(140, 520), status=rng.choice(["online", "online", "degraded"]))
        add_link(links, "SENSOR_AT", "Sensor", snsr_id, "AirBase", base[0])

    for idx in range(480):
        base_id = BASES[idx % len(BASES)][0]
        wx_id = f"WX-{idx + 1:05d}"
        add_obj(objects, "WeatherReport", wx_id, baseId=base_id, observedAt=iso(idx * 3), ceilingFt=rng.randint(600, 35000), windKt=rng.randint(0, 45), status=rng.choice(["green", "green", "yellow", "red"]))
        add_link(links, "WX_CONSTRAINS", "WeatherReport", wx_id, "AirBase", base_id)

    for idx, name in enumerate(SATELLITES):
        norad = f"58{idx + 1:03d}"
        add_obj(objects, "Satellite", norad, name=name, tle=f"1 {norad}U SYNTHETIC\n2 {norad} 97.7 120.0 001 90.0 270.0 14.2", sensorType=rng.choice(["SAR", "EO", "IR", "COMMS"]), status=rng.choice(["nominal", "nominal", "tasked"]))
        for offset in range(30):
            add_link(links, "COVERS", "Satellite", norad, "Target", target_ids[(idx * 30 + offset) % len(target_ids)], windowStart=iso(360 + offset * 12), windowEnd=iso(366 + offset * 12))

    for idx in range(10):
        base = BASES[idx % len(BASES)]
        gs_id = f"GS-{idx + 1:03d}"
        add_obj(objects, "GroundStation", gs_id, name=f"Ground Station {idx + 1}", lat=jitter(rng, base[2], 0.8), lon=jitter(rng, base[3], 0.8), band=rng.choice(["X", "S", "Ka"]), status=rng.choice(["available", "available", "limited"]))
        for sat_id in list(objects["Satellite"])[:8]:
            add_link(links, "DOWNLINKS", "Satellite", sat_id, "GroundStation", gs_id)

    threat_total = 70 if scenario == "S2" else 45
    expected_impacts: dict[str, list[str]] = {}
    for idx in range(threat_total):
        sam_id = sam_ids[idx % len(sam_ids)]
        sam = objects["SAMSite"][sam_id]
        tev_id = f"TEV-{idx + 1:04d}"
        add_obj(objects, "ThreatEvent", tev_id, eventType=rng.choice(["SAM_RADAR_EMIT", "GPS_JAMMING", "MISSILE_LAUNCH_WARNING"]), lat=sam["lat"], lon=sam["lon"], severity=rng.choice(["medium", "high", "critical"]), firstSeen=iso(420 + idx * 9), status="active")
        add_link(links, "SOURCE_SITE", "ThreatEvent", tev_id, "SAMSite", sam_id)
        add_link(links, "RELATED_TRACK", "ThreatEvent", tev_id, "Track", f"TRK-{idx + 1:05d}")
        add_link(links, "DETECTED", "Sensor", f"SNSR-{idx % 80 + 1:03d}", "ThreatEvent", tev_id)
        ranked_impacts = sorted(
            (
                (point_to_route_km(float(sam["lat"]), float(sam["lon"]), mission["route"]), mission["id"])
                for mission in objects["Mission"].values()
            ),
            key=lambda item: item[0],
        )
        expected = [mission_id for _, mission_id in ranked_impacts[:2]]
        objects["ThreatEvent"][tev_id]["expected_impact"] = expected
        expected_impacts[tev_id] = expected

    satellite_ids = list(objects["Satellite"])
    space_total = 40 if scenario == "S3" else 20
    for idx in range(space_total):
        sat_id = satellite_ids[idx % len(satellite_ids)]
        sev_id = f"SEV-{idx + 1:04d}"
        add_obj(objects, "SpaceEvent", sev_id, eventType=rng.choice(["CONJUNCTION", "MANEUVER", "RF_INTERFERENCE", "GROUND_OUTAGE"]), satelliteId=sat_id, tca=iso(900 + idx * 17), missKm=round(rng.uniform(0.2, 9.5), 2), severity=rng.choice(["medium", "high", "critical"]))
        add_link(links, "SPACE_TARGETS", "SpaceEvent", sev_id, "Satellite", sat_id)
        coverage_links = [link for link in links if link["type"] == "COVERS" and link["fromId"] == sat_id]
        objects["SpaceEvent"][sev_id]["expected_impact"] = [link["toId"] for link in coverage_links[:5]]

    audit = [{
        "at": iso(0),
        "actor": "system",
        "action": "GenerateScenario",
        "detail": f"{scenario} synthetic scenario",
        "scenario": scenario,
        "seed": seed,
    }]
    return OntologyGraph(objects, links, audit)


def generate(path: str | Path, seed: int | None = None, scenario: str = "S0") -> OntologyGraph:
    scenario = scenario.upper()
    if seed is None:
        seed = SCENARIO_SEEDS.get(scenario, SCENARIO_SEEDS["S0"])
    graph = build_graph(seed=seed, scenario=scenario)
    graph.save(path)
    return graph


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/argos_graph.json")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--scenario", choices=sorted(SCENARIO_SEEDS), default="S0")
    args = parser.parse_args()
    graph = generate(args.out, seed=args.seed, scenario=args.scenario)
    print(json.dumps(graph.stats(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

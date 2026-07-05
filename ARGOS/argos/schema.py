from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ObjectType:
    name: str
    pk: str
    properties: tuple[str, ...]


OBJECT_TYPES: dict[str, ObjectType] = {
    "AirBase": ObjectType("AirBase", "baseId", ("name", "lat", "lon", "protection", "capacity")),
    "Runway": ObjectType("Runway", "rwyId", ("baseId", "heading", "lengthM", "surfaceStatus")),
    "Squadron": ObjectType("Squadron", "sqdnId", ("name", "airframe", "baseId", "manning", "missionType")),
    "Aircraft": ObjectType("Aircraft", "tailNo", ("airframe", "status", "loadout", "fuelPct", "readiness")),
    "Pilot": ObjectType("Pilot", "pilotId", ("callsign", "quals", "flightHours", "status")),
    "MaintRecord": ObjectType("MaintRecord", "maintId", ("tailNo", "issue", "severity", "status", "openedAt")),
    "ATO": ObjectType("ATO", "atoId", ("day", "status")),
    "Mission": ObjectType("Mission", "msnId", ("callsign", "missionType", "route", "start", "end", "status")),
    "Target": ObjectType("Target", "tgtId", ("name", "lat", "lon", "category", "priority", "bdaStatus")),
    "SAMSite": ObjectType("SAMSite", "samId", ("system", "lat", "lon", "rangeKm", "status")),
    "ThreatEvent": ObjectType("ThreatEvent", "tevId", ("eventType", "lat", "lon", "severity", "firstSeen", "status")),
    "Track": ObjectType("Track", "trkId", ("lat", "lon", "speedKt", "heading", "identity", "lastSeen")),
    "Satellite": ObjectType("Satellite", "noradId", ("name", "tle", "sensorType", "status")),
    "GroundStation": ObjectType("GroundStation", "gsId", ("name", "lat", "lon", "band", "status")),
    "SpaceEvent": ObjectType("SpaceEvent", "sevId", ("eventType", "satelliteId", "tca", "missKm", "severity")),
    "Sensor": ObjectType("Sensor", "snsrId", ("sensorType", "lat", "lon", "rangeKm", "status")),
    "WeatherReport": ObjectType("WeatherReport", "wxId", ("baseId", "observedAt", "ceilingFt", "windKt", "status")),
    "AirspaceZone": ObjectType("AirspaceZone", "zoneId", ("name", "lat", "lon", "radiusKm", "floorFt", "ceilingFt", "status")),
}


LINK_TYPES: tuple[tuple[str, str, str], ...] = (
    ("ASSIGNED_TO", "Aircraft", "Squadron"),
    ("BASED_AT", "Squadron", "AirBase"),
    ("PILOT_ASSIGNED", "Pilot", "Aircraft"),
    ("PILOT_IN_SQUADRON", "Pilot", "Squadron"),
    ("MAINT_TARGET", "MaintRecord", "Aircraft"),
    ("HAS_RUNWAY", "AirBase", "Runway"),
    ("FLOWN_BY", "Mission", "Aircraft"),
    ("TASKS", "ATO", "Mission"),
    ("STRIKES", "Mission", "Target"),
    ("DEPARTS_FROM", "Mission", "AirBase"),
    ("RECOVERS_AT", "Mission", "AirBase"),
    ("TRANSITS", "Mission", "AirspaceZone"),
    ("ESCORTS", "Mission", "Mission"),
    ("REFUELS", "Mission", "Mission"),
    ("THREAT_RING", "SAMSite", "AirspaceZone"),
    ("SOURCE_SITE", "ThreatEvent", "SAMSite"),
    ("IMPACTS", "ThreatEvent", "Mission"),
    ("RELATED_TRACK", "ThreatEvent", "Track"),
    ("DETECTED", "Sensor", "ThreatEvent"),
    ("SENSOR_AT", "Sensor", "AirBase"),
    ("WX_CONSTRAINS", "WeatherReport", "AirBase"),
    ("COVERS", "Satellite", "Target"),
    ("DOWNLINKS", "Satellite", "GroundStation"),
    ("SPACE_TARGETS", "SpaceEvent", "Satellite"),
)


ACTION_TYPES: tuple[str, ...] = (
    "CreateThreatEvent",
    "RetaskMission",
    "DivertAircraft",
    "AssignInterceptor",
    "RequestSatCollection",
    "UpdateReadiness",
    "RecordDecision",
)


FUNCTIONS: tuple[str, ...] = (
    "fnThreatIntersect",
    "fnCoverageWindow",
    "fnReadinessRollup",
    "fnDeconflict",
)


ACTION_SPECS: dict[str, dict[str, Any]] = {
    "CreateThreatEvent": {"authority": "situation-officer", "parameters": ("eventType", "lat", "lon", "severity")},
    "RetaskMission": {"authority": "mission-planner", "parameters": ("missionIds", "targetId", "route")},
    "DivertAircraft": {"authority": "mission-planner", "parameters": ("missionIds", "candidateBase")},
    "AssignInterceptor": {"authority": "air-defense-officer", "parameters": ("threatEventId", "priority")},
    "RequestSatCollection": {"authority": "space-operations", "parameters": ("satelliteId", "targetIds")},
    "UpdateReadiness": {"authority": "maintenance-control", "parameters": ("assetId", "status")},
    "RecordDecision": {"authority": "battle-captain", "parameters": ("decision", "rationale")},
}


FUNCTION_SPECS: dict[str, dict[str, Any]] = {
    "fnThreatIntersect": {
        "input": "ThreatEvent",
        "output": "ranked Mission impacts with distanceKm and severity",
    },
    "fnCoverageWindow": {
        "input": "Target and/or Satellite filters",
        "output": "Satellite to Target visibility windows",
    },
    "fnReadinessRollup": {
        "input": "Aircraft, Squadron, AirBase readiness links",
        "output": "base-level readiness rate",
    },
    "fnDeconflict": {
        "input": "Mission route and AirspaceZone restrictions",
        "output": "clear/conflict status with conflicting zones",
    },
}


def schema_summary() -> dict[str, object]:
    return {
        "objectTypes": {name: {"pk": spec.pk, "properties": list(spec.properties)} for name, spec in OBJECT_TYPES.items()},
        "linkTypes": [{"name": n, "from": src, "to": dst} for n, src, dst in LINK_TYPES],
        "actionTypes": {name: ACTION_SPECS[name] for name in ACTION_TYPES},
        "functions": {name: FUNCTION_SPECS[name] for name in FUNCTIONS},
    }


def ontology_manifest() -> dict[str, Any]:
    return {
        "name": "ARGOS",
        "description": "Aerospace Reasoning & Graph Ontology System synthetic ontology",
        "classification": "PUBLIC SYNTHETIC DATA ONLY",
        **schema_summary(),
    }

from __future__ import annotations

from typing import Any

from .graph import OntologyGraph
from .reasoning import ArgosAgent


def call_function(graph: OntologyGraph, name: str, **kwargs: Any) -> dict[str, Any]:
    agent = ArgosAgent(graph)
    if name == "fnThreatIntersect":
        event_id = str(kwargs["eventId"])
        event = graph.get("ThreatEvent", event_id)
        if not event:
            return {"ok": False, "error": f"ThreatEvent {event_id} not found"}
        return {"ok": True, "results": agent.fn_threat_intersect(event)}
    if name == "fnCoverageWindow":
        return {
            "ok": True,
            "results": agent.fn_coverage_window(
                target_id=kwargs.get("targetId"),
                satellite_id=kwargs.get("satelliteId"),
            ),
        }
    if name == "fnReadinessRollup":
        return {"ok": True, "results": agent.fn_readiness_rollup()}
    if name == "fnDeconflict":
        return {"ok": True, "results": agent.fn_deconflict(str(kwargs["missionId"]))}
    return {"ok": False, "error": f"unknown function {name}"}


def evaluate_expected_impacts(graph: OntologyGraph, limit: int = 30) -> dict[str, Any]:
    agent = ArgosAgent(graph)
    scored = []
    for event in graph.all("ThreatEvent")[:limit]:
        expected = set(event.get("expected_impact", []))
        if not expected:
            continue
        ranked = [item["mission"]["id"] for item in agent.fn_threat_intersect(event, max_results=30)]
        actual = set(ranked)
        actual_at_k = set(ranked[: max(len(expected), 1)])
        tp = len(expected & actual)
        tp_at_k = len(expected & actual_at_k)
        recall = tp / max(len(expected), 1)
        precision = tp_at_k / max(len(actual_at_k), 1)
        scored.append({"eventId": event["id"], "recall": recall, "precision": precision, "expected": sorted(expected), "actualTop": ranked[:10]})
    if not scored:
        return {"events": [], "recall": 0.0, "precision": 0.0}
    return {
        "events": scored,
        "recall": round(sum(item["recall"] for item in scored) / len(scored), 3),
        "precision": round(sum(item["precision"] for item in scored) / len(scored), 3),
    }

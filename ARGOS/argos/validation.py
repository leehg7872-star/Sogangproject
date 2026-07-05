from __future__ import annotations

from typing import Any

from .graph import OntologyGraph
from .schema import LINK_TYPES, OBJECT_TYPES


def validate_graph(graph: OntologyGraph) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for object_type, spec in OBJECT_TYPES.items():
        if object_type not in graph.objects:
            errors.append(f"missing object type {object_type}")
            continue
        for object_id, obj in graph.objects[object_type].items():
            if obj.get("type") != object_type:
                errors.append(f"{object_type}:{object_id} has mismatched type {obj.get('type')}")
            if obj.get("id") != object_id:
                errors.append(f"{object_type}:{object_id} has mismatched id {obj.get('id')}")
            for prop in spec.properties:
                if prop not in obj:
                    errors.append(f"{object_type}:{object_id} missing property {prop}")

    link_specs = {name: (src, dst) for name, src, dst in LINK_TYPES}
    for idx, link in enumerate(graph.links):
        link_type = link.get("type")
        if link_type not in link_specs:
            errors.append(f"link[{idx}] unknown type {link_type}")
            continue
        src_type, dst_type = link_specs[link_type]
        if link.get("fromType") != src_type or link.get("toType") != dst_type:
            errors.append(
                f"link[{idx}] {link_type} expected {src_type}->{dst_type}, got {link.get('fromType')}->{link.get('toType')}"
            )
        if not graph.get(src_type, str(link.get("fromId"))):
            errors.append(f"link[{idx}] missing source {src_type}:{link.get('fromId')}")
        if not graph.get(dst_type, str(link.get("toId"))):
            errors.append(f"link[{idx}] missing target {dst_type}:{link.get('toId')}")

    stats = graph.stats()
    if stats["objectCount"] < 5000:
        warnings.append("object count is below white-paper target 5000")
    if stats["linkCount"] < 15000:
        warnings.append("link count is below white-paper target 15000")

    return {
        "ok": not errors,
        "errorCount": len(errors),
        "warningCount": len(warnings),
        "errors": errors[:100],
        "warnings": warnings,
        "stats": stats,
    }

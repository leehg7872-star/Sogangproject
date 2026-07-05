from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


ObjectRecord = dict[str, Any]
LinkRecord = dict[str, Any]


class OntologyGraph:
    def __init__(self, objects: dict[str, dict[str, ObjectRecord]], links: list[LinkRecord], audit: list[dict[str, Any]] | None = None):
        self.objects = objects
        self.links = links
        self.audit = audit or []
        self.out_links: dict[tuple[str, str], list[LinkRecord]] = defaultdict(list)
        self.in_links: dict[tuple[str, str], list[LinkRecord]] = defaultdict(list)
        for link in links:
            self.out_links[(link["fromType"], link["fromId"])].append(link)
            self.in_links[(link["toType"], link["toId"])].append(link)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "OntologyGraph":
        return cls(payload["objects"], payload["links"], payload.get("audit", []))

    @classmethod
    def load(cls, path: str | Path) -> "OntologyGraph":
        return cls.from_payload(json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_payload(), ensure_ascii=False, indent=2), encoding="utf-8")

    def to_payload(self) -> dict[str, Any]:
        return {"objects": self.objects, "links": self.links, "audit": self.audit}

    def get(self, object_type: str, object_id: str) -> ObjectRecord | None:
        return self.objects.get(object_type, {}).get(object_id)

    def all(self, object_type: str) -> list[ObjectRecord]:
        return list(self.objects.get(object_type, {}).values())

    def outgoing(self, object_type: str, object_id: str, link_type: str | None = None) -> list[LinkRecord]:
        links = self.out_links.get((object_type, object_id), [])
        return [link for link in links if link_type is None or link["type"] == link_type]

    def incoming(self, object_type: str, object_id: str, link_type: str | None = None) -> list[LinkRecord]:
        links = self.in_links.get((object_type, object_id), [])
        return [link for link in links if link_type is None or link["type"] == link_type]

    def linked_objects(self, object_type: str, object_id: str, link_type: str | None = None, direction: str = "out") -> list[ObjectRecord]:
        links = self.outgoing(object_type, object_id, link_type) if direction == "out" else self.incoming(object_type, object_id, link_type)
        result = []
        for link in links:
            target_type = link["toType"] if direction == "out" else link["fromType"]
            target_id = link["toId"] if direction == "out" else link["fromId"]
            obj = self.get(target_type, target_id)
            if obj:
                result.append(obj)
        return result

    def bfs(self, start_type: str, start_id: str, max_depth: int = 3) -> list[ObjectRecord]:
        seen = {(start_type, start_id)}
        queue = deque([(start_type, start_id, 0)])
        found: list[ObjectRecord] = []
        while queue:
            object_type, object_id, depth = queue.popleft()
            obj = self.get(object_type, object_id)
            if obj:
                found.append(obj)
            if depth >= max_depth:
                continue
            adjacent = self.outgoing(object_type, object_id) + self.incoming(object_type, object_id)
            for link in adjacent:
                if link["fromType"] == object_type and link["fromId"] == object_id:
                    nxt = (link["toType"], link["toId"])
                else:
                    nxt = (link["fromType"], link["fromId"])
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt[0], nxt[1], depth + 1))
        return found

    def add_link(self, link: LinkRecord) -> None:
        self.links.append(link)
        self.out_links[(link["fromType"], link["fromId"])].append(link)
        self.in_links[(link["toType"], link["toId"])].append(link)

    def stats(self) -> dict[str, Any]:
        object_counts = {object_type: len(records) for object_type, records in sorted(self.objects.items())}
        return {
            "objectCount": sum(object_counts.values()),
            "linkCount": len(self.links),
            "objectCounts": object_counts,
        }


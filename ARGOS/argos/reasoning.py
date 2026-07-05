from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from .geo import haversine_km, point_to_route_km, severity_from_distance
from .graph import OntologyGraph
from .llm_gateway import LlmGateway, LlmRequest, default_gateway
from .schema import schema_summary


def chip(obj: dict[str, Any]) -> dict[str, str]:
    return {"type": obj["type"], "id": obj["id"], "label": obj.get("callsign") or obj.get("name") or obj["id"]}


class ArgosAgent:
    """Deterministic Korean natural-language interface over the ontology graph."""

    def __init__(self, graph: OntologyGraph, gateway: LlmGateway | None = None):
        self.graph = graph
        self.gateway = gateway or default_gateway()

    def fn_threat_intersect(self, event: dict[str, Any], max_results: int = 30) -> list[dict[str, Any]]:
        source_links = self.graph.outgoing("ThreatEvent", event["id"], "SOURCE_SITE")
        range_km = 220.0
        if source_links:
            site = self.graph.get("SAMSite", source_links[0]["toId"])
            if site:
                range_km = float(site["rangeKm"])

        impacts = []
        for mission in self.graph.all("Mission"):
            distance = point_to_route_km(float(event["lat"]), float(event["lon"]), mission["route"])
            if distance <= range_km:
                impacts.append({"mission": mission, "distanceKm": round(distance, 1), "severity": severity_from_distance(distance, range_km)})
        impacts.sort(key=lambda item: (item["distanceKm"], item["mission"]["start"]))
        return impacts[:max_results]

    def fn_coverage_window(self, target_id: str | None = None, satellite_id: str | None = None) -> list[dict[str, Any]]:
        windows = []
        for link in self.graph.links:
            if link["type"] != "COVERS":
                continue
            if target_id and link["toId"] != target_id:
                continue
            if satellite_id and link["fromId"] != satellite_id:
                continue
            sat = self.graph.get("Satellite", link["fromId"])
            target = self.graph.get("Target", link["toId"])
            if sat and target:
                windows.append({"satellite": sat, "target": target, "start": link.get("windowStart"), "end": link.get("windowEnd")})
        return sorted(windows, key=lambda item: item["start"] or "")[:50]

    def fn_readiness_rollup(self) -> list[dict[str, Any]]:
        by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for aircraft in self.graph.all("Aircraft"):
            sq_links = self.graph.outgoing("Aircraft", aircraft["id"], "ASSIGNED_TO")
            if not sq_links:
                continue
            sqdn = self.graph.get("Squadron", sq_links[0]["toId"])
            if sqdn:
                by_base[sqdn["baseId"]].append(aircraft)

        rollup = []
        for base_id, aircraft in by_base.items():
            ready = sum(1 for item in aircraft if item["status"] == "ready")
            base = self.graph.get("AirBase", base_id)
            rollup.append({"base": base, "ready": ready, "total": len(aircraft), "rate": round(ready / max(len(aircraft), 1), 3)})
        return sorted(rollup, key=lambda item: item["rate"], reverse=True)

    def fn_deconflict(self, mission_id: str) -> dict[str, Any]:
        mission = self.graph.get("Mission", mission_id)
        if not mission:
            return {"status": "unknown", "conflicts": []}
        conflicts = []
        for link in self.graph.outgoing("Mission", mission_id, "TRANSITS"):
            zone = self.graph.get("AirspaceZone", link["toId"])
            if zone and zone["status"] == "restricted":
                conflicts.append(zone)
        return {"status": "conflict" if conflicts else "clear", "conflicts": conflicts}

    def ask(self, question: str) -> dict[str, Any]:
        q = question.strip()
        normalized = q.lower()
        tokens = self._tokens(normalized)

        base_id = self._extract_base_id(q)
        if base_id and self._has_any(tokens, {"대대", "비행대", "squadron", "주둔"}):
            return self._answer_squadrons_at_base(base_id)

        if base_id and self._has_any(tokens, {"비행장", "기지", "활주로", "수용", "위치"}):
            return self._answer_base_status(base_id)

        object_hit = self._find_object_mention(q)
        if object_hit and self._has_any(tokens, {"상세", "정보", "상태", "어디", "위치", "보여", "조회"}):
            return self._answer_object_detail(object_hit[0], object_hit[1])

        if self._has_any(tokens, {"가동률", "가용", "readiness", "준비태세"}):
            return self._answer_readiness()

        if self._has_any(tokens, {"정비", "고장", "불가동"}) and self._has_any(tokens, {"대체", "교체", "임무", "ato"}):
            return self._answer_maintenance_mission_alternates()

        if self._has_any(tokens, {"위협", "threat", "sam", "방사", "영향", "위험"}):
            event_id = self._first_known_id(q, "ThreatEvent") or "TEV-0001"
            if self.graph.get("ThreatEvent", event_id):
                return self.watch_event("ThreatEvent", event_id)

        if self._has_any(tokens, {"우주", "위성", "수집", "coverage", "satellite"}):
            space_event = self._first_known_id(q, "SpaceEvent")
            if space_event and self._has_any(tokens, {"영향", "결심", "대응"}):
                return self.watch_event("SpaceEvent", space_event)
            return self._answer_satellite_coverage(q)

        if self._has_any(tokens, {"항적", "track", "미식별", "접근"}):
            return self._answer_tracks()

        if self._has_any(tokens, {"결심", "권고", "추천", "대응", "조치", "decide"}):
            space_event_id = self._first_known_id(q, "SpaceEvent")
            if space_event_id:
                return self.watch_event("SpaceEvent", space_event_id)
            event_id = self._first_known_id(q, "ThreatEvent") or "TEV-0001"
            event = self.graph.get("ThreatEvent", event_id)
            if event:
                impacts = self.fn_threat_intersect(event, max_results=12)
                actions = self.decide(event, impacts)
                text = f"{event_id} 기준 권고는 {', '.join(action['type'] for action in actions)}입니다. 모든 조치는 승인 후 실행됩니다."
                result = {"answer": text, "mode": "decide", "evidence": [chip(event)] + [chip(item["mission"]) for item in impacts[:3]], "actions": actions, "impacts": [_impact_payload(item) for item in impacts]}
                return self._gateway_payload(q, result)

        if self._has_any(tokens, {"aar", "사후", "검토", "보고서"}):
            aar = self.generate_aar()
            result = {"answer": aar["sections"]["overview"], "mode": "aar", "evidence": aar["evidence"], "aar": aar}
            return self._gateway_payload(q, result)

        if self._has_any(tokens, {"스키마", "온톨로지", "객체", "링크"}):
            summary = schema_summary()
            text = f"온톨로지는 객체 {len(summary['objectTypes'])}종, 링크 {len(summary['linkTypes'])}종, Action {len(summary['actionTypes'])}종, Function {len(summary['functions'])}종으로 구성됩니다."
            return self._answer(text, [], "schema")

        return self._unknown(
            "현재 온톨로지에서 직접 확인 가능한 질문으로 바꿔 답변할 수 있습니다. 예: 'K-2 비행장 상태', "
            "'미식별 항적 보여줘', 'TEV-0001 영향과 결심 권고', '정비 이슈 임무 대체 기체', 'T-001 위성 수집 창'."
        )

    def watch_event(self, object_type: str, object_id: str) -> dict[str, Any]:
        event = self.graph.get(object_type, object_id)
        if not event:
            return self._unknown("현재 온톨로지에서 이벤트를 확인할 수 없습니다.")

        if object_type == "ThreatEvent":
            impacts = self.fn_threat_intersect(event, max_results=12)
            for item in impacts[:8]:
                mission = item["mission"]
                existing = self.graph.outgoing("ThreatEvent", object_id, "IMPACTS")
                if not any(link["toId"] == mission["id"] for link in existing):
                    self.graph.add_link({"type": "IMPACTS", "fromType": "ThreatEvent", "fromId": object_id, "toType": "Mission", "toId": mission["id"], "severity": item["severity"], "distanceKm": item["distanceKm"]})
            text = f"{event['id']} 영향 분석: 임무 {len(impacts)}건이 위협 반경과 교차합니다. 최상위 영향은 " + ", ".join(
                f"{item['mission']['callsign']}({item['severity']}, {item['distanceKm']}km)" for item in impacts[:5]
            ) + "입니다."
            actions = self.decide(event, impacts)
            self._audit("WatchThreatEvent", f"{object_id} impacts={len(impacts)}")
            result = {"answer": text, "mode": "watch", "evidence": [chip(event)] + [chip(item["mission"]) for item in impacts[:5]], "impacts": [_impact_payload(item) for item in impacts], "actions": actions}
            return self._gateway_payload(f"Watch {object_id}", result)

        if object_type == "SpaceEvent":
            sat_links = self.graph.outgoing("SpaceEvent", object_id, "SPACE_TARGETS")
            sat_id = sat_links[0]["toId"] if sat_links else event.get("satelliteId")
            windows = self.fn_coverage_window(satellite_id=sat_id)[:12]
            targets = [item["target"] for item in windows]
            text = f"{event['id']} 우주 이벤트 영향 분석: {sat_id} 의존 수집 표적 {len(targets)}건이 영향을 받을 수 있습니다."
            actions = [{
                "type": "RequestSatCollection",
                "title": "대체 위성 수집 요청",
                "effect": "동일 표적의 다음 가시 창을 다른 위성으로 전환",
                "requiresApproval": True,
                "parameters": {"satelliteId": sat_id, "targetIds": [target["id"] for target in targets[:5]]},
            }]
            self._audit("WatchSpaceEvent", f"{object_id} targets={len(targets)}")
            result = {"answer": text, "mode": "watch", "evidence": [chip(event)] + [chip(t) for t in targets[:5]], "impacts": [{"target": t, "severity": event["severity"]} for t in targets], "actions": actions}
            return self._gateway_payload(f"Watch {object_id}", result)

        return self._unknown("지원되는 Watch 이벤트 유형은 ThreatEvent와 SpaceEvent입니다.")

    def decide(self, event: dict[str, Any], impacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not impacts:
            return []
        top = impacts[:3]
        mission_ids = [item["mission"]["id"] for item in top]
        return [
            {
                "type": "RetaskMission",
                "title": "영향 임무 재임무부여",
                "effect": f"{len(top)}개 임무의 위협 반경 체류를 줄이고 목표 도착 지연을 제한",
                "requiresApproval": True,
                "parameters": {"threatEventId": event["id"], "missionIds": mission_ids},
            },
            {
                "type": "DivertAircraft",
                "title": "대체 회복기지로 우회",
                "effect": "위협 회랑 통과 후 회복 경로를 변경해 노출 시간을 감소",
                "requiresApproval": True,
                "parameters": {"missionIds": mission_ids, "candidateBase": "K-5"},
            },
            {
                "type": "AssignInterceptor",
                "title": "요격/감시 자원 할당",
                "effect": "미식별 항적과 위협원을 같은 결심 화면에서 추적",
                "requiresApproval": True,
                "parameters": {"threatEventId": event["id"], "priority": top[0]["severity"]},
            },
        ]

    def approve_action(self, action: dict[str, Any], actor: str = "operator") -> dict[str, Any]:
        self._audit(action.get("type", "RecordDecision"), f"approved by {actor}: {action.get('title', '')}", actor=actor)
        return {"status": "approved", "action": action, "auditSize": len(self.graph.audit)}

    def generate_aar(self, hours: int = 12) -> dict[str, Any]:
        events = sorted(self.graph.all("ThreatEvent") + self.graph.all("SpaceEvent"), key=lambda item: item.get("firstSeen") or item.get("tca") or "")
        actions = self.graph.audit[-20:]
        status_counter = Counter(mission["status"] for mission in self.graph.all("Mission"))
        sample_events = events[:10]
        evidence = [chip(item) for item in sample_events[:5]]
        sections = {
            "overview": f"최근 {hours}시간 합성 상황에서는 ThreatEvent {len(self.graph.all('ThreatEvent'))}건, SpaceEvent {len(self.graph.all('SpaceEvent'))}건이 기록되었습니다.",
            "timeline": [f"{item.get('firstSeen') or item.get('tca')} {item['type']} {item['id']} {item.get('eventType')}" for item in sample_events],
            "planVsActual": "Mission 상태 분포: " + ", ".join(f"{key} {value}" for key, value in sorted(status_counter.items())),
            "decisionAnalysis": [f"{item['at']} {item['actor']} {item['action']} - {item['detail']}" for item in actions[-8:]],
            "lessons": [
                "위협 이벤트와 임무 경로 교차 계산은 결정론적 Function으로 유지해야 한다.",
                "대체 수집과 회항 제안은 자동 실행하지 않고 승인형 Action으로 남겨야 한다.",
                "근거 칩이 없는 서술은 AAR 초안에서 제외해야 한다.",
            ],
        }
        section_evidence = {
            "overview": evidence,
            "timeline": evidence,
            "planVsActual": [chip(item) for item in self.graph.all("Mission")[:5]],
            "decisionAnalysis": evidence,
            "lessons": evidence[:3],
        }
        return {
            "title": "ARGOS AAR Draft",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "evidence": evidence,
            "sections": sections,
            "sectionEvidence": section_evidence,
        }

    def _answer_object_detail(self, object_type: str, object_id: str) -> dict[str, Any]:
        obj = self.graph.get(object_type, object_id)
        if not obj:
            return self._unknown(f"{object_id}는 현재 온톨로지에서 확인되지 않습니다.")
        fields = [f"{key}={value}" for key, value in obj.items() if key not in {"route", "tle"}][:8]
        return self._answer(f"{object_type} {object_id} 상세: " + ", ".join(fields), [chip(obj)], "object-detail")

    def _answer_base_status(self, base_id: str) -> dict[str, Any]:
        base = self.graph.get("AirBase", base_id)
        if not base:
            return self._unknown(f"{base_id} 비행장은 현재 온톨로지에서 확인되지 않습니다.")
        runways = self.graph.linked_objects("AirBase", base_id, "HAS_RUNWAY")
        squadrons = self.graph.linked_objects("AirBase", base_id, "BASED_AT", direction="in")
        open_runways = [r for r in runways if r["surfaceStatus"] == "open"]
        text = f"{base_id} {base['name']}은 활주로 {len(open_runways)}/{len(runways)}개 사용 가능, 주둔 대대 {len(squadrons)}개, 수용능력 {base['capacity']}입니다."
        return self._answer(text, [chip(base)] + [chip(r) for r in runways] + [chip(s) for s in squadrons], "base-status")

    def _answer_squadrons_at_base(self, base_id: str) -> dict[str, Any]:
        base = self.graph.get("AirBase", base_id)
        if not base:
            return self._unknown(f"{base_id} 기지는 현재 온톨로지에서 확인되지 않습니다.")
        squadrons = self.graph.linked_objects("AirBase", base_id, "BASED_AT", direction="in")
        text = f"{base_id}에 주둔한 대대는 " + ", ".join(f"{sq['id']}({sq['airframe']})" for sq in squadrons) + "입니다."
        return self._answer(text, [chip(base)] + [chip(sq) for sq in squadrons], "single-hop")

    def _answer_readiness(self) -> dict[str, Any]:
        rollup = self.fn_readiness_rollup()[:5]
        parts = [f"{item['base']['id']} {item['rate'] * 100:.1f}% ({item['ready']}/{item['total']})" for item in rollup if item["base"]]
        return self._answer("기지별 가동률 상위 5개는 " + ", ".join(parts) + "입니다.", [chip(item["base"]) for item in rollup if item["base"]], "aggregate")

    def _answer_maintenance_mission_alternates(self) -> dict[str, Any]:
        open_maint_by_tail = {
            link["toId"]: self.graph.get("MaintRecord", link["fromId"])
            for link in self.graph.links
            if link["type"] == "MAINT_TARGET" and (self.graph.get("MaintRecord", link["fromId"]) or {}).get("status") == "open"
        }
        impacted = []
        for mission in self.graph.all("Mission"):
            for link in self.graph.outgoing("Mission", mission["id"], "FLOWN_BY"):
                if link["toId"] in open_maint_by_tail:
                    aircraft = self.graph.get("Aircraft", link["toId"])
                    alternate = self._alternate_aircraft(aircraft)
                    impacted.append({"mission": mission, "aircraft": aircraft, "maint": open_maint_by_tail[link["toId"]], "alternate": alternate})
                    break
            if len(impacted) >= 8:
                break

        if not impacted:
            return self._answer("현재 열린 정비 이슈가 배정된 ATO 임무는 확인되지 않습니다.", [], "multi-hop")
        text = "정비 이슈가 있는 기체에 배정된 임무는 " + ", ".join(
            f"{item['mission']['callsign']}->{item['aircraft']['id']} 대체 {item['alternate']['id'] if item['alternate'] else '없음'}"
            for item in impacted
        ) + "입니다."
        evidence = []
        for item in impacted:
            evidence.extend([chip(item["mission"]), chip(item["aircraft"]), chip(item["maint"])])
            if item["alternate"]:
                evidence.append(chip(item["alternate"]))
        return self._answer(text, evidence, "multi-hop")

    def _answer_satellite_coverage(self, question: str) -> dict[str, Any]:
        target_id = self._first_known_id(question, "Target")
        sat_id = self._first_known_id(question, "Satellite")
        windows = self.fn_coverage_window(target_id=target_id, satellite_id=sat_id)[:8]
        if not windows:
            return self._unknown("현재 온톨로지에서 해당 수집 창을 확인할 수 없습니다.")
        text = "확인된 수집 창은 " + ", ".join(f"{w['satellite']['name']}->{w['target']['id']} {w['start']}~{w['end']}" for w in windows) + "입니다."
        evidence = [chip(w["satellite"]) for w in windows] + [chip(w["target"]) for w in windows[:3]]
        return self._answer(text, evidence, "spatiotemporal")

    def _answer_tracks(self) -> dict[str, Any]:
        tracks = [t for t in self.graph.all("Track") if t["identity"] in {"unknown", "suspect"}]
        tracks.sort(key=lambda item: 0 if item["identity"] == "suspect" else 1)
        sample = tracks[:8]
        text = "관심 항적은 " + ", ".join(f"{t['id']}({t['identity']}, {t['speedKt']}kt, heading {t['heading']})" for t in sample) + "입니다."
        return self._answer(text, [chip(t) for t in sample], "tracks")

    def _alternate_aircraft(self, aircraft: dict[str, Any] | None) -> dict[str, Any] | None:
        if not aircraft:
            return None
        sq_links = self.graph.outgoing("Aircraft", aircraft["id"], "ASSIGNED_TO")
        if not sq_links:
            return None
        candidates = self.graph.linked_objects("Squadron", sq_links[0]["toId"], "ASSIGNED_TO", direction="in")
        ready = [item for item in candidates if item["id"] != aircraft["id"] and item["status"] == "ready" and item["airframe"] == aircraft["airframe"]]
        return sorted(ready, key=lambda item: item["readiness"], reverse=True)[0] if ready else None

    def _find_object_mention(self, text: str) -> tuple[str, str] | None:
        for object_type in ("ThreatEvent", "SpaceEvent", "Mission", "Aircraft", "Track", "AirBase", "Target", "Satellite"):
            object_id = self._first_known_id(text, object_type)
            if object_id:
                return object_type, object_id
        base_id = self._extract_base_id(text)
        return ("AirBase", base_id) if base_id else None

    def _first_known_id(self, text: str, object_type: str) -> str | None:
        for object_id in self.graph.objects.get(object_type, {}):
            if object_id in text:
                return object_id
        return None

    def _extract_base_id(self, text: str) -> str | None:
        match = re.search(r"K-\d+", text, re.IGNORECASE)
        return match.group(0).upper() if match else None

    def _tokens(self, text: str) -> set[str]:
        return set(re.findall(r"[0-9a-zA-Z가-힣-]+", text))

    def _has_any(self, tokens: set[str], words: set[str]) -> bool:
        return any(word in token for token in tokens for word in words)

    def _answer(self, text: str, evidence: list[dict[str, str]], mode: str) -> dict[str, Any]:
        return self._gateway_payload("", {"answer": text, "mode": mode, "evidence": evidence})

    def _unknown(self, text: str) -> dict[str, Any]:
        return {"answer": text, "mode": "unknown", "evidence": [], "adapter": "none"}

    def _gateway_payload(self, question: str, result: dict[str, Any]) -> dict[str, Any]:
        response = self.gateway.complete(
            LlmRequest(
                question=question,
                mode=str(result.get("mode", "unknown")),
                tool_result=result,
                evidence=list(result.get("evidence", [])),
                actions=list(result.get("actions", [])),
            )
        ).to_payload()
        for key in ("impacts", "aar"):
            if key in result:
                response[key] = result[key]
        return response

    def _audit(self, action: str, detail: str, actor: str = "agent") -> None:
        self.graph.audit.append({"at": datetime.now(timezone.utc).isoformat(), "actor": actor, "action": action, "detail": detail})


def cop_tracks(graph: OntologyGraph, limit: int = 80) -> list[dict[str, Any]]:
    bases = graph.all("AirBase")
    tracks = graph.all("Track")[:limit]
    result = []
    for track in tracks:
        nearest = min(bases, key=lambda base: haversine_km(track["lat"], track["lon"], base["lat"], base["lon"]))
        result.append({**track, "nearestBase": nearest["id"], "nearestBaseKm": round(haversine_km(track["lat"], track["lon"], nearest["lat"], nearest["lon"]), 1)})
    return result


def _impact_payload(item: dict[str, Any]) -> dict[str, Any]:
    mission = item["mission"]
    return {
        "missionId": mission["id"],
        "callsign": mission["callsign"],
        "distanceKm": item["distanceKm"],
        "severity": item["severity"],
        "route": mission["route"],
        "start": mission["start"],
        "end": mission["end"],
    }

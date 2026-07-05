from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from typing import Any

from .graph import OntologyGraph
from .reasoning import ArgosAgent, _impact_payload, chip
from .schema import schema_summary

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
MAX_TOOL_ROUNDS = 6
MAX_TURNS = 12

OBJECT_TYPE_NAMES = list(schema_summary()["objectTypes"].keys())


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
            },
        },
    }


OLLAMA_TOOLS: list[dict[str, Any]] = [
    _tool(
        "get_object",
        "온톨로지 그래프에서 특정 타입/ID 객체의 전체 속성을 조회합니다.",
        {
            "objectType": {"type": "string", "enum": OBJECT_TYPE_NAMES},
            "objectId": {"type": "string"},
        },
        ["objectType", "objectId"],
    ),
    _tool(
        "search_objects",
        "정확한 ID를 모를 때, 이름/콜사인/ID 일부 문자열로 특정 타입의 객체를 검색합니다.",
        {
            "objectType": {"type": "string", "enum": OBJECT_TYPE_NAMES},
            "query": {"type": "string"},
            "limit": {"type": "integer", "default": 10},
        },
        ["objectType", "query"],
    ),
    _tool(
        "get_base_status",
        "공군기지(K-2~K-10) 활주로 가동 상태와 주둔 대대 목록을 조회합니다.",
        {"baseId": {"type": "string"}},
        ["baseId"],
    ),
    _tool(
        "get_readiness_rollup",
        "기지별 항공기 가동률(ready/total) 집계를 조회합니다.",
        {},
    ),
    _tool(
        "get_unidentified_tracks",
        "미식별(unknown) 또는 의심(suspect) 항적 목록을 조회합니다.",
        {"limit": {"type": "integer", "default": 8}},
    ),
    _tool(
        "get_maintenance_impacted_missions",
        "열린 정비 이슈가 있는 기체에 배정된 임무와, 있다면 대체 가능 기체를 조회합니다.",
        {"limit": {"type": "integer", "default": 8}},
    ),
    _tool(
        "get_satellite_coverage",
        "위성-표적 수집 창(coverage window)을 조회합니다. targetId/satelliteId 중 하나 이상을 지정할 수 있습니다.",
        {"targetId": {"type": "string"}, "satelliteId": {"type": "string"}},
    ),
    _tool(
        "threat_intersect",
        "특정 ThreatEvent가 영향을 미치는 임무 목록을 위협 반경 교차 계산으로 조회합니다.",
        {"eventId": {"type": "string"}},
        ["eventId"],
    ),
    _tool(
        "deconflict_mission",
        "특정 임무 경로와 제한 공역(AirspaceZone) 충돌 여부를 확인합니다.",
        {"missionId": {"type": "string"}},
        ["missionId"],
    ),
    _tool(
        "watch_threat_event",
        "ThreatEvent에 대한 Watch->Decide 분석을 수행합니다. 영향 임무와 승인 필요 대응조치 후보(RetaskMission/DivertAircraft/AssignInterceptor)를 함께 반환합니다.",
        {"eventId": {"type": "string"}},
        ["eventId"],
    ),
    _tool(
        "watch_space_event",
        "SpaceEvent 영향 분석과 승인 필요 대응조치 후보(RequestSatCollection)를 반환합니다.",
        {"eventId": {"type": "string"}},
        ["eventId"],
    ),
    _tool(
        "generate_aar",
        "최근 N시간 사후강평(AAR) 초안을 생성합니다.",
        {"hours": {"type": "integer", "default": 12}},
    ),
    _tool(
        "list_recent_events",
        "최근 ThreatEvent/SpaceEvent 이벤트 목록(ID, 유형, 심각도)을 조회합니다. 다른 도구를 호출하기 전 유효한 이벤트 ID를 확인할 때 사용합니다.",
        {
            "eventType": {"type": "string", "enum": ["ThreatEvent", "SpaceEvent"]},
            "limit": {"type": "integer", "default": 15},
        },
    ),
]


def _system_prompt() -> str:
    # Kept intentionally short: small local models (e.g. llama3.2:3b) lose tool-calling
    # accuracy when the system prompt is long. Embedding the full schema_summary() JSON
    # here (~5KB) measurably made tool selection worse in testing, so object-type detail
    # is left to the tool parameter enums instead of being duplicated in prose.
    #
    # The language-consistency rule + worked examples were added after testing showed the
    # 3B model would otherwise copy raw English tool-result field names (or stray words in
    # other languages, e.g. "capacidad", or even Vietnamese/Chinese in a closing summary
    # sentence on longer multi-fact answers) straight into its answer instead of translating
    # them. The "don't add a wrap-up sentence" rule specifically targets that closing-sentence
    # drift, and a second example covers the longer bullet-style "status report" answer shape
    # where it showed up, since the model leans heavily on whichever example most resembles
    # the answer it's building.
    return (
        "당신은 ARGOS Response Agent입니다. 한반도 공중-우주 작전 상황도 챗봇입니다. "
        "데이터는 전부 SYNTHETIC(합성)입니다. "
        "질문에 답하기 전에 반드시 제공된 도구를 먼저 호출해 사실을 확인하세요. 절대 추측하지 마세요. "
        "ID를 모르면 search_objects나 list_recent_events를 먼저 호출하세요. "
        "대응조치(RetaskMission 등)는 전부 사람 승인이 필요한 권고입니다, 이미 실행됐다고 말하지 마세요. "
        "반드시 한국어로만 답하세요. 영어 단어, 중국어, 베트남어 등 한국어가 아닌 언어는 단 한 글자도 섞지 마세요. "
        "도구 결과에 있는 영어 필드명(capacity, protection, lat, lon 등)이나 원문 값을 그대로 베끼지 말고 "
        "자연스러운 한국어 문장으로 바꿔서 설명하세요. 객체 ID(예: 'K-2', 'TEV-0001')만 원문 그대로 씁니다. "
        "사실을 전달했으면 그 자리에서 답변을 끝내세요. 마무리 인사말이나 요약 문장을 따로 덧붙이지 마세요. "
        "예시 답변1: 'K-2(대구기지)는 활주로 2개가 모두 가동 중이며, 수용 인원은 51명입니다.' "
        "예시 답변2: '대구기지(K-2) 현황: 활주로 2개 모두 가동 중(2661m, 3164m). F-35A, KF-16 배치. 인원 97명, 110명.'"
    )


class OllamaApiError(Exception):
    pass


class OllamaChatAgent:
    """Multi-turn Ollama tool-use chatbot grounded on the ARGOS ontology graph."""

    def __init__(self, graph: OntologyGraph):
        self.graph = graph
        self.agent = ArgosAgent(graph)
        self.host = os.getenv("ARGOS_OLLAMA_HOST", DEFAULT_HOST).rstrip("/")
        self.model = os.getenv("ARGOS_OLLAMA_MODEL", DEFAULT_MODEL)
        self.system_prompt = _system_prompt()
        self.sessions: dict[str, list[list[dict[str, Any]]]] = {}
        self.lock = threading.Lock()

    def available(self) -> bool:
        return self.status()["available"]

    def status(self) -> dict[str, Any]:
        try:
            request = urllib.request.Request(f"{self.host}/api/tags", method="GET")
            with urllib.request.urlopen(request, timeout=3) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception:
            return {"available": False, "model": self.model, "modelInstalled": False}
        names = [str(m.get("name", "")) for m in data.get("models", [])]
        installed = any(n == self.model or n.split(":")[0] == self.model for n in names)
        return {"available": True, "model": self.model, "modelInstalled": installed}

    def reset(self, session_id: str) -> None:
        with self.lock:
            self.sessions.pop(session_id, None)

    def chat(self, session_id: str, message: str) -> dict[str, Any]:
        message = message.strip()
        if not message:
            return {"answer": "질문을 입력해 주세요.", "mode": "chat", "evidence": [], "adapter": "ollama"}

        with self.lock:
            turns = self.sessions.setdefault(session_id, [])
            current_turn: list[dict[str, Any]] = [{"role": "user", "content": message}]
            flattened = [m for turn in turns for m in turn] + current_turn

            evidence: dict[tuple[str, str], dict[str, str]] = {}
            actions: list[dict[str, Any]] = []
            impacts: list[dict[str, Any]] = []
            final_text = ""

            try:
                for _ in range(MAX_TOOL_ROUNDS):
                    data = self._call_ollama(flattened)
                    assistant_message = dict(data.get("message") or {})
                    assistant_message.setdefault("role", "assistant")
                    current_turn.append(assistant_message)
                    flattened.append(assistant_message)

                    tool_calls = assistant_message.get("tool_calls") or []
                    if not tool_calls:
                        final_text = str(assistant_message.get("content", "")).strip()
                        break

                    for call in tool_calls:
                        function = call.get("function", {})
                        name = str(function.get("name", ""))
                        args = function.get("arguments") or {}
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}
                        result, chips, tool_actions, tool_impacts = self._execute_tool(name, args)
                        for item in chips:
                            evidence[(item["type"], item["id"])] = item
                        actions.extend(tool_actions)
                        impacts.extend(tool_impacts)
                        tool_message = {
                            "role": "tool",
                            "name": name,
                            "content": json.dumps(result, ensure_ascii=False, default=str)[:4000],
                        }
                        current_turn.append(tool_message)
                        flattened.append(tool_message)
                else:
                    final_text = final_text or "도구 호출 한도에 도달했습니다. 질문을 더 구체적으로 나눠서 다시 물어봐 주세요."
            except OllamaApiError as exc:
                return {
                    "answer": f"Ollama 호출 중 오류가 발생했습니다: {exc}",
                    "mode": "chat",
                    "evidence": [],
                    "adapter": "ollama-error",
                }
            except Exception as exc:
                # Anything unexpected here (malformed Ollama payload, dropped connection mid-read,
                # etc.) must still return a normal HTTP response — otherwise the request handler
                # dies mid-write and the browser sees a bare "Failed to fetch" with no explanation.
                return {
                    "answer": f"예상치 못한 오류로 답변을 생성하지 못했습니다: {exc}",
                    "mode": "chat",
                    "evidence": [],
                    "adapter": "ollama-error",
                }

            turns.append(current_turn)
            del turns[:-MAX_TURNS]

            return {
                "answer": final_text or "답변을 생성하지 못했습니다.",
                "mode": "chat",
                "evidence": list(evidence.values())[:12],
                "actions": actions[:3],
                "impacts": impacts[:20],
                "adapter": "ollama",
            }

    def _call_ollama(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        full_messages = [{"role": "system", "content": self.system_prompt}] + messages
        body = json.dumps(
            {
                "model": self.model,
                "messages": full_messages,
                "tools": OLLAMA_TOOLS,
                "stream": False,
                # Lower temperature trades a little creativity for a lot of consistency: small
                # local models drift into other languages / invent field names more at defaults.
                # num_predict caps generation length — the observed language-mixing happened in
                # trailing "wrap-up" sentences on longer answers, so keeping answers short shrinks
                # the window where that drift shows up.
                "options": {"temperature": 0.2, "num_predict": 200},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=body,
            method="POST",
            headers={"content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise OllamaApiError(f"HTTP {exc.code}: {detail[:500]}") from exc
        except urllib.error.URLError as exc:
            raise OllamaApiError(
                f"{self.host}에 연결할 수 없습니다 ({exc.reason}). Ollama가 실행 중인지 확인하세요."
            ) from exc
        except OSError as exc:
            # Covers timeouts and connection resets that happen mid-read rather than on connect,
            # which urllib does not always wrap as URLError.
            raise OllamaApiError(f"Ollama와의 연결이 끊겼습니다: {exc}") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OllamaApiError(f"Ollama 응답을 해석할 수 없습니다: {exc}") from exc

    def _execute_tool(
        self, name: str, args: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]]]:
        graph = self.graph
        agent = self.agent
        try:
            if name == "get_object":
                obj = graph.get(str(args["objectType"]), str(args["objectId"]))
                if not obj:
                    return {"error": "not found"}, [], [], []
                return obj, [chip(obj)], [], []

            if name == "search_objects":
                object_type = str(args["objectType"])
                query = str(args.get("query", "")).lower()
                limit = int(args.get("limit", 10))
                matches = []
                for obj in graph.all(object_type):
                    haystack = " ".join(str(v) for v in obj.values()).lower()
                    if query in haystack:
                        matches.append(obj)
                    if len(matches) >= limit:
                        break
                return {"results": matches}, [chip(o) for o in matches[:8]], [], []

            if name == "get_base_status":
                base_id = str(args["baseId"]).upper()
                base = graph.get("AirBase", base_id)
                if not base:
                    return {"error": f"{base_id} not found"}, [], [], []
                runways = graph.linked_objects("AirBase", base_id, "HAS_RUNWAY")
                squadrons = graph.linked_objects("AirBase", base_id, "BASED_AT", direction="in")
                result = {"base": base, "runways": runways, "squadrons": squadrons}
                return result, [chip(base)] + [chip(s) for s in squadrons], [], []

            if name == "get_readiness_rollup":
                rollup = agent.fn_readiness_rollup()
                chips = [chip(item["base"]) for item in rollup if item.get("base")]
                return {"rollup": rollup}, chips[:10], [], []

            if name == "get_unidentified_tracks":
                limit = int(args.get("limit", 8))
                tracks = [t for t in graph.all("Track") if t["identity"] in {"unknown", "suspect"}]
                tracks.sort(key=lambda t: 0 if t["identity"] == "suspect" else 1)
                sample = tracks[:limit]
                return {"tracks": sample}, [chip(t) for t in sample], [], []

            if name == "get_maintenance_impacted_missions":
                limit = int(args.get("limit", 8))
                open_maint_by_tail = {
                    link["toId"]: graph.get("MaintRecord", link["fromId"])
                    for link in graph.links
                    if link["type"] == "MAINT_TARGET"
                    and (graph.get("MaintRecord", link["fromId"]) or {}).get("status") == "open"
                }
                impacted = []
                for mission in graph.all("Mission"):
                    for link in graph.outgoing("Mission", mission["id"], "FLOWN_BY"):
                        if link["toId"] in open_maint_by_tail:
                            aircraft = graph.get("Aircraft", link["toId"])
                            alternate = agent._alternate_aircraft(aircraft)
                            impacted.append(
                                {
                                    "mission": mission,
                                    "aircraft": aircraft,
                                    "maintRecord": open_maint_by_tail[link["toId"]],
                                    "alternate": alternate,
                                }
                            )
                            break
                    if len(impacted) >= limit:
                        break
                chips = []
                for item in impacted:
                    chips += [chip(item["mission"]), chip(item["aircraft"]), chip(item["maintRecord"])]
                    if item["alternate"]:
                        chips.append(chip(item["alternate"]))
                return {"impactedMissions": impacted}, chips[:12], [], []

            if name == "get_satellite_coverage":
                windows = agent.fn_coverage_window(
                    target_id=args.get("targetId"), satellite_id=args.get("satelliteId")
                )
                chips = [chip(w["satellite"]) for w in windows[:5]] + [chip(w["target"]) for w in windows[:5]]
                return {"windows": windows[:12]}, chips, [], []

            if name == "threat_intersect":
                event_id = str(args["eventId"])
                event = graph.get("ThreatEvent", event_id)
                if not event:
                    return {"error": f"{event_id} not found"}, [], [], []
                impacts = agent.fn_threat_intersect(event)
                payload_impacts = [_impact_payload(item) for item in impacts]
                chips = [chip(event)] + [chip(item["mission"]) for item in impacts[:5]]
                return {"impacts": payload_impacts}, chips, [], payload_impacts

            if name == "deconflict_mission":
                mission_id = str(args["missionId"])
                result = agent.fn_deconflict(mission_id)
                mission = graph.get("Mission", mission_id)
                chips = ([chip(mission)] if mission else []) + [chip(z) for z in result.get("conflicts", [])]
                return result, chips, [], []

            if name == "watch_threat_event":
                result = agent.watch_event("ThreatEvent", str(args["eventId"]))
                return result, list(result.get("evidence", [])), list(result.get("actions", [])), list(
                    result.get("impacts", [])
                )

            if name == "watch_space_event":
                result = agent.watch_event("SpaceEvent", str(args["eventId"]))
                return result, list(result.get("evidence", [])), list(result.get("actions", [])), list(
                    result.get("impacts", [])
                )

            if name == "generate_aar":
                hours = int(args.get("hours", 12))
                aar = agent.generate_aar(hours=hours)
                return aar, list(aar.get("evidence", [])), [], []

            if name == "list_recent_events":
                event_type = args.get("eventType")
                limit = int(args.get("limit", 15))
                events = graph.all("ThreatEvent") + graph.all("SpaceEvent")
                if event_type:
                    events = [e for e in events if e["type"] == event_type]
                events.sort(key=lambda e: e.get("firstSeen") or e.get("tca") or "", reverse=True)
                sample = events[:limit]
                return {"events": sample}, [chip(e) for e in sample[:8]], [], []

            return {"error": f"unknown tool {name}"}, [], [], []
        except Exception as exc:  # tool execution must never crash the chat loop
            return {"error": str(exc)}, [], [], []

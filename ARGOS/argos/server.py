from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .generator import generate
from .function_api import call_function, evaluate_expected_impacts
from .graph import OntologyGraph
from .ollama_gateway import OllamaChatAgent
from .reasoning import ArgosAgent, cop_tracks
from .schema import schema_summary


class ArgosHandler(SimpleHTTPRequestHandler):
    graph: OntologyGraph
    agent: ArgosAgent
    chat_agent: OllamaChatAgent
    web_root: Path
    data_path: Path

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        rel = unquote(parsed.path).lstrip("/") or "index.html"
        return str((self.web_root / rel).resolve())

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/summary":
            return self._json({"stats": self.graph.stats(), "schema": schema_summary()})
        if parsed.path == "/api/graph":
            return self._json(self._cop_graph())
        if parsed.path == "/api/chat/status":
            return self._json(self.chat_agent.status())
        if parsed.path == "/api/events":
            events = sorted(
                self.graph.all("ThreatEvent") + self.graph.all("SpaceEvent"),
                key=lambda item: item.get("firstSeen") or item.get("tca") or "",
                reverse=True,
            )
            return self._json(events[:120])
        if parsed.path.startswith("/api/objects/"):
            _, _, _, object_type, object_id = parsed.path.split("/", 4)
            obj = self.graph.get(object_type, object_id)
            return self._json(obj or {"error": "not found"}, status=200 if obj else 404)
        if parsed.path.startswith("/api/neighborhood/"):
            _, _, _, object_type, object_id = parsed.path.split("/", 4)
            obj = self.graph.get(object_type, object_id)
            if not obj:
                return self._json({"error": "not found"}, status=404)
            return self._json(self._neighborhood(object_type, object_id))
        if parsed.path == "/" or not parsed.path.startswith("/api/"):
            return super().do_GET()
        self._json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        body = self._read_json()
        if parsed.path == "/api/ask":
            return self._json(self.agent.ask(str(body.get("question", ""))))
        if parsed.path == "/api/chat":
            session_id = str(body.get("sessionId") or "default")
            return self._json(self.chat_agent.chat(session_id, str(body.get("message", ""))))
        if parsed.path == "/api/chat/reset":
            self.chat_agent.reset(str(body.get("sessionId") or "default"))
            return self._json({"status": "reset"})
        if parsed.path == "/api/watch":
            return self._json(self.agent.watch_event(str(body.get("type", "ThreatEvent")), str(body.get("id", ""))))
        if parsed.path == "/api/action/approve":
            result = self.agent.approve_action(body.get("action", {}), actor=str(body.get("actor", "operator")))
            self.graph.save(self.data_path)
            return self._json(result)
        if parsed.path == "/api/aar":
            return self._json(self.agent.generate_aar(hours=int(body.get("hours", 12))))
        if parsed.path == "/api/aar/download":
            aar = self.agent.generate_aar(hours=int(body.get("hours", 12)))
            return self._markdown(_aar_markdown(aar), "argos_aar.md")
        if parsed.path == "/api/function":
            return self._json(call_function(self.graph, str(body.get("name", "")), **dict(body.get("args", {}))))
        if parsed.path == "/api/evals/watch":
            return self._json(evaluate_expected_impacts(self.graph))
        self._json({"error": "not found"}, status=404)

    def _cop_graph(self) -> dict[str, Any]:
        return {
            "bases": self.graph.all("AirBase"),
            "missions": self.graph.all("Mission")[:160],
            "threats": self.graph.all("ThreatEvent")[:30],
            "spaceEvents": self.graph.all("SpaceEvent")[:20],
            "satellites": self.graph.all("Satellite"),
            "tracks": cop_tracks(self.graph, limit=100),
        }

    def _neighborhood(self, object_type: str, object_id: str) -> dict[str, Any]:
        outgoing = self.graph.outgoing(object_type, object_id)[:40]
        incoming = self.graph.incoming(object_type, object_id)[:40]

        def link_payload(link: dict[str, Any], direction: str) -> dict[str, Any]:
            related_type = link["toType"] if direction == "out" else link["fromType"]
            related_id = link["toId"] if direction == "out" else link["fromId"]
            related = self.graph.get(related_type, related_id)
            return {
                "direction": direction,
                "link": link,
                "related": related,
            }

        return {
            "object": self.graph.get(object_type, object_id),
            "outgoing": [link_payload(link, "out") for link in outgoing],
            "incoming": [link_payload(link, "in") for link in incoming],
            "nearby": self.graph.bfs(object_type, object_id, max_depth=1)[:30],
        }

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _json(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _markdown(self, text: str, filename: str) -> None:
        data = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def serve(data_path: str | Path = "data/argos_graph.json", port: int = 8787) -> None:
    data = Path(data_path)
    if not data.exists():
        generate(data)
    handler = ArgosHandler
    handler.graph = OntologyGraph.load(data)
    handler.agent = ArgosAgent(handler.graph)
    handler.chat_agent = OllamaChatAgent(handler.graph)
    handler.data_path = data
    handler.web_root = Path(__file__).resolve().parent.parent / "web"
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"ARGOS COP serving http://127.0.0.1:{port}")
    server.serve_forever()


def _aar_markdown(aar: dict[str, Any]) -> str:
    sections = aar["sections"]
    lines = [f"# {aar['title']}", "", f"Generated: {aar['generatedAt']}", ""]
    lines += ["## Overview", sections["overview"], ""]
    lines += ["## Timeline", *[f"- {item}" for item in sections["timeline"]], ""]
    lines += ["## Plan vs Actual", sections["planVsActual"], ""]
    lines += ["## Decision Analysis", *[f"- {item}" for item in sections["decisionAnalysis"]], ""]
    lines += ["## Lessons", *[f"- {item}" for item in sections["lessons"]], ""]
    lines += ["## Evidence", *[f"- {item['type']}:{item['id']} {item['label']}" for item in aar.get("evidence", [])], ""]
    return "\n".join(lines)

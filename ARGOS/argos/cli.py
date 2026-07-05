from __future__ import annotations

import argparse
import json
from pathlib import Path

from .generator import generate
from .function_api import evaluate_expected_impacts
from .graph import OntologyGraph
from .reasoning import ArgosAgent
from .schema import ontology_manifest
from .server import serve
from .validation import validate_graph


def load_or_generate(path: str) -> OntologyGraph:
    if not Path(path).exists():
        return generate(path)
    return OntologyGraph.load(path)


def main() -> None:
    parser = argparse.ArgumentParser(prog="argos")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate")
    gen.add_argument("--out", default="data/argos_graph.json")
    gen.add_argument("--seed", type=int)
    gen.add_argument("--scenario", choices=["S0", "S1", "S2", "S3"], default="S0")

    stats = sub.add_parser("stats")
    stats.add_argument("--data", default="data/argos_graph.json")

    ask = sub.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--data", default="data/argos_graph.json")

    aar = sub.add_parser("aar")
    aar.add_argument("--data", default="data/argos_graph.json")
    aar.add_argument("--hours", type=int, default=12)

    validate = sub.add_parser("validate")
    validate.add_argument("--data", default="data/argos_graph.json")

    evals = sub.add_parser("eval-watch")
    evals.add_argument("--data", default="data/argos_graph.json")

    manifest = sub.add_parser("manifest")
    manifest.add_argument("--out", default="ontology_manifest.json")

    srv = sub.add_parser("serve")
    srv.add_argument("--data", default="data/argos_graph.json")
    srv.add_argument("--port", type=int, default=8787)

    args = parser.parse_args()
    if args.command == "generate":
        graph = generate(args.out, seed=args.seed, scenario=args.scenario)
        print(json.dumps(graph.stats(), ensure_ascii=False, indent=2))
        return
    if args.command == "manifest":
        payload = ontology_manifest()
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"written": args.out, "objectTypes": len(payload["objectTypes"])}, ensure_ascii=False, indent=2))
        return
    if args.command == "serve":
        serve(args.data, args.port)
        return

    graph = load_or_generate(args.data)
    agent = ArgosAgent(graph)
    if args.command == "stats":
        print(json.dumps(graph.stats(), ensure_ascii=False, indent=2))
    elif args.command == "validate":
        print(json.dumps(validate_graph(graph), ensure_ascii=False, indent=2))
    elif args.command == "eval-watch":
        print(json.dumps(evaluate_expected_impacts(graph), ensure_ascii=False, indent=2))
    elif args.command == "ask":
        print(json.dumps(agent.ask(args.question), ensure_ascii=False, indent=2))
    elif args.command == "aar":
        print(json.dumps(agent.generate_aar(hours=args.hours), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

# ARGOS - Aerospace Reasoning & Graph Ontology System

ARGOS is a local, runnable MVP based on `ARGOS_공중우주온톨로지빌더_기술백서_v1.0.pdf`.
It implements the white paper concepts without Foundry/AIP dependencies:

- 18 ontology object types, 24 link types, 7 action types, and 4 deterministic functions
- deterministic Scenario-as-Code synthetic data generation
- graph traversal for single-hop, multi-hop, aggregate, spatiotemporal, and trap queries
- Watch -> Decide threat and space-event impact analysis
- AAR draft generation from event/action history
- a 3-panel COP-style web app: map, timeline, and agent panel

All data is synthetic.

## Quick Start

```powershell
python -m argos.cli generate --scenario S2 --out data/argos_graph.json
python -m argos.cli serve --data data/argos_graph.json --port 8787
```

Then open:

```text
http://127.0.0.1:8787
```

If `python` is not on PATH, use the bundled Codex Python shown in the workspace dependency output.

## Useful CLI Commands

```powershell
python -m argos.cli stats --data data/argos_graph.json
python -m argos.cli validate --data data/argos_graph.json
python -m argos.cli eval-watch --data data/argos_graph.json
python -m argos.cli manifest --out ontology_manifest.json
python -m argos.cli ask "K-2에 주둔한 대대는?" --data data/argos_graph.json
python -m argos.cli ask "오늘 ATO 임무 중 정비 이슈 있는 기체에 배정된 것은? 대체 기체까지 찾아줘" --data data/argos_graph.json
python -m argos.cli aar --data data/argos_graph.json --hours 12
```

## Project Layout

```text
argos/
  schema.py      ontology schema, links, actions, function names
  generator.py   deterministic synthetic graph generator
  graph.py       in-memory ontology graph and traversal helpers
  llm_gateway.py Palantir AIP Agent contract with local mock fallback
  function_api.py deterministic Function API and Watch evals
  validation.py  schema validation
  reasoning.py   Ask, Watch, Decide, AAR logic
  server.py      stdlib HTTP API and static file server
  cli.py         command-line entry point
web/
  index.html
  styles.css
  app.js
tests/
  test_argos.py
```

## White Paper Traceability

- FR-1: `argos/schema.py`
- FR-2: `argos/generator.py`
- FR-3: `argos/reasoning.py::ArgosAgent.ask`
- FR-4: `argos/reasoning.py::ArgosAgent.watch_event`
- FR-5: `argos/reasoning.py::ArgosAgent.decide`
- FR-6: `argos/reasoning.py::ArgosAgent.generate_aar`
- FR-7: evidence chips are returned as object references in every answer/report
- FR-8: `web/` implements the 3-panel COP app

## Submission Artifacts

- `ontology_manifest.json`: machine-readable ontology/AIP manifest
- `docs/ontology_mapping.md`: object/link/action/function mapping
- `docs/aip_submission_package.md`: AIP submission handoff notes

The local runtime uses a Palantir AIP-compatible gateway contract. If
`ARGOS_AIP_AGENT_ENDPOINT` and `ARGOS_AIP_TOKEN` are not configured, the app
uses a deterministic mock AIP adapter so demos remain reproducible.

## Response Agent (local Ollama Chatbot)

The `Response Agent` panel in the web app is a multi-turn chatbot backed by a
local [Ollama](https://ollama.com) model (`argos/ollama_gateway.py`). The model
answers using tool-use function calling against the ontology graph (base
status, readiness rollup, threat/space Watch analysis, coverage windows,
deconfliction, AAR, object/search lookups) so every factual claim is grounded
in `data/argos_graph.json` and returned with evidence chips. Recommended
actions still require human approval through the existing approval-card UI.
No data leaves the machine — everything runs against the local Ollama server.

```powershell
ollama pull llama3.2
ollama serve
python -m argos.cli serve --data data/argos_graph.json --port 8787
```

Optional env vars: `ARGOS_OLLAMA_HOST` overrides the Ollama server URL
(default `http://localhost:11434`), `ARGOS_OLLAMA_MODEL` overrides the model
(default `llama3.2`). Use any Ollama model that supports tool calling, e.g.
`llama3.2`, `llama3.1`, `qwen2.5`, or `mistral-nemo`. The panel checks
`/api/tags` on load and reports whether the Ollama server is reachable and
whether the configured model is pulled, so misconfiguration is visible
immediately instead of failing silently.

# ARGOS AIP Submission Package

## Deliverables

- `ontology_manifest.json`: object, link, Action, and Function definitions
- `docs/ontology_mapping.md`: human-readable ontology and AIP mapping
- `data/argos_graph.json`: synthetic scenario graph
- Local COP app: `python -m argos.cli serve --data data/argos_graph.json`

## AIP Components

- Foundry Ontology Manager: load object and link definitions from manifest
- Pipeline Builder: map synthetic JSON/CSV records into backing datasets
- Foundry Functions: implement `fnThreatIntersect`, `fnCoverageWindow`,
  `fnReadinessRollup`, `fnDeconflict`
- AIP Agent Studio: call graph tools, deterministic functions, and approval
  Action tools through the contract in `llm_gateway.py`
- Workshop: reproduce the local COP map, event timeline, agent panel, evidence
  chips, and approval cards

## Evaluation

- Schema validation: `python -m argos.cli validate --data data/argos_graph.json`
- Watch evaluation: `python -m argos.cli eval-watch --data data/argos_graph.json`
- Unit tests: `python -m unittest discover -s tests -v`

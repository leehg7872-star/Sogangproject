# ARGOS Ontology and AIP Mapping

ARGOS maps the white-paper ontology into a Palantir AIP-style local package.
All records are synthetic and marked as public synthetic data.

## Ontology Objects

The ontology has 18 operational object types:

AirBase, Runway, Squadron, Aircraft, Pilot, MaintRecord, ATO, Mission, Target,
SAMSite, ThreatEvent, Track, Satellite, GroundStation, SpaceEvent, Sensor,
WeatherReport, AirspaceZone.

Each object has a stable synthetic primary key and the properties defined in
`argos/schema.py`. The exported `ontology_manifest.json` is the canonical
submission artifact.

## Relationships

The graph has 24 relationship types covering:

- force structure: Aircraft -> Squadron -> AirBase
- crew and maintenance: Pilot -> Aircraft, MaintRecord -> Aircraft
- ATO execution: ATO -> Mission -> Aircraft/Target/AirBase/AirspaceZone
- threat reasoning: ThreatEvent -> SAMSite/Mission/Track, Sensor -> ThreatEvent
- space reasoning: SpaceEvent -> Satellite -> Target/GroundStation
- operating constraints: WeatherReport -> AirBase, SAMSite -> AirspaceZone

## AIP Agent Contract

The local `llm_gateway.py` module defines the AIP Agent Studio handoff contract.
The request contains:

- `question`: user natural-language question
- `mode`: classified intent
- `tool_result`: deterministic graph/function result
- `evidence`: object references used as evidence chips
- `actions`: optional approval-required decision cards

The local runtime uses `MockAipGateway` or `PalantirAipGateway` fallback. In a
Foundry environment, replace the gateway implementation with an AIP Agent tool
call while preserving the same request/response shape.

## Functions

ARGOS exposes four deterministic functions:

- `fnThreatIntersect`: threat radius vs mission route impact ranking
- `fnCoverageWindow`: satellite-to-target collection windows
- `fnReadinessRollup`: base-level aircraft readiness aggregation
- `fnDeconflict`: mission route vs restricted airspace check

These are surfaced locally by `argos/function_api.py` and map to Foundry
Functions in an AIP deployment.

## Actions

All decision actions require human approval:

- CreateThreatEvent
- RetaskMission
- DivertAircraft
- AssignInterceptor
- RequestSatCollection
- UpdateReadiness
- RecordDecision

Approved actions are appended to the graph audit log.

## Scenarios

Synthetic data supports four deterministic modes:

- `S0`: peacetime baseline
- `S1`: large force exercise with increased mission density
- `S2`: threat campaign with additional ThreatEvents and expected impacts
- `S3`: space event campaign with additional SpaceEvents and expected impacts

Use `python -m argos.cli generate --scenario S2 --out data/argos_graph.json` to
regenerate a scenario.

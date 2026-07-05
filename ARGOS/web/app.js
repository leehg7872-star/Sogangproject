function getSessionId() {
  const key = "argosSessionId";
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(key, id);
  }
  return id;
}

const state = {
  graph: null,
  events: [],
  summary: null,
  selected: null,
  selectedEventId: null,
  eventFilter: "all",
  mapScope: "south",
  sessionId: getSessionId(),
  layers: { routes: true, tracks: true, threats: true, satellites: true },
  map: { zoom: 1, focusX: 55, focusY: 48 },
  scenario: {
    frame: 0,
    totalFrames: 20,
    intervalMs: 1000,
    timer: null,
    alertTimers: new Map(),
    alertedTrackIds: new Set(),
    alertEvents: [],
    lastDetectedTrackIds: new Set(),
  },
  vworld: {
    ready: false,
    loading: false,
    map: null,
    apiKey: "",
    vectorSource: null,
    vectorLayer: null,
    baseLayer: null,
    renderTimer: null,
    failed: false,
  },
};

const $ = (id) => document.getElementById(id);
const fmt = new Intl.NumberFormat("ko-KR");
const focusRegions = {
  all: { zoom: 1, focusX: 55, focusY: 48 },
  gangneung: { zoom: 2.35, focusX: 69, focusY: 25 },
  seoul: { zoom: 2.05, focusX: 42, focusY: 26 },
  busan: { zoom: 2.2, focusX: 70, focusY: 73 },
  jeju: { zoom: 2.25, focusX: 38, focusY: 93 },
};
const cityMarkers = [
  { name: "Seoul", lat: 37.5665, lon: 126.9780 },
  { name: "Gangneung", lat: 37.7519, lon: 128.8761 },
  { name: "Daegu", lat: 35.8714, lon: 128.6014 },
  { name: "Busan", lat: 35.1796, lon: 129.0756 },
  { name: "Gwangju", lat: 35.1595, lon: 126.8526 },
  { name: "Jeju", lat: 33.4996, lon: 126.5312 },
];
const vworldFocusRegions = {
  all: { center: [127.85, 36.25], zoom: 7 },
  gangneung: { center: [128.8761, 37.7519], zoom: 10 },
  seoul: { center: [126.9780, 37.5665], zoom: 10 },
  busan: { center: [129.0756, 35.1796], zoom: 10 },
  jeju: { center: [126.5312, 33.4996], zoom: 10 },
};
const scenarioStartMs = Date.parse("2026-07-04T18:00:00Z");
const busanRadarSite = { name: "Busan Air Defense Radar", lat: 35.1796, lon: 129.0756 };
const detectionRangeKm = 420;
const detectionSites = [
  busanRadarSite,
];
// Friendly ROK ground radar sites (SAM_RADAR_EMIT threat records repurposed as our own
// sensors, not enemy threats) — rendered green and relabeled instead of showing raw TEV IDs.
// Fixed at 3 real ROK airbase areas (Suwon x2, Daegu) instead of scattered around Busan.
const radarSites = [
  { lat: 37.239, lon: 127.007, label: "Radar Site 1" }, // Suwon
  { lat: 35.894, lon: 128.659, label: "Radar Site 2" }, // Daegu
  { lat: 37.20, lon: 126.95, label: "Radar Site 3" }, // Suwon area, offset
];
// Actual hostile threat rings are relocated to realistic DPRK sites: Pyongyang (SAM belt
// defending the capital) and Wonsan (the well-known missile launch coast), both displayed as
// SAM sites. These are DPRK installations, so they're only rendered under the North Korea
// map scope (see selectedNorthThreats/renderSyntheticStaticOverlays), not the South Korea COP.
// The Wonsan point is nudged inland from the real coastal coordinate because the synthetic
// basemap draws the coastline slightly differently there, which put the marker in the bay
// instead of on land. The underlying records are still MISSILE_LAUNCH_WARNING-type
// ThreatEvents (see selectedNorthThreats/displayThreat below) — only the displayed
// label/eventType is overridden to SAM_SITE.
const threatRingSites = [
  { lat: 39.0392, lon: 125.7625, eventType: "SAM_SITE", label: "Pyongyang SAM Site", status: "Pyongyang strategic SAM belt" },
  { lat: 39.20, lon: 126.95, eventType: "SAM_SITE", label: "Wonsan SAM Site", status: "Wonsan strategic SAM belt" },
];
const trackScenarioSpecs = [
  { source: "Northwest", start: [39.20, 124.90], end: [37.98, 126.10], heading: 137, speedKt: 410 },
  { source: "Northwest", start: [39.05, 125.55], end: [37.86, 126.62], heading: 142, speedKt: 390 },
  { source: "North", start: [39.45, 126.80], end: [38.08, 127.05], heading: 170, speedKt: 430 },
  { source: "North", start: [39.55, 127.45], end: [38.16, 127.64], heading: 174, speedKt: 420 },
  { source: "Northeast", start: [39.95, 128.45], end: [38.36, 128.30], heading: 186, speedKt: 405 },
  { source: "Northeast", start: [39.70, 129.10], end: [38.18, 128.78], heading: 195, speedKt: 385 },
];
const northKoreaTargets = [
  { id: "NKT-001", type: "SyntheticTarget", name: "Sunan airfield", category: "Airfield", priority: "high", lat: 39.1983, lon: 125.6702 },
  { id: "NKT-002", type: "SyntheticTarget", name: "Nampo port logistics", category: "Port", priority: "high", lat: 38.7375, lon: 125.4078 },
  { id: "NKT-003", type: "SyntheticTarget", name: "Hamhung industrial complex", category: "Industrial", priority: "medium", lat: 39.9800, lon: 127.3500 },
  { id: "NKT-004", type: "SyntheticTarget", name: "Sinpo inland support site", category: "Naval support", priority: "high", lat: 40.1200, lon: 127.9100 },
  { id: "NKT-005", type: "SyntheticTarget", name: "Chongjin port node", category: "Port", priority: "medium", lat: 41.7956, lon: 129.7758 },
  { id: "NKT-006", type: "SyntheticTarget", name: "Hyesan northern comms", category: "Comms", priority: "medium", lat: 41.4017, lon: 128.1778 },
  { id: "NKT-007", type: "SyntheticTarget", name: "Sinuiju transport node", category: "Transport", priority: "high", lat: 40.1006, lon: 124.3981 },
  { id: "NKT-008", type: "SyntheticTarget", name: "Kusong missile support", category: "Missile support", priority: "critical", lat: 39.9810, lon: 125.2440 },
];
const satelliteScenarioLanes = [
  { start: [33.2, 124.7], end: [40.3, 128.4] },
  { start: [33.8, 125.6], end: [40.8, 129.4] },
  { start: [34.5, 126.5], end: [41.0, 130.5] },
  { start: [35.3, 124.8], end: [41.1, 127.8] },
  { start: [32.9, 127.7], end: [39.8, 130.8] },
  { start: [33.6, 128.8], end: [40.1, 125.4] },
  { start: [34.3, 130.0], end: [40.4, 126.5] },
  { start: [35.2, 131.0], end: [40.9, 127.4] },
  { start: [32.8, 126.2], end: [38.9, 131.0] },
  { start: [33.5, 129.8], end: [39.4, 124.9] },
  { start: [34.9, 125.3], end: [41.2, 129.8] },
  { start: [35.8, 130.7], end: [40.5, 125.8] },
];

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await res.json();
  if (!res.ok) throw new Error(payload.error || `HTTP ${res.status}`);
  return payload;
}

// Calibrated against web/assets/korea_basemap.jpg (687x1024) so synthetic
// lat/lon points land on the drawn peninsula, not on a true GIS projection.
const MAP_IMAGE_WIDTH = 687;
const MAP_IMAGE_HEIGHT = 1024;
const MAP_LON_ORIGIN = { x: 250, lon: 125.0, pxPerDeg: 60.5 };
const MAP_LAT_ORIGIN = { y: 900, lat: 34, pxPerDeg: 103 };

function project(lat, lon) {
  const px = MAP_LON_ORIGIN.x + (lon - MAP_LON_ORIGIN.lon) * MAP_LON_ORIGIN.pxPerDeg;
  const py = MAP_LAT_ORIGIN.y - (lat - MAP_LAT_ORIGIN.lat) * MAP_LAT_ORIGIN.pxPerDeg;
  const x = (px / MAP_IMAGE_WIDTH) * 100;
  const y = (py / MAP_IMAGE_HEIGHT) * 100;
  return { x: Math.max(1, Math.min(99, x)), y: Math.max(1, Math.min(99, y)) };
}

function layoutMapFrame() {
  const map = $("map");
  const frame = $("mapFrame");
  if (!map || !frame) return;
  const cw = map.clientWidth;
  const info = $("mapInfo");
  const footerHeight = info ? info.offsetHeight + 8 : 0;
  const ch = Math.max(1, map.clientHeight - footerHeight);
  const ratio = MAP_IMAGE_WIDTH / MAP_IMAGE_HEIGHT;
  let width = cw;
  let height = width / ratio;
  if (height > ch) {
    height = ch;
    width = height * ratio;
  }
  frame.style.width = `${width}px`;
  frame.style.height = `${height}px`;
  frame.style.left = `${(cw - width) / 2}px`;
  frame.style.top = `${(ch - height) / 2}px`;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function lerp(a, b, progress) {
  return a + (b - a) * progress;
}

function frameProgress(frame = state.scenario.frame) {
  return clamp(frame / Math.max(state.scenario.totalFrames - 1, 1), 0, 1);
}

function kmBetween(a, b) {
  const toRad = (value) => (value * Math.PI) / 180;
  const r = 6371;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(h));
}

function nearestDetectionSite(lat, lon) {
  const point = { lat, lon };
  return detectionSites
    .map((site) => ({ ...site, distanceKm: kmBetween(point, site) }))
    .sort((a, b) => a.distanceKm - b.distanceKm)[0];
}

function scenarioTimestamp(frame = state.scenario.frame, plusMs = 0) {
  return new Date(scenarioStartMs + frame * state.scenario.intervalMs + plusMs).toISOString();
}

function currentScenarioTracks(frame = state.scenario.frame) {
  const progress = frameProgress(frame);
  const sourceTracks = state.graph?.tracks || [];
  return trackScenarioSpecs.map((spec, index) => {
    const base = sourceTracks[index] || {};
    const eased = clamp(progress + Math.sin((progress + index * 0.13) * Math.PI) * 0.015, 0, 1);
    const lat = lerp(spec.start[0], spec.end[0], eased);
    const lon = lerp(spec.start[1], spec.end[1], eased);
    const nearest = nearestDetectionSite(lat, lon);
    const detected = nearest.distanceKm <= detectionRangeKm;
    return {
      ...base,
      id: base.id || `SCN-TRK-${String(index + 1).padStart(2, "0")}`,
      type: "Track",
      lat,
      lon,
      heading: spec.heading,
      speedKt: spec.speedKt,
      identity: detected ? "suspect" : "unknown",
      sourceRegion: spec.source,
      detected,
      detectionSite: nearest.name,
      detectionSiteLat: nearest.lat,
      detectionSiteLon: nearest.lon,
      detectionRangeKm,
      nearestBase: nearest.name,
      nearestBaseKm: Math.round(nearest.distanceKm),
      lastSeen: scenarioTimestamp(frame),
      scenarioIndex: index + 1,
    };
  });
}

function currentScenarioSatellites(frame = state.scenario.frame) {
  const progress = frameProgress(frame);
  const satellites = state.graph?.satellites || [];
  return satellites.map((sat, index) => {
    const lane = satelliteScenarioLanes[index % satelliteScenarioLanes.length];
    const phase = (progress + index * 0.035) % 1;
    const lat = lerp(lane.start[0], lane.end[0], phase);
    const lon = lerp(lane.start[1], lane.end[1], phase);
    return { ...sat, lat, lon, scenarioLane: index + 1 };
  });
}

// Index is derived from the threat's own ID within its category (not array position), so the
// same threat always maps to the same display site whether it's rendered on the map or looked
// up again later for the inspector panel (see selectObject's displayThreat(detail.object) call).
function displayThreat(threat) {
  const allThreats = state.graph?.threats || [];
  if (threat.eventType === "SAM_RADAR_EMIT") {
    const radarIds = allThreats.filter((t) => t.eventType === "SAM_RADAR_EMIT").map((t) => t.id);
    const index = Math.max(0, radarIds.indexOf(threat.id));
    const site = radarSites[index % radarSites.length];
    return {
      ...threat,
      lat: site.lat,
      lon: site.lon,
      eventType: "RADAR_SITE",
      displayLabel: site.label,
      status: "ROK ground radar site",
      rangeKm: detectionRangeKm,
      severity: "medium",
      friendly: true,
    };
  }
  if (threat.eventType !== "MISSILE_LAUNCH_WARNING") return threat;
  const ringIds = allThreats.filter((t) => t.eventType === "MISSILE_LAUNCH_WARNING").map((t) => t.id);
  const index = Math.max(0, ringIds.indexOf(threat.id));
  const site = threatRingSites[index % threatRingSites.length];
  return {
    ...threat,
    lat: site.lat,
    lon: site.lon,
    eventType: site.eventType,
    displayLabel: site.label,
    status: site.status,
    severity: "critical",
  };
}

function scenarioStatusText() {
  const tracks = currentScenarioTracks();
  const detected = tracks.filter((track) => track.detected).length;
  const seconds = Math.round((state.scenario.frame * state.scenario.intervalMs) / 1000);
  const scope =
    state.mapScope === "north"
      ? `North Korea targets ${northKoreaTargets.length}`
      : state.mapScope === "all"
        ? `Combined COP · North Korea targets ${northKoreaTargets.length}`
        : "South Korea COP";
  return `${scope} | frame ${String(state.scenario.frame + 1).padStart(2, "0")}/20 | T+${String(seconds).padStart(2, "0")}s | detected ${detected}/${trackScenarioSpecs.length}`;
}

function scenarioTrackById(id) {
  return currentScenarioTracks().find((track) => track.id === id);
}

function syntheticTargetById(id) {
  return northKoreaTargets.find((target) => target.id === id);
}

function scenarioAlertForTrack(track, frame = state.scenario.frame) {
  return {
    id: `ALR-${track.id}`,
    type: "ThreatEvent",
    eventType: "Detection Alert",
    severity: "critical",
    firstSeen: scenarioTimestamp(frame, 1000),
    status: `${track.id} entered ${track.detectionSite} detection range from ${track.sourceRegion}.`,
    lat: track.lat,
    lon: track.lon,
    sourceTrackId: track.id,
    syntheticScenario: true,
    timelineKind: "detection",
  };
}

function scenarioRecommendationForTrack(track, frame = state.scenario.frame) {
  return {
    id: `REC-${track.id}`,
    type: "ThreatEvent",
    eventType: "Response Recommendation",
    severity: track.nearestBaseKm <= 320 ? "critical" : "high",
    firstSeen: scenarioTimestamp(frame, 1300),
    status: `Track ${track.id}: maintain radar custody, classify as inbound unknown, and prepare intercept handoff.`,
    lat: track.lat,
    lon: track.lon,
    sourceTrackId: track.id,
    syntheticScenario: true,
    timelineKind: "recommendation",
  };
}

function queueScenarioAlerts() {
  const tracks = currentScenarioTracks();
  const detectedIds = new Set(tracks.filter((track) => track.detected).map((track) => track.id));
  tracks.forEach((track) => {
    const newlyDetected = track.detected && !state.scenario.lastDetectedTrackIds.has(track.id);
    if (!newlyDetected || state.scenario.alertedTrackIds.has(track.id) || state.scenario.alertTimers.has(track.id)) return;
    const timer = setTimeout(() => {
      state.scenario.alertTimers.delete(track.id);
      state.scenario.alertedTrackIds.add(track.id);
      state.scenario.alertEvents.unshift(
        scenarioRecommendationForTrack(track),
        scenarioAlertForTrack(track),
      );
      renderTimeline();
    }, 1000);
    state.scenario.alertTimers.set(track.id, timer);
  });
  state.scenario.lastDetectedTrackIds = detectedIds;
}

function advanceScenarioFrame() {
  if (state.scenario.frame >= state.scenario.totalFrames - 1) {
    clearInterval(state.scenario.timer);
    state.scenario.timer = null;
    return;
  }
  state.scenario.frame += 1;
  renderScenarioMotion();
  renderTimeline();
  queueScenarioAlerts();
}

function startScenarioPlayback() {
  queueScenarioAlerts();
  if (state.scenario.timer) clearInterval(state.scenario.timer);
  state.scenario.timer = setInterval(advanceScenarioFrame, state.scenario.intervalMs);
}

function renderScenarioMotion() {
  if (state.vworld.ready) {
    renderVworldOverlays();
    return;
  }
  if (!$("mapFrame")) {
    renderSyntheticMap();
    return;
  }
  $("mapTitle").textContent = scenarioStatusText();
  renderSyntheticDynamicOverlays();
  markSelected();
}

// Panning is implemented by moving the zoomed layer's transform-origin: the layer is scaled
// around (focusX%, focusY%), so dragging just recomputes which point that origin should be so
// the content under the cursor tracks the mouse. Only meaningful once zoom > 1.
const mapDrag = { active: false, moved: false, startX: 0, startY: 0, startFocusX: 55, startFocusY: 48 };

function bindMapDrag() {
  const mapEl = $("map");

  mapEl.addEventListener("mousedown", (event) => {
    if (state.vworld.ready || state.map.zoom <= 1.001) return;
    mapDrag.active = true;
    mapDrag.moved = false;
    mapDrag.startX = event.clientX;
    mapDrag.startY = event.clientY;
    mapDrag.startFocusX = state.map.focusX;
    mapDrag.startFocusY = state.map.focusY;
    mapEl.classList.add("dragging");
  });

  window.addEventListener("mousemove", (event) => {
    if (!mapDrag.active) return;
    const dx = event.clientX - mapDrag.startX;
    const dy = event.clientY - mapDrag.startY;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) mapDrag.moved = true;
    const frame = $("mapFrame");
    const layer = $("mapLayer");
    if (!frame || !layer) return;
    const rect = frame.getBoundingClientRect();
    const factor = state.map.zoom - 1;
    if (factor <= 0) return;
    const nextFocusX = clamp(mapDrag.startFocusX - (dx / factor / rect.width) * 100, 0, 100);
    const nextFocusY = clamp(mapDrag.startFocusY - (dy / factor / rect.height) * 100, 0, 100);
    state.map.focusX = nextFocusX;
    state.map.focusY = nextFocusY;
    layer.style.transformOrigin = `${nextFocusX}% ${nextFocusY}%`;
  });

  window.addEventListener("mouseup", () => {
    mapDrag.active = false;
    mapEl.classList.remove("dragging");
  });

  // A drag that actually moved the map shouldn't also fire the marker/base click underneath it.
  mapEl.addEventListener(
    "click",
    (event) => {
      if (mapDrag.moved) {
        event.stopPropagation();
        event.preventDefault();
        mapDrag.moved = false;
      }
    },
    true
  );
}

function renderMap() {
  if (state.vworld.ready) {
    renderVworldMap();
    return;
  }
  renderSyntheticMap();
}

function renderSyntheticMap() {
  const map = $("map");
  map.classList.remove("vworld-active");
  map.classList.toggle("pannable", state.map.zoom > 1);
  if (!$("mapFrame")) initializeSyntheticMapShell(map);
  layoutMapFrame();
  const graph = state.graph;
  if (!graph) return;
  const layer = $("mapLayer");
  layer.style.transform = `scale(${state.map.zoom})`;
  layer.style.transformOrigin = `${state.map.focusX}% ${state.map.focusY}%`;
  layer.style.setProperty("--zoom", state.map.zoom);
  $("mapTitle").textContent = scenarioStatusText();
  $("zoomReadout").textContent = `x${state.map.zoom.toFixed(1)}`;
  renderSyntheticStaticOverlays();
  renderSyntheticDynamicOverlays();

  markSelected();
}

function initializeSyntheticMapShell(map) {
  map.innerHTML = `
    <div class="zoom-readout" id="zoomReadout"></div>
    <div class="map-frame" id="mapFrame">
      <div class="map-layer" id="mapLayer">
        <div class="map-image"></div>
        <div class="static-overlay" id="staticOverlay"></div>
        <div class="dynamic-overlay" id="dynamicOverlay"></div>
      </div>
    </div>
    <div class="map-info" id="mapInfo">
      <div class="map-title" id="mapTitle"></div>
      <div class="legend">
        <span><i class="swatch swatch-base"></i>Airbase</span>
        <span><i class="swatch swatch-track"></i>Track</span>
        <span><i class="swatch swatch-threat"></i>Detection/Threat</span>
        <span><i class="swatch swatch-route"></i>Mission</span>
        <span><i class="swatch swatch-sat"></i>Satellite</span>
      </div>
    </div>
  `;
}

// The 3 ROK radar sites are curated demo content (see radarSites) and must always be shown
// regardless of the zoom-based density cap — otherwise TEV-0008/TEV-0010 (radar sites 2-3)
// never appear because they sort past the generic threat slice limit. Radar sites are shown
// first; any remaining density budget is filled with other (e.g. GPS_JAMMING) threats. These
// only ever appear under the South Korea scope, since they're our own friendly sensors.
function selectedSouthThreats(graph, cap) {
  const radarThreats = graph.threats.filter((t) => t.eventType === "SAM_RADAR_EMIT").slice(0, radarSites.length);
  const otherThreats = graph.threats.filter((t) => t.eventType !== "SAM_RADAR_EMIT" && t.eventType !== "MISSILE_LAUNCH_WARNING");
  const fillCount = Math.max(0, cap - radarThreats.length);
  return radarThreats.concat(otherThreats.slice(0, fillCount));
}

// The Pyongyang/Wonsan SAM sites (see threatRingSites) are DPRK installations, so they belong
// in the North Korea scope alongside northKoreaTargets, not mixed in with the South Korea COP.
function selectedNorthThreats(graph) {
  return graph.threats.filter((t) => t.eventType === "MISSILE_LAUNCH_WARNING").slice(0, threatRingSites.length);
}

function renderSyntheticStaticOverlays() {
  const graph = state.graph;
  const layer = $("staticOverlay");
  if (!graph || !layer) return;
  layer.innerHTML = "";
  cityMarkers.forEach((city) => drawCity(layer, city));
  // "all" combines both the South Korea COP and North Korea target view in one render.
  const showSouth = state.mapScope === "south" || state.mapScope === "all";
  const showNorth = state.mapScope === "north" || state.mapScope === "all";
  if (showSouth && state.layers.routes) {
    graph.missions.slice(0, mapDensity().routes).forEach((mission) => drawRoute(layer, mission));
  }
  if (showSouth) {
    graph.bases.forEach((base) => drawNode(layer, base, "node base", base.id));
  }
  if (showSouth && state.layers.threats) {
    selectedSouthThreats(graph, mapDensity().threats).map(displayThreat).forEach((threat) => drawThreat(layer, threat));
  }
  if (showNorth && state.layers.threats) {
    northKoreaTargets.forEach((target) => drawNorthTarget(layer, target));
    selectedNorthThreats(graph).map(displayThreat).forEach((threat) => drawThreat(layer, threat));
  }
}

function renderSyntheticDynamicOverlays() {
  const layer = $("dynamicOverlay");
  if (!layer) return;
  layer.innerHTML = "";
  if (state.layers.tracks) {
    currentScenarioTracks().forEach((track) => drawTrack(layer, track));
  }
  if (state.layers.satellites) {
    currentScenarioSatellites().slice(0, mapDensity().satellites).forEach((sat) => drawSatellite(layer, sat, sat.lat, sat.lon));
  }
}

function mapDensity() {
  if (state.map.zoom < 1.25) return { routes: 6, threats: 3, tracks: 6, satellites: 4, labels: false };
  if (state.map.zoom < 1.8) return { routes: 14, threats: 5, tracks: 6, satellites: 8, labels: true };
  return { routes: 26, threats: 6, tracks: 6, satellites: 12, labels: true };
}

function vworldDensity() {
  const zoom = state.vworld.map?.getView?.().getZoom?.() || 7;
  if (zoom < 8) return { routes: 12, threats: 3, tracks: 6, satellites: 3 };
  if (zoom < 10) return { routes: 30, threats: 5, tracks: 6, satellites: 7 };
  return { routes: 90, threats: 6, tracks: 6, satellites: 12 };
}

function renderVworldMap() {
  const mapEl = $("map");
  mapEl.classList.add("vworld-active");
  if (!state.vworld.map) {
    mapEl.innerHTML = "";
    const { center, zoom } = vworldFocusRegions.all;
    state.vworld.baseLayer = new ol.layer.Tile({
      source: new ol.source.XYZ({
        url: `https://api.vworld.kr/req/wmts/1.0.0/${encodeURIComponent(state.vworld.apiKey)}/Base/{z}/{y}/{x}.png`,
        crossOrigin: "anonymous",
      }),
    });
    state.vworld.baseLayer.getSource().on("tileloaderror", () => {
      handleVworldMapFailure("VWorld tile load failed. Check the key, registered referrer, and 2D/WMTS permissions.");
    });
    state.vworld.vectorSource = new ol.source.Vector();
    state.vworld.vectorLayer = new ol.layer.Vector({ source: state.vworld.vectorSource });
    const mapOptions = {
      target: mapEl,
      layers: [state.vworld.baseLayer, state.vworld.vectorLayer],
      view: new ol.View({
        center: ol.proj.fromLonLat(center),
        zoom,
        minZoom: 6,
        maxZoom: 13,
      }),
    };
    const defaultControls = getOpenLayersDefaultControls();
    if (defaultControls) mapOptions.controls = defaultControls;
    state.vworld.map = new ol.Map(mapOptions);
    state.vworld.map.on("moveend", () => scheduleVworldRender());
    state.vworld.map.on("singleclick", (event) => {
      state.vworld.map.forEachFeatureAtPixel(event.pixel, (feature) => {
        const type = feature.get("argosType");
        const id = feature.get("argosId");
        if (type && id) selectObject(type, id, { watch: type.endsWith("Event") });
        return true;
      });
    });
  }
  renderVworldOverlays();
}

function scheduleVworldRender() {
  clearTimeout(state.vworld.renderTimer);
  state.vworld.renderTimer = setTimeout(renderVworldOverlays, 120);
}

function clearVworldOverlays() {
  state.vworld.vectorSource?.clear();
}

function renderVworldOverlays() {
  if (!state.vworld.map || !state.graph || !state.vworld.vectorSource) return;
  clearVworldOverlays();
  const density = vworldDensity();
  if (state.layers.routes) {
    state.graph.missions.slice(0, density.routes).forEach((mission) => drawVworldRoute(mission));
  }
  state.graph.bases.forEach((base) => drawVworldPoint(base, "AirBase", base.id, "#5ab0f2", 7));
  if (state.layers.threats) {
    // VWorld mode doesn't yet implement the South/North Korea scope toggle, so it keeps
    // showing the ROK radar sites only (matching its prior always-South-Korea behavior).
    selectedSouthThreats(state.graph, density.threats).map(displayThreat).forEach((threat) => drawVworldThreat(threat));
  }
  if (state.layers.tracks) {
    currentScenarioTracks().forEach((track) => drawVworldTrack(track));
  }
  if (state.layers.satellites) {
    currentScenarioSatellites().slice(0, density.satellites).forEach((sat) => drawVworldPoint(sat, "Satellite", sat.name, "#4fd08a", 6));
  }
}

function drawVworldPoint(obj, type, title, color, radius) {
  const feature = new ol.Feature({
    geometry: new ol.geom.Point(ol.proj.fromLonLat([Number(obj.lon), Number(obj.lat)])),
    argosType: type,
    argosId: obj.id,
    title,
  });
  feature.setStyle(new ol.style.Style({
    image: new ol.style.Circle({
      radius,
      fill: new ol.style.Fill({ color }),
      stroke: new ol.style.Stroke({ color: "#edf3f7", width: 1 }),
    }),
    text: new ol.style.Text({
      text: title,
      offsetY: -14,
      font: "11px Segoe UI, sans-serif",
      fill: new ol.style.Fill({ color: "#101418" }),
      stroke: new ol.style.Stroke({ color: "#ffffff", width: 3 }),
    }),
  }));
  state.vworld.vectorSource.addFeature(feature);
}

function drawVworldRoute(mission) {
  const start = mission.route[0];
  const end = mission.route[mission.route.length - 1];
  const feature = new ol.Feature({
    geometry: new ol.geom.LineString([
      ol.proj.fromLonLat([start.lon, start.lat]),
      ol.proj.fromLonLat([end.lon, end.lat]),
    ]),
    argosType: "Mission",
    argosId: mission.id,
    title: mission.callsign,
  });
  feature.setStyle(new ol.style.Style({
    stroke: new ol.style.Stroke({ color: "rgba(240,184,74,.8)", width: state.vworld.map.getView().getZoom() >= 10 ? 3 : 2 }),
  }));
  state.vworld.vectorSource.addFeature(feature);
}

function drawVworldThreat(threat) {
  const radiusBySeverity = { critical: 85000, high: 65000, medium: 45000, low: 30000 };
  const radius = threat.rangeKm ? Number(threat.rangeKm) * 1000 : radiusBySeverity[threat.severity] || 45000;
  const color = threat.friendly ? "#a255ff" : "#e35d5b";
  const feature = new ol.Feature({
    geometry: new ol.geom.Circle(
      ol.proj.fromLonLat([Number(threat.lon), Number(threat.lat)]),
      radius
    ),
    argosType: "ThreatEvent",
    argosId: threat.id,
  });
  feature.setStyle(new ol.style.Style({
    stroke: new ol.style.Stroke({ color: threat.friendly ? "rgba(162,85,255,.55)" : "rgba(227,93,91,.55)", width: 1 }),
    fill: new ol.style.Fill({ color: threat.friendly ? "rgba(162,85,255,.12)" : "rgba(227,93,91,.12)" }),
  }));
  state.vworld.vectorSource.addFeature(feature);
  drawVworldPoint(threat, "ThreatEvent", threat.displayLabel || threat.id, color, 8);
}

function drawVworldTrack(track) {
  const color = track.identity === "suspect" ? "#e35d5b" : track.identity === "unknown" ? "#f0b84a" : "#5ab0f2";
  const feature = new ol.Feature({
    geometry: new ol.geom.Point(ol.proj.fromLonLat([Number(track.lon), Number(track.lat)])),
    argosType: "Track",
    argosId: track.id,
    title: `${track.id} ${track.identity}`,
  });
  feature.setStyle(new ol.style.Style({
    image: new ol.style.RegularShape({
      points: 3,
      radius: 8,
      rotation: ((Number(track.heading) || 0) * Math.PI) / 180,
      fill: new ol.style.Fill({ color }),
      stroke: new ol.style.Stroke({ color: "#101418", width: 1 }),
    }),
  }));
  state.vworld.vectorSource.addFeature(feature);
}

function drawCity(map, city) {
  const p = project(city.lat, city.lon);
  const marker = document.createElement("div");
  marker.className = "city-marker";
  marker.style.left = `${p.x}%`;
  marker.style.top = `${p.y}%`;
  marker.textContent = city.name;
  map.appendChild(marker);
}

function drawNode(map, obj, cls, label, options = {}) {
  const p = project(obj.lat, obj.lon);
  const node = document.createElement("button");
  node.className = cls;
  node.style.left = `${p.x}%`;
  node.style.top = `${p.y}%`;
  node.title = label;
  node.dataset.type = obj.type;
  node.dataset.id = obj.id;
  node.addEventListener("click", () => selectObject(obj.type, obj.id));
  map.appendChild(node);

  if (options.skipLabel) return;

  const text = document.createElement("button");
  text.className = "label";
  text.style.left = `${p.x}%`;
  text.style.top = `${p.y}%`;
  text.textContent = label;
  text.dataset.type = obj.type;
  text.dataset.id = obj.id;
  text.addEventListener("click", () => selectObject(obj.type, obj.id));
  map.appendChild(text);
}

function drawRoute(map, mission) {
  const start = mission.route[0];
  const end = mission.route[mission.route.length - 1];
  const a = project(start.lat, start.lon);
  const b = project(end.lat, end.lon);
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const line = document.createElement("button");
  line.className = "route";
  line.style.left = `${a.x}%`;
  line.style.top = `${a.y}%`;
  line.style.width = `${Math.sqrt(dx * dx + dy * dy)}%`;
  line.style.transform = `rotate(${Math.atan2(dy, dx)}rad) scaleY(calc(1 / var(--zoom, 1)))`;
  line.title = `${mission.callsign} ${mission.missionType}`;
  line.dataset.type = "Mission";
  line.dataset.id = mission.id;
  line.addEventListener("click", () => selectObject("Mission", mission.id));
  map.appendChild(line);

  if (!mapDensity().labels) return;
  const p = project((start.lat + end.lat) / 2, (start.lon + end.lon) / 2);
  const text = document.createElement("button");
  text.className = "route-label";
  text.style.left = `${p.x}%`;
  text.style.top = `${p.y}%`;
  text.textContent = mission.callsign;
  text.dataset.type = "Mission";
  text.dataset.id = mission.id;
  text.addEventListener("click", () => selectObject("Mission", mission.id));
  map.appendChild(text);
}

function drawThreat(map, threat) {
  const p = project(threat.lat, threat.lon);
  const friendlyCls = threat.friendly ? " friendly" : "";
  const ring = document.createElement("button");
  ring.className = `threat-ring severity-${threat.severity}${friendlyCls}`;
  ring.style.left = `${p.x}%`;
  ring.style.top = `${p.y}%`;
  if (threat.rangeKm) {
    const size = clamp(Number(threat.rangeKm) * 0.42, 110, 210);
    ring.style.width = `${size}px`;
    ring.style.height = `${size}px`;
  }
  ring.title = `${threat.displayLabel || threat.id} (${threat.eventType})`;
  ring.dataset.type = "ThreatEvent";
  ring.dataset.id = threat.id;
  ring.addEventListener("click", () => selectObject("ThreatEvent", threat.id));
  map.appendChild(ring);
  drawNode(map, threat, `node threat severity-${threat.severity}${friendlyCls}`, threat.displayLabel || threat.id, { skipLabel: true });
}

function drawNorthTarget(map, target) {
  const p = project(target.lat, target.lon);
  const node = document.createElement("button");
  node.className = `north-target priority-${target.priority}`;
  node.style.left = `${p.x}%`;
  node.style.top = `${p.y}%`;
  node.title = `${target.id} ${target.name} ${target.category}`;
  node.dataset.type = target.type;
  node.dataset.id = target.id;
  node.addEventListener("click", () => selectSyntheticTarget(target));
  map.appendChild(node);

  if (!mapDensity().labels) return;
  const text = document.createElement("button");
  text.className = "target-label";
  text.style.left = `${p.x}%`;
  text.style.top = `${p.y}%`;
  text.textContent = target.id;
  text.dataset.type = target.type;
  text.dataset.id = target.id;
  text.addEventListener("click", () => selectSyntheticTarget(target));
  map.appendChild(text);
}

function drawTrack(map, track) {
  const p = project(track.lat, track.lon);
  const node = document.createElement("button");
  node.className = `track-node ${track.identity} ${track.detected ? "detected" : "pre-detect"}`;
  node.style.left = `${p.x}%`;
  node.style.top = `${p.y}%`;
  node.style.transform = `translate(-50%, -50%) rotate(${track.heading}deg) scale(calc(1 / var(--zoom, 1)))`;
  node.title = `${track.id} ${track.sourceRegion} ${track.identity} ${track.speedKt}kt / ${track.detectionSite} ${track.nearestBaseKm}km`;
  node.dataset.type = "Track";
  node.dataset.id = track.id;
  node.addEventListener("click", () => selectObject("Track", track.id));
  map.appendChild(node);
}

function drawSatellite(map, sat, lat, lon) {
  const p = project(lat, lon);
  const node = document.createElement("button");
  node.className = "node sat";
  node.style.left = `${p.x}%`;
  node.style.top = `${p.y}%`;
  node.title = `${sat.name} ${sat.sensorType} lane ${sat.scenarioLane || "-"}`;
  node.dataset.type = "Satellite";
  node.dataset.id = sat.id;
  node.addEventListener("click", () => selectObject("Satellite", sat.id));
  map.appendChild(node);
}

function buildEventRow(event) {
  const div = document.createElement("button");
  const lane = event.type === "SpaceEvent" ? "space" : "threat";
  div.className = `event severity-${event.severity || "medium"} lane-${lane} ${event.syntheticScenario ? "scenario-alert" : ""} ${event.timelineKind ? `timeline-${event.timelineKind}` : ""}`;
  div.dataset.type = event.type;
  div.dataset.id = event.id;
  div.innerHTML = `
    <span class="event-time">${formatTime(event.firstSeen || event.tca)}</span>
    <strong>${event.id} ${event.eventType}</strong>
    <p>${event.severity || "medium"} · ${event.status || event.satelliteId || ""}</p>
  `;
  div.addEventListener("click", () => {
    if (event.syntheticScenario && event.sourceTrackId) {
      selectObject("Track", event.sourceTrackId);
      return;
    }
    selectObject(event.type, event.id, { watch: true });
  });
  return div;
}

// The candidate pool grows with map zoom (mapDensity().threats), then we trim from the end
// until the rendered rows actually fit the panel without overflowing/scrolling.
function timelineZoomCapacity() {
  const density = mapDensity();
  return density.threats + Math.round(density.tracks / 3);
}

function renderTimeline() {
  const timeline = $("timeline");
  const zoom = state.map.zoom;
  timeline.classList.toggle("density-compact", zoom >= 1.25 && zoom < 2.5);
  timeline.classList.toggle("density-tight", zoom >= 2.5);
  const candidates = filteredEvents().slice(0, timelineZoomCapacity());
  timeline.innerHTML = "";
  if (!candidates.length) {
    const empty = document.createElement("div");
    empty.className = "timeline-empty";
    empty.textContent = "Monitoring live detections...";
    timeline.appendChild(empty);
  } else {
    candidates.forEach((event) => timeline.appendChild(buildEventRow(event)));
  }
  while (timeline.children.length > 1 && timeline.scrollHeight > timeline.clientHeight) {
    timeline.removeChild(timeline.lastElementChild);
  }
  markSelected();
}

function filteredEvents() {
  const scenarioEvents = state.scenario.alertEvents.filter((event) => state.eventFilter === "all" || event.type === state.eventFilter);
  return [...scenarioEvents].sort((a, b) => eventTime(b).localeCompare(eventTime(a)));
}

function eventTime(event) {
  return event.firstSeen || event.tca || "";
}

async function selectObject(type, id, options = {}) {
  const syntheticTarget = type === "SyntheticTarget" ? syntheticTargetById(id) : null;
  if (syntheticTarget) {
    selectSyntheticTarget(syntheticTarget);
    return;
  }
  state.selected = { type, id };
  state.selectedEventId = type.endsWith("Event") ? id : state.selectedEventId;
  markSelected();
  $("agentContext").textContent = `${type}:${id} selected`;

  const detail = await api(`/api/neighborhood/${encodeURIComponent(type)}/${encodeURIComponent(id)}`);
  const scenarioTrack = type === "Track" ? scenarioTrackById(id) : null;
  if (scenarioTrack && detail.object) {
    detail.object = {
      ...detail.object,
      ...scenarioTrack,
      sourceRegion: scenarioTrack.sourceRegion,
      detectionStatus: scenarioTrack.detected ? "detected" : "not yet inside detection range",
      detectionSite: scenarioTrack.detectionSite,
      detectionDistanceKm: scenarioTrack.nearestBaseKm,
    };
  }
  if (type === "ThreatEvent" && detail.object) {
    detail.object = displayThreat(detail.object);
  }
  renderInspector(detail);

  if (options.watch || type.endsWith("Event")) {
    const payload = await api("/api/watch", {
      method: "POST",
      body: JSON.stringify({ type, id }),
    });
    addMessage(`Watch ${id}`, payload, "agent");
    renderResponseSummary(payload);
  } else {
    addMessage("Selected Object", {
      answer: `${type}:${id} selected. Review related links and properties, then ask a response question if needed.`,
      evidence: [{ type, id, label: id }],
    }, "agent");
  }
}

function selectSyntheticTarget(target) {
  state.selected = { type: target.type, id: target.id };
  markSelected();
  $("agentContext").textContent = `${target.type}:${target.id} selected`;
  renderInspector({
    object: target,
    outgoing: [],
    incoming: [],
  });
  addMessage("Selected Target", {
    answer: `${target.id} ${target.name} selected. Category: ${target.category}, priority: ${target.priority}.`,
    evidence: [{ type: target.type, id: target.id, label: target.name }],
  }, "agent");
}

function markSelected() {
  document.querySelectorAll("[data-type][data-id]").forEach((el) => {
    const active = state.selected && el.dataset.type === state.selected.type && el.dataset.id === state.selected.id;
    el.classList.toggle("selected", Boolean(active));
  });
}

function renderInspector(payload) {
  const obj = payload.object;
  const outgoing = payload.outgoing || [];
  const incoming = payload.incoming || [];
  $("inspector").innerHTML = `
    <div class="inspector-head">
      <div>
        <strong>${escapeHtml(labelFor(obj))}</strong>
        <span>${escapeHtml(obj.type)}:${escapeHtml(obj.id)}</span>
      </div>
      ${obj.type.endsWith("Event") ? `<button id="inspectWatch">Watch</button>` : `<button id="inspectAsk">Ask</button>`}
    </div>
    <div class="field-grid">${objectFields(obj).map(([key, value]) => `
      <div><span>${escapeHtml(key)}</span><strong>${escapeHtml(formatValue(value))}</strong></div>
    `).join("")}</div>
    <div class="relation-list">
      <h3>Related Links</h3>
      ${[...outgoing, ...incoming].slice(0, 10).map(renderRelation).join("") || `<p class="muted">No direct links</p>`}
    </div>
  `;

  const watchBtn = $("inspectWatch");
  if (watchBtn) {
    watchBtn.addEventListener("click", () => selectObject(obj.type, obj.id, { watch: true }));
  }
  const askBtn = $("inspectAsk");
  if (askBtn) {
    askBtn.addEventListener("click", () => {
      const q = `${obj.id} detail, risk, and recommended response`;
      $("question").value = q;
      ask(q);
    });
  }
}

function renderRelation(item) {
  const related = item.related || {};
  const arrow = item.direction === "out" ? "->" : "<-";
  return `
    <button class="relation" data-type="${escapeHtml(related.type || "")}" data-id="${escapeHtml(related.id || "")}">
      <span>${escapeHtml(item.link.type)} ${arrow}</span>
      <strong>${escapeHtml(labelFor(related))}</strong>
    </button>
  `;
}

function bindRelationClicks() {
  $("inspector").addEventListener("click", (event) => {
    const target = event.target.closest(".relation");
    if (!target || !target.dataset.type || !target.dataset.id) return;
    selectObject(target.dataset.type, target.dataset.id);
  });
}

function addMessage(title, payload, role = "agent") {
  const chat = $("chat");
  const div = document.createElement("div");
  div.className = `message ${role} mode-${payload.mode || "unknown"}`;
  const chips = (payload.evidence || []).slice(0, 9).map((ev) => `
    <button class="chip" data-type="${escapeHtml(ev.type)}" data-id="${escapeHtml(ev.id)}">${escapeHtml(ev.type)}:${escapeHtml(ev.id)}</button>
  `).join("");
  div.innerHTML = `
    <strong>${escapeHtml(title)}</strong>
    <p>${escapeHtml(payload.answer || "")}</p>
    <div class="chips">${chips}</div>
  `;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  if (payload.impacts?.length) highlightImpacts(payload.impacts);
  if (payload.actions?.length) {
    payload.actions.forEach((action) => addAction(action));
  }
}

function addUserMessage(question) {
  addMessage("User", { answer: question, evidence: state.selected ? [{ ...state.selected, label: state.selected.id }] : [] }, "user");
}

function bindChatChips() {
  $("chat").addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    selectObject(chip.dataset.type, chip.dataset.id);
  });
}

function highlightImpacts(impacts) {
  document.querySelectorAll(".hot-label, .impact-route").forEach((el) => {
    el.classList.remove("hot-label", "impact-route");
  });
  const callsigns = new Set(impacts.slice(0, 10).map((impact) => impact.callsign));
  document.querySelectorAll(".route-label").forEach((label) => {
    if (callsigns.has(label.textContent)) label.classList.add("hot-label");
  });
  document.querySelectorAll(".route").forEach((route) => {
    const mission = state.graph.missions.find((item) => item.id === route.dataset.id);
    if (mission && callsigns.has(mission.callsign)) route.classList.add("impact-route");
  });
}

function renderResponseSummary(payload) {
  const severity = payload.impacts?.[0]?.severity || "medium";
  const count = payload.impacts?.length || 0;
  const actions = payload.actions?.map((action) => action.type).join(", ") || "continue monitoring";
  const chat = $("chat");
  const div = document.createElement("div");
  div.className = `message agent response-summary severity-${severity}`;
  div.innerHTML = `
    <strong>Response Summary</strong>
    <p>Impacted objects: ${fmt.format(count)}. Recommended actions: ${escapeHtml(actions)}.</p>
  `;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function addAction(action) {
  const chat = $("chat");
  const div = document.createElement("div");
  div.className = "action agent";
  div.innerHTML = `
    <strong>${escapeHtml(action.type)}</strong>
    <p>${escapeHtml(action.title)}</p>
    <p>${escapeHtml(action.effect)}</p>
    <code>${escapeHtml(JSON.stringify(action.parameters || {}))}</code>
  `;
  const btn = document.createElement("button");
  btn.textContent = "Approve";
  btn.addEventListener("click", async () => {
    const result = await api("/api/action/approve", {
      method: "POST",
      body: JSON.stringify({ action, actor: "operator" }),
    });
    btn.textContent = result.status === "approved" ? "Approved" : result.status;
    btn.disabled = true;
  });
  div.appendChild(btn);
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

let isAsking = false;

function setAskingUI(pending) {
  const submitBtn = $("askSubmitBtn");
  const input = $("question");
  if (submitBtn) submitBtn.disabled = pending;
  if (input) input.disabled = pending;
  document.querySelectorAll(".quick button").forEach((btn) => { btn.disabled = pending; });
  const schemaBtn = $("schemaBtn");
  if (schemaBtn) schemaBtn.disabled = pending;
  const inspectAskBtn = $("inspectAsk");
  if (inspectAskBtn) inspectAskBtn.disabled = pending;
}

function addThinkingIndicator() {
  const chat = $("chat");
  const div = document.createElement("div");
  div.className = "message agent thinking";
  div.innerHTML = `<span class="spinner" aria-hidden="true"></span> Generating response...`;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

async function ask(question) {
  if (!question.trim() || isAsking) return;
  isAsking = true;
  setAskingUI(true);
  addUserMessage(question);
  const thinking = addThinkingIndicator();
  try {
    const scopedQuestion = state.selected ? `${question} (selected object: ${state.selected.type}:${state.selected.id})` : question;
    const payload = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({ sessionId: state.sessionId, message: scopedQuestion }),
    });
    thinking.remove();
    addMessage("ARGOS", payload, "agent");
    if (payload.impacts?.length || payload.actions?.length) renderResponseSummary(payload);
  } catch (error) {
    thinking.remove();
    addMessage("Error", { answer: `Request failed: ${error.message}`, evidence: [] }, "agent");
  } finally {
    isAsking = false;
    setAskingUI(false);
  }
}

async function resetChat() {
  await api("/api/chat/reset", {
    method: "POST",
    body: JSON.stringify({ sessionId: state.sessionId }),
  });
  $("chat").innerHTML = "";
}

async function refreshChatStatus() {
  const statusEl = $("chatStatus");
  if (!statusEl) return;
  try {
    const { available, model, modelInstalled } = await api("/api/chat/status");
    const ok = available && modelInstalled;
    if (!available) {
      statusEl.textContent = "Ollama 미연결 (로컬 서버 실행 필요)";
    } else if (!modelInstalled) {
      statusEl.textContent = `모델 미설치: ollama pull ${model}`;
    } else {
      statusEl.textContent = `Ollama 연결됨 (${model})`;
    }
    statusEl.classList.toggle("chat-status-ok", ok);
    statusEl.classList.toggle("chat-status-warn", !ok);
  } catch (error) {
    statusEl.textContent = "Ollama 상태 확인 실패";
    statusEl.classList.add("chat-status-warn");
  }
}

async function aar() {
  const payload = await api("/api/aar", {
    method: "POST",
    body: JSON.stringify({ hours: 12 }),
  });
  const chat = $("chat");
  const div = document.createElement("div");
  div.className = "aar agent";
  div.innerHTML = `
    <strong>${escapeHtml(payload.title)}</strong>
    <p>${escapeHtml(payload.sections.overview)}</p>
    <p>${escapeHtml(payload.sections.planVsActual)}</p>
    <ul>${payload.sections.lessons.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}</ul>
  `;
  const btn = document.createElement("button");
  btn.textContent = "다운로드";
  btn.addEventListener("click", downloadAar);
  div.appendChild(btn);
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

async function downloadAar() {
  const res = await fetch("/api/aar/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hours: 12 }),
  });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "argos_aar.md";
  a.click();
  URL.revokeObjectURL(url);
}

async function init() {
  state.summary = await api("/api/summary");
  const counts = state.summary.stats.objectCounts;
  $("stats").innerHTML = `
    <strong>${fmt.format(state.summary.stats.objectCount)}</strong> objects /
    <strong>${fmt.format(state.summary.stats.linkCount)}</strong> links ·
    Threat ${fmt.format(counts.ThreatEvent || 0)} · Track ${fmt.format(counts.Track || 0)}
  `;
  state.graph = await api("/api/graph");
  state.events = await api("/api/events");
  renderMap();
  renderTimeline();
  bindRelationClicks();
  bindChatChips();
  addMessage("ARGOS", {
    answer: "ARGOS ontology service is ready. Select a map object or timeline event to begin response analysis.",
    evidence: [],
  }, "agent");
  startScenarioPlayback();
}

function objectFields(obj) {
  return Object.entries(obj)
    .filter(([key]) => !["route", "tle", "expected_impact", "marking"].includes(key))
    .slice(0, 10);
}

function labelFor(obj) {
  if (!obj) return "Unknown";
  return obj.callsign || obj.name || obj.eventType || obj.id || "Unknown";
}

function formatValue(value) {
  if (Array.isArray(value)) return value.join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  return value ?? "-";
}

function formatTime(value) {
  if (!value) return "-";
  return value.replace("2026-07-04T", "").replace(":00Z", "Z");
}

function setMapZoom(nextZoom, focus = {}) {
  if (state.vworld.ready && state.vworld.map) {
    const view = state.vworld.map.getView();
    const next = Math.max(6, Math.min(13, Math.round((view.getZoom() || 7) + (nextZoom > state.map.zoom ? 1 : -1))));
    view.setZoom(next);
    return;
  }
  state.map.zoom = Math.max(1, Math.min(4, nextZoom));
  if (focus.focusX !== undefined) state.map.focusX = focus.focusX;
  if (focus.focusY !== undefined) state.map.focusY = focus.focusY;
  renderMap();
  renderTimeline();
}

function loadVworldMapApi(apiKey) {
  if (window.ol) return Promise.resolve();
  if (state.vworld.loading) return state.vworld.loading;
  state.vworld.loading = (async () => {
    const params = new URLSearchParams({
      version: "2.0",
      apiKey,
      domain: window.location.origin,
    });
    await loadScript(`https://map.vworld.kr/js/vworldMapInit.js.do?${params.toString()}`, "vworld-map-init");
    const foundVworldOl = await waitFor(() => Boolean(window.ol), 2500);
    if (!foundVworldOl) {
      await loadOpenLayersFallback();
      const foundFallbackOl = await waitFor(() => Boolean(window.ol), 2500);
      if (!foundFallbackOl) {
        throw new Error("VWorld script and OpenLayers fallback both failed to expose the ol object.");
      }
      renderMapSecurityHint("VWorld did not expose ol directly, so the OpenLayers fallback is rendering VWorld WMTS tiles.");
    }
  })().catch((error) => {
    state.vworld.loading = false;
    throw error;
  });
  return state.vworld.loading;
}

function getOpenLayersDefaultControls() {
  if (typeof ol?.control?.defaults === "function") {
    return ol.control.defaults({ attribution: true, zoom: false });
  }
  if (typeof ol?.control?.defaults?.defaults === "function") {
    return ol.control.defaults.defaults({ attribution: true, zoom: false });
  }
  return undefined;
}

function loadScript(src, id) {
  return new Promise((resolve, reject) => {
    const existing = document.getElementById(id);
    if (existing) {
      if (existing.dataset.loaded === "true") resolve();
      else existing.addEventListener("load", () => resolve(), { once: true });
      return;
    }
    const script = document.createElement("script");
    script.id = id;
    script.async = true;
    script.src = src;
    script.onload = () => {
      script.dataset.loaded = "true";
      resolve();
    };
    script.onerror = () => reject(new Error(`${src} 로드에 실패했습니다.`));
    document.head.appendChild(script);
  });
}

function waitFor(predicate, timeoutMs) {
  const started = Date.now();
  return new Promise((resolve) => {
    const tick = () => {
      if (predicate()) {
        resolve(true);
        return;
      }
      if (Date.now() - started >= timeoutMs) {
        resolve(false);
        return;
      }
      setTimeout(tick, 50);
    };
    tick();
  });
}

async function loadOpenLayersFallback() {
  if (!document.getElementById("openlayers-css")) {
    const link = document.createElement("link");
    link.id = "openlayers-css";
    link.rel = "stylesheet";
    link.href = "https://cdn.jsdelivr.net/npm/ol@7.5.2/ol.css";
    document.head.appendChild(link);
  }
  await loadScript("https://cdn.jsdelivr.net/npm/ol@7.5.2/dist/ol.js", "openlayers-fallback");
}

async function activateVworldMap() {
  const input = $("vworldApiKey");
  const key = (input?.value || state.vworld.apiKey || "").trim();
  if (!key && !window.ol) {
    if ($("mapProviderStatus")) $("mapProviderStatus").textContent = "Synthetic";
    renderMapSecurityHint("VWorld key input is disabled. The current view uses Synthetic map mode.");
    return;
  }
  if ($("mapProviderStatus")) $("mapProviderStatus").textContent = "Loading...";
  try {
    state.vworld.failed = false;
    if (!window.ol) await loadVworldMapApi(key);
    if (input) input.value = "";
    state.vworld.apiKey = key || state.vworld.apiKey;
    state.vworld.ready = true;
    if ($("mapProviderStatus")) $("mapProviderStatus").textContent = "VWorld";
    renderMapSecurityHint("VWorld 2D map loaded.");
    renderMap();
  } catch (error) {
    handleVworldMapFailure(error.message);
  }
}

function activateSyntheticMap() {
  clearVworldOverlays();
  if (state.vworld.map) state.vworld.map.setTarget(null);
  state.vworld.ready = false;
  state.vworld.map = null;
  state.vworld.vectorSource = null;
  state.vworld.vectorLayer = null;
  state.vworld.baseLayer = null;
  state.vworld.failed = false;
  if ($("mapProviderStatus")) $("mapProviderStatus").textContent = "Synthetic";
  renderMap();
}

function handleVworldMapFailure(message) {
  if (state.vworld.failed) return;
  state.vworld.failed = true;
  clearVworldOverlays();
  if (state.vworld.map) state.vworld.map.setTarget(null);
  state.vworld.ready = false;
  state.vworld.map = null;
  state.vworld.vectorSource = null;
  state.vworld.vectorLayer = null;
  state.vworld.baseLayer = null;
  state.vworld.loading = false;
  if ($("mapProviderStatus")) $("mapProviderStatus").textContent = "VWorld failed · Fallback";
  renderMapSecurityHint(message);
  renderSyntheticMap();
  const isClientCompatibilityIssue = /ol\.|OpenLayers|function|object/.test(message);
  const nextStep = isClientCompatibilityIssue
    ? "This is likely a map library compatibility issue. Keep Synthetic fallback active and verify the OpenLayers compatibility layer."
    : `Register one of these referrers for the VWorld key: ${recommendedReferrers().join(", ")}.`;
  addMessage("VWorld 2D Map", {
    answer: `${message} ${nextStep}`,
    evidence: [],
  }, "agent");
}

function recommendedReferrers() {
  const origin = window.location.origin;
  const localhost = "http://localhost:8787";
  const loopback = "http://127.0.0.1:8787";
  return [...new Set([origin, loopback, localhost])];
}

function renderMapSecurityHint(prefix = "") {
  const hint = $("mapSecurityHint");
  if (!hint) return;
  const refs = recommendedReferrers();
  hint.innerHTML = `
    <strong>API key 보호 설정</strong>
    <span>${escapeHtml(prefix)}</span>
    <code>${refs.map(escapeHtml).join("</code><code>")}</code>
  `;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  }[char]));
}

$("askForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = $("question");
  ask(input.value);
  input.value = "";
});

document.querySelectorAll(".quick button").forEach((button) => {
  button.addEventListener("click", () => ask(button.dataset.q));
});
$("schemaBtn").addEventListener("click", () => ask("스키마 요약"));
$("resetChatBtn").addEventListener("click", resetChat);
$("aarBtn").addEventListener("click", aar);
refreshChatStatus();

document.querySelectorAll(".layer").forEach((button) => {
  button.addEventListener("click", () => {
    const layer = button.dataset.layer;
    state.layers[layer] = !state.layers[layer];
    button.classList.toggle("active", state.layers[layer]);
    renderMap();
  });
});

document.querySelectorAll(".scope").forEach((button) => {
  button.addEventListener("click", () => {
    state.mapScope = button.dataset.scope || "south";
    document.querySelectorAll(".scope").forEach((node) => node.classList.remove("active"));
    button.classList.add("active");
    renderMap();
    renderTimeline();
  });
});

document.querySelectorAll(".time-filter").forEach((button) => {
  button.addEventListener("click", () => {
    state.eventFilter = button.dataset.filter;
    document.querySelectorAll(".time-filter").forEach((node) => node.classList.remove("active"));
    button.classList.add("active");
    renderTimeline();
  });
});

$("zoomIn").addEventListener("click", () => setMapZoom(state.map.zoom + 0.2));
$("zoomOut").addEventListener("click", () => setMapZoom(state.map.zoom - 0.2));
$("zoomReset").addEventListener("click", () => {
  if (state.vworld.ready && state.vworld.map) {
    const focus = vworldFocusRegions.all;
    const view = state.vworld.map.getView();
    view.setCenter(ol.proj.fromLonLat(focus.center));
    view.setZoom(focus.zoom);
    $("focusRegion").value = "all";
    renderVworldOverlays();
    return;
  }
  state.map = { ...focusRegions.all };
  $("focusRegion").value = "all";
  renderMap();
  renderTimeline();
});
$("focusRegion").addEventListener("change", (event) => {
  if (state.vworld.ready && state.vworld.map) {
    const focus = vworldFocusRegions[event.target.value] || vworldFocusRegions.all;
    const view = state.vworld.map.getView();
    view.setCenter(ol.proj.fromLonLat(focus.center));
    view.setZoom(focus.zoom);
    renderVworldOverlays();
    return;
  }
  const focus = focusRegions[event.target.value] || focusRegions.all;
  state.map = { ...focus };
  renderMap();
  renderTimeline();
});
if ($("loadVworldMap")) $("loadVworldMap").addEventListener("click", activateVworldMap);

let mapResizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(mapResizeTimer);
  mapResizeTimer = setTimeout(() => {
    if (!state.vworld.ready) layoutMapFrame();
    renderTimeline();
  }, 100);
});
if ($("useSyntheticMap")) $("useSyntheticMap").addEventListener("click", activateSyntheticMap);
bindMapDrag();

init().catch((error) => {
  addMessage("Load error", { answer: error.message, evidence: [] }, "agent");
});


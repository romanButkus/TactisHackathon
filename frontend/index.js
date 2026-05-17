// =====================================================================
// CONFIG & TACTICAL RESOURCE PATHS
// =====================================================================
const BASE_URL = "http://localhost:8000";
const SIMULATION_JSON_PATH = "objects.json"; // Update to your exact local path
const LIVE_MAP_STATE_PATH = `${BASE_URL}/api/analysis/live`;
const SYNC_INTERVAL_MS = 10000; 
const WEATHER_SYNC_INTERVAL_MS = 1800000; 

// =====================================================================
// RUNTIME STATE RUNWAY
// =====================================================================
let map = null;
let activeRegion = null;
let regions = [];
let syncTimer = null;
let weatherSyncTimer = null;

// Core Engine Controls Runtime Flags
let useSimulationMode = true; 
let currentSimulationTick = 1;
let simulationPlayInterval = null;
let localSimulationData = null; // Hydrated via asynchronous file read
let liveMapState = null;

let baseMaps = {
  normal: null,
  topo: null
};

const layers = {
  satellite: null,
  terrain: null,
  drones: L.layerGroup(),
  enemies: L.layerGroup(),
  pois: L.layerGroup(),
  simulation: L.layerGroup() 
};

// =====================================================================
// SYSTEM INITIALIZATION CORE PIPELINE
// =====================================================================
window.addEventListener("load", async () => {
  updateClock();
  setInterval(updateClock, 1000);
  initMap();
  
  // High-priority operational load sequence
  await loadSimulationFile(); 
  await loadLiveMapState();
  await fetchRegions();
});

/**
 * Asynchronously hydrates the tracking runtime mapping matrix directly from asset storage
 */
async function loadSimulationFile() {
  try {
    const response = await fetch(SIMULATION_JSON_PATH);
    if (!response.ok) {
      throw new Error(`HTTP network error status: ${response.status}`);
    }
    const data = await response.json();
    
    // Safety check framework: mirror timeline tick frames if data exists but structure is sparse
    if (data && data.timeline) {
      const totalTicks = data.simulation_summary?.total_ticks_recorded || 6;
      for (let t = 2; t <= totalTicks; t++) {
        if (!data.timeline[`tick_${t}`] || !data.timeline[`tick_${t}`].objects || data.timeline[`tick_${t}`].objects.length === 0) {
          data.timeline[`tick_${t}`] = {
            ...data.timeline[`tick_${t}`],
            tick: t,
            timestamp_sec: t * (data.simulation_summary?.interval_seconds || 20),
            object_count: data.timeline.tick_1.object_count,
            objects: [...data.timeline.tick_1.objects]
          };
        }
      }
    }
    
    localSimulationData = data;
    console.log("Tactical simulation matrix successfully cached locally.");
  } catch (err) {
    console.error("CRITICAL: Failed to load simulation data file from disk:", err);
  }
}

async function loadLiveMapState() {
  try {
    const response = await fetch(LIVE_MAP_STATE_PATH);
    if (!response.ok) {
      throw new Error(`HTTP error status: ${response.status}`);
    }
    liveMapState = await response.json();
  } catch (err) {
    console.error("Failed to load live map state file from backend:", err);
  }
}

// =====================================================================
// CLOCK
// =====================================================================
function updateClock() {
  const now = new Date();
  document.getElementById("clock").textContent =
    String(now.getHours()).padStart(2, "0") + ":" +
    String(now.getMinutes()).padStart(2, "0") + ":" +
    String(now.getSeconds()).padStart(2, "0");
}

// =====================================================================
// MAP INIT
// =====================================================================
function initMap() {
  map = L.map("map", {
    center: [64.5, 26],
    zoom: 5,
    zoomControl: true,
    attributionControl: false,
    background: "#060a06",
  });

  baseMaps.normal = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 18,
    opacity: 0.4,
  });

  baseMaps.topo = L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
    maxZoom: 17,
    opacity: 0.6,
  });
  baseMaps.normal.addTo(map);

  layers.drones.addTo(map);
  layers.enemies.addTo(map);
  layers.pois.addTo(map);
  layers.simulation.addTo(map);

  map.on("mousemove", e => {
    document.getElementById("h-lat").textContent = e.latlng.lat.toFixed(4);
    document.getElementById("h-lng").textContent = e.latlng.lng.toFixed(4);
  });
  map.on("zoom", () => {
    document.getElementById("h-zoom").textContent = map.getZoom();
  });
}

// =====================================================================
// FETCH REGIONS
// =====================================================================
async function fetchRegions() {
  try {
    const res = await fetch(`${BASE_URL}/api/regions`);
    if (!res.ok) throw new Error(res.status);
    regions = await res.json();
    setBackendStatus(true);
    renderRegionList();
  } catch (err) {
    setBackendStatus(false);
    console.error("Failed to fetch regions:", err);
    setTimeout(fetchRegions, 5000);
  }
}

// =====================================================================
// REGION SELECTION
// =====================================================================
async function selectRegion(id) {
  activeRegion = id;

  document.querySelectorAll(".region-btn").forEach(b => b.classList.toggle("on", b.dataset.id === id));

  const region = regions.find(r => r.id === id);
  if (!region) return;

  document.getElementById("region-label").textContent = region.name.toUpperCase();
  document.getElementById("map-hud2").textContent = region.name.toUpperCase() + " — SELECTED AO";

  document.getElementById("t-min").textContent = region.elevation.min + " m";
  document.getElementById("t-max").textContent = region.elevation.max + " m";
  document.getElementById("t-relief").textContent = (region.elevation.max - region.elevation.min) + " m";

  await loadRegionImages(region);
  map.fitBounds(region.bbox, { padding: [20, 20] });

  startSync(id);

  fetchWeather(region.center[0], region.center[1]);
  if (weatherSyncTimer) clearInterval(weatherSyncTimer);
  weatherSyncTimer = setInterval(() => {
    fetchWeather(region.center[0], region.center[1]);
  }, WEATHER_SYNC_INTERVAL_MS);
}

async function loadRegionImages(region) {
  showLoading(true);
  if (layers.satellite) { map.removeLayer(layers.satellite); layers.satellite = null; }
  if (layers.terrain) { map.removeLayer(layers.terrain); layers.terrain = null; }

  const imageUrl = region.image_url.startsWith("http") ? region.image_url : `${BASE_URL}${region.image_url}`;
  layers.satellite = L.imageOverlay(imageUrl, region.bbox, { opacity: 1, interactive: false }).addTo(map);

  layers.satellite.on("load", () => showLoading(false));
  layers.satellite.on("error", () => { showLoading(false); console.error("Overlay load crash:", imageUrl); });

  if (region.terrain_url) {
    const terrainUrl = region.terrain_url.startsWith("http") ? region.terrain_url : `${BASE_URL}${region.terrain_url}`;
    layers.terrain = L.imageOverlay(terrainUrl, region.bbox, { opacity: 0.6, interactive: false }).addTo(map);
  }
}

function startSync(regionId) {
  if (syncTimer) clearInterval(syncTimer);
  syncOnce(regionId);
  syncTimer = setInterval(() => syncOnce(regionId), SYNC_INTERVAL_MS);
}

// =====================================================================
// SYNC RECON LOOP — Read from Runtime Local Memory Cache Layer
// =====================================================================
async function syncOnce(regionId) {
  try {
    // Only hit the live API endpoints for normal map assets, not the simulation data
    let [droneData, objectData, intelData, analysisData] = await Promise.all([
      fetch(`${BASE_URL}/api/drones?region=${regionId}`).then(r => r.json()),
      fetch(`${BASE_URL}/api/objects?region=${regionId}`).then(r => r.json()),
      fetch(`${BASE_URL}/api/intel?region=${regionId}`).then(r => r.json()),
      fetch(`${BASE_URL}/api/analysis?region=${regionId}`).then(r => r.json())
    ]);

    renderDroneOverlays(droneData);

    // If local file simulation mode is active, handle tracking purely through UI controls
    if (useSimulationMode && localSimulationData) {
      layers.enemies.clearLayers();
      layers.pois.clearLayers();
      
      const tickKey = `tick_${currentSimulationTick}`;
      const tickData = localSimulationData.timeline[tickKey];
      const region = regions.find(r => r.id === activeRegion);

      if (tickData && region) {
        objectData = tickData.objects.map(o => {
          const coords = o.global_pixel_center || o.local_pixel_center;
          const latLng = projectPixelToLatLng(coords, localSimulationData.simulation_summary.map_dimensions, region.bbox);
          return {
            category: "enemy",
            type: o.type === "COMMAND_POST" ? "cmd" : "comms",
            name: `${o.type.replace("_", " ")} [ID: ${o.id}]`,
            threat: o.type === "COMMAND_POST" ? "HIGH" : "MED",
            lat: latLng[0],
            lng: latLng[1]
          };
        });

        intelData = {
          sorties: 1,
          analyzed: tickData.objects.length,
          pending: 0
        };
      }

      // Keep rendering the active selected timeline frame from local file state
      renderSimulationTick(`tick_${currentSimulationTick}`);
      setupSimulationControls();
    } else {
      if(document.getElementById("sim-control-deck")) {
        document.getElementById("sim-control-deck").remove();
      }
      layers.simulation.clearLayers();
      renderObjectMarkers(objectData);
      renderObjectList(objectData);
    }

    await loadLiveMapState(); // Refresh AI analysis data on sync

    renderIntelPane(intelData, objectData);
    renderAnalysisPane(analysisData);

    setBackendStatus(true);
    document.getElementById("map-hud3").textContent = "LAST SYNC: " + new Date().toLocaleTimeString();
  } catch (err) {
    setBackendStatus(false);
    console.error("Sync telemetry loop crash encounter:", err);
  }
}

// =====================================================================
// SIMULATION RENDERING MODULE ENGINE
// =====================================================================
// =====================================================================
// RENDER SIMULATION TICK OBJECTS
// =====================================================================
function renderSimulationTick(tickKey) {
  layers.simulation.clearLayers();

  if (!localSimulationData || !localSimulationData.timeline[tickKey]) return;

  const region = regions.find((r) => r.id === activeRegion);
  if (!region) return;

  const tickData = localSimulationData.timeline[tickKey];
  const dimensions = localSimulationData.simulation_summary.map_dimensions;
  const objects = tickData.objects || [];

  // Update Left-Hand Panel List dynamically with Simulation Objects
  renderSimulationObjectList(objects, dimensions, region.bbox);

  // HUD Update element hook
  const hudLabel = document.getElementById("map-hud2");
  if (hudLabel) {
    hudLabel.textContent = `${region.name.toUpperCase()} — TICK ${tickData.tick} [${tickData.object_count} DETECTIONS]`;
  }

  objects.forEach((obj) => {
    // Fallback to local coordinates if global fields are empty
    const pixelCoordinates = obj.global_pixel_center || obj.local_pixel_center;
    if (!pixelCoordinates) return;

    // Run projection
    const latLng = projectPixelToLatLng(
      pixelCoordinates,
      dimensions,
      region.bbox
    );

    // Styling based on object classification types
    const isComms = obj.type === "COMMS_CENTER";
    const markerColor = isComms ? "#3b82f6" : "#ef4444"; // Comms Blue vs Command Red
    const borderRadius = isComms ? "3px" : "50%";

    // Build customized DOM asset node marker
    const icon = L.divIcon({
      html: `
                <div class="sim-marker" style="
                    width: 16px;
                    height: 16px;
                    background: ${markerColor};
                    border: 2px solid #ffffff;
                    border-radius: ${borderRadius};
                    box-shadow: 0 0 8px ${markerColor};
                    position: relative;
                ">
                    <span style="
                        position: absolute;
                        top: -18px;
                        left: 50%;
                        transform: translateX(-50%);
                        font-size: 9px;
                        color: #ffffff;
                        font-weight: bold;
                        background: rgba(0,0,0,0.7);
                        padding: 1px 3px;
                        border-radius: 2px;
                        white-space: nowrap;
                    ">ID:${obj.id}</span>
                </div>`,
      className: "",
      iconSize: [16, 16],
      iconAnchor: [8, 8],
    });

    // Add interactive popups including crop-snapshot preview structures
    const popupContent = `
            <div style="color: #ffffff; background: #111; padding: 5px; border-radius: 4px; font-family: monospace;">
                <b style="color: #4ade80;">${obj.type}</b><br>
                Sector ID: ${obj.sector}<br>
                Pixels: X:${pixelCoordinates[0]} Y:${pixelCoordinates[1]}<br>
                <hr style="border-color: #333; margin: 4px 0;">
                <div style="text-align:center; margin-top:5px;">
                    <img src="${BASE_URL}/${obj.image}" style="max-width:110px; border:1px solid #4ade80;" alt="crop snapshot"/>
                </div>
            </div>
        `;

    L.marker(latLng, { icon }).bindPopup(popupContent).addTo(layers.simulation);
  });
}

function renderSimulationObjectList(simObjects, dimensions, bbox) {
  const el = document.getElementById("object-list");
  if (!simObjects || !simObjects.length) {
    el.innerHTML = '<div class="empty-msg">NO OBJECTS DETECTED</div>';
    return;
  }

  el.innerHTML = simObjects.map(obj => {
    const coords = obj.global_pixel_center || obj.local_pixel_center;
    const projectedLatLng = projectPixelToLatLng(coords, dimensions, bbox);
    const markerColor = obj.type === "COMMS_CENTER" ? "#3b82f6" : "#ef4444";
    const shape = obj.type === "COMMS_CENTER" ? "border-radius:2px;" : "border-radius:50%;";

    return `
      <div class="object-item" onclick="map.setView([${projectedLatLng[0]}, ${projectedLatLng[1]}], 14)">
        <div class="obj-icon" style="background:${markerColor}; ${shape}"></div>
        <div class="obj-name">ID: ${obj.id} — Sector ${obj.sector}</div>
        <div class="obj-threat HIGH">${obj.type.replace("_", " ")}</div>
      </div>`;
  }).join("");
}

// =====================================================================
// PLAYBACK CONTROL PANEL
// =====================================================================
function setupSimulationControls() {
  if (document.getElementById("sim-control-deck") || !localSimulationData) return;

  const mapContainer = document.getElementById("map");
  const controlDeck = document.createElement("div");
  controlDeck.id = "sim-control-deck";
  controlDeck.style = "position:absolute; bottom:30px; left:50%; transform:translateX(-50%); z-index:1000; background:rgba(6,10,6,0.95); border:1px solid #4b7a4b; padding:10px 20px; border-radius:4px; display:flex; align-items:center; gap:15px; color:#fff; font-family:monospace; box-shadow:0 4px 15px rgba(0,0,0,0.5);";

  controlDeck.innerHTML = `
    <span style="color:#4ade80; font-weight:bold; font-size:11px;">TACTICAL PLAYBACK (JSON FILE RECON):</span>
    <button id="sim-prev-btn" style="background:#111; border:1px solid #4b7a4b; color:#fff; padding:2px 8px; cursor:pointer;">◀</button>
    <span id="sim-tick-display" style="min-width:75px; text-align:center;">TICK 1/6</span>
    <button id="sim-next-btn" style="background:#111; border:1px solid #4b7a4b; color:#fff; padding:2px 8px; cursor:pointer;">▶</button>
    <button id="sim-autoplay-btn" style="background:#1b3a1b; border:1px solid #4ade80; color:#4ade80; padding:2px 8px; cursor:pointer; font-weight:bold;">AUTO PLAY</button>
  `;
  mapContainer.appendChild(controlDeck);

  document.getElementById("sim-prev-btn").addEventListener("click", () => shiftTick(-1));
  document.getElementById("sim-next-btn").addEventListener("click", () => shiftTick(1));
  document.getElementById("sim-autoplay-btn").addEventListener("click", toggleAutoplay);
}

function shiftTick(direction) {
  if(!localSimulationData) return;
  const maxTicks = localSimulationData.simulation_summary.total_ticks_recorded;
  currentSimulationTick += direction;
  if (currentSimulationTick < 1) currentSimulationTick = maxTicks;
  if (currentSimulationTick > maxTicks) currentSimulationTick = 1;

  document.getElementById("sim-tick-display").textContent = `TICK ${currentSimulationTick}/${maxTicks}`;
  renderSimulationTick(`tick_${currentSimulationTick}`);
}

function toggleAutoplay() {
  const btn = document.getElementById("sim-autoplay-btn");
  if (simulationPlayInterval) {
    clearInterval(simulationPlayInterval);
    simulationPlayInterval = null;
    btn.textContent = "AUTO PLAY";
    btn.style.background = "#1b3a1b";
    btn.style.color = "#4ade80";
    btn.style.borderColor = "#4ade80";
  } else {
    btn.textContent = "STOP LOOP";
    btn.style.background = "#7f1d1d";
    btn.style.color = "#f87171";
    btn.style.borderColor = "#f87171";

    const pace = localSimulationData.simulation_summary.interval_seconds;
    simulationPlayInterval = setInterval(() => { shiftTick(1); }, pace * 100); 
  }
}

// =====================================================================
// GEOGRAPHIC BOUNDS COORDINATE PROJECTION TRANSFORMATION
// =====================================================================
function projectPixelToLatLng(pixelCoords, mapDimensions, bbox) {
  const [px, py] = pixelCoords;
  const [width, height] = mapDimensions;
  const [[minLat, minLng], [maxLat, maxLng]] = bbox;

  const lat = maxLat - (py / height) * (maxLat - minLat);
  const lng = minLng + (px / width) * (maxLng - minLng);

  return [lat, lng];
}

// =====================================================================
// BASELINE ENDPOINT FALLBACK PRERENDER MODULE HOOKS
// =====================================================================
function renderDroneOverlays(drones) {
  layers.drones.clearLayers();
  drones.forEach(d => {
    const overlay = L.imageOverlay(d.image_url.startsWith("http") ? d.image_url : `${BASE_URL}${d.image_url}`, d.bounds, { opacity: d.opacity ?? 0.8, interactive: true });
    const center = [(d.bounds[0][0] + d.bounds[1][0]) / 2, (d.bounds[0][1] + d.bounds[1][1]) / 2];
    const marker = L.marker(center, { icon: droneIcon() }).bindPopup(`<div><span style="color:#fbbf24">${d.name ?? d.id}</span><br><span style="color:#4b7a4b">Objects: </span>${d.object_count ?? "—"}<br><span style="color:#4b7a4b">Status: </span>${d.status ?? "—"}</div>`);
    layers.drones.addLayer(overlay);
    layers.drones.addLayer(marker);
  });
}

function renderObjectMarkers(objects) {
  layers.enemies.clearLayers();
  layers.pois.clearLayers();
  objects.forEach(obj => {
    const isEnemy = obj.category === "enemy";
    const icon = isEnemy ? enemyIcon(obj.threat) : poiIcon();
    const layer = isEnemy ? layers.enemies : layers.pois;
    L.marker([obj.lat, obj.lng], { icon }).bindPopup(`<div><span style="color:${isEnemy ? "#f87171" : "#fbbf24"}">${isEnemy ? "ENEMY OBJECT" : "POINT OF INTEREST"}</span><br>${obj.name}<br><span style="color:#4b7a4b">Type: </span>${obj.type}<br>${isEnemy ? `<span style="color:#4b7a4b">Threat: </span><span style="color:#f87171">${obj.threat}</span>` : ""}</div>`).addTo(layer);
  });
}

function renderObjectList(objects) {
  const el = document.getElementById("object-list");
  if (!objects.length) { el.innerHTML = '<div class="empty-msg">NO OBJECTS DETECTED</div>'; return; }
  el.innerHTML = objects.map(obj => `
    <div class="object-item" onclick="map.setView([${obj.lat},${obj.lng}], 12)">
      <div class="obj-icon" style="background:${obj.category === "enemy" ? "#f87171" : "#fbbf24"}; transform:rotate(${obj.category === "enemy" ? "45" : "0"}deg); border-radius:${obj.category === "poi" ? "50%" : "1px"}"></div>
      <div class="obj-name">${obj.name}</div>
      <div class="obj-threat ${obj.threat ?? ""}">${obj.threat ?? obj.category.toUpperCase()}</div>
    </div>`).join("");
}

function renderIntelPane(intel, objects) {
  const enemies = objects.filter(o => o.category === "enemy");
  document.getElementById("pane-intel").innerHTML = `
    <div class="dcard">
      <div class="dcard-title">Region Overview</div>
      <div class="drow"><span class="dlabel">Drone sorties</span><span class="dval">${intel.sorties}</span></div>
      <div class="drow"><span class="dlabel">Analyzed</span><span class="dval ok">${intel.analyzed}</span></div>
      <div class="drow"><span class="dlabel">Pending</span><span class="dval warn">${intel.pending}</span></div>
      <div class="drow"><span class="dlabel">Objects detected</span><span class="dval bad">${enemies.length}</span></div>
    </div>
    <div class="dcard">
      <div class="dcard-title">Confirmed Targets</div>
      ${enemies.length === 0 ? '<div class="empty-msg">NO TARGETS IN THIS AO</div>' : enemies.map(t => `<div class="target-item" onclick="map.setView([${t.lat},${t.lng}], 12)"><div class="ttype ${t.type ?? "log"}">${(t.type ?? "UNK").toUpperCase()}</div><div class="tname">${t.name}</div><div class="tthreat ${t.threat}">${t.threat}</div></div>`).join("")}
    </div>`;
}

function renderAnalysisPane(a) {
  const region = regions.find(r => r.id === activeRegion);
  const regionName = region ? region.name : null;
  const stateKey = liveMapState && regionName ? Object.keys(liveMapState).find(k => k.includes(regionName)) : null;
  const state = stateKey ? liveMapState[stateKey] : null;

  if (state) {
    const ma = state.master_analysis;
    const mods = state.modules;
    const color = ma.overall_risk_score > 7 ? "#f87171" : ma.overall_risk_score > 4 ? "#fbbf24" : "#4ade80";

    document.getElementById("pane-analysis").innerHTML = `
      <div class="dcard">
        <div class="dcard-title">AI Master Analysis</div>
        <div class="score-row">
            <div class="score-hdr"><span>Overall Risk Score</span><span style="color:${color}">${ma.overall_risk_score}/10</span></div>
            <div class="score-trk"><div class="score-fill" style="width:${ma.overall_risk_score * 10}%; background:${color}"></div></div>
        </div>
        <div style="font-size:11px; margin-top:8px; line-height:1.4; color:#d1d5db;">${ma.integrated_summary}</div>
      </div>
      <div class="dcard">
        <div class="dcard-title">Flight Recommendation</div>
        <div class="rec ${ma.overall_risk_score > 7 ? 'nogo' : ma.overall_risk_score > 4 ? 'warn' : 'go'}">${ma.flight_recommendation}</div>
      </div>
      <div class="dcard">
        <div class="dcard-title">Module Insights</div>
        <div style="margin-bottom: 8px;">
            <strong style="color:#fbbf24;">Weather (${mods.weather.severity}):</strong> 
            <span style="font-size:11px; color:#d1d5db;">${mods.weather.impact_statement}</span>
        </div>
        <div style="margin-bottom: 8px;">
            <strong style="color:#f87171;">Objects (${mods.objects.hazard_level}):</strong> 
            <span style="font-size:11px; color:#d1d5db;">${mods.objects.object_summary}</span>
        </div>
        <div>
            <strong style="color:#4ade80;">Terrain (${mods.elevation.terrain_type}):</strong> 
            <span style="font-size:11px; color:#d1d5db;">${mods.elevation.elevation_summary}</span>
        </div>
      </div>`;
  } else {
    const scores = [
      { label: "Strike viability", val: a.strike },
      { label: "Visibility / ISR", val: a.visibility },
      { label: "Accessibility", val: a.accessibility },
      { label: "Intel confidence", val: a.intel }
    ];
    document.getElementById("pane-analysis").innerHTML = `
      <div class="dcard">
        <div class="dcard-title">Strike Assessment</div>
        ${scores.map(s => {
          const color = s.val > 65 ? "#4ade80" : s.val > 40 ? "#fbbf24" : "#f87171";
          return `<div class="score-row"><div class="score-hdr"><span>${s.label}</span><span style="color:${color}">${s.val}%</span></div><div class="score-trk"><div class="score-fill" style="width:${s.val}%; background:${color}"></div></div></div>`;
        }).join("")}
      </div>
      <div class="dcard"><div class="dcard-title">AI Recommendation</div><div class="rec ${a.recType}">${a.rec}</div></div>`;
  }
}

// =====================================================================
// WEATHER SYSTEM EXTRACTION
// =====================================================================
async function fetchWeather(lat, lng) {
  try {
    const res = await fetch(`${BASE_URL}/api/weather?lat=${lat}&lng=${lng}`);
    if (!res.ok) throw new Error(res.status);
    const weather = await res.json() || {};

    const windKmh = weather.wind_speed ? (weather.wind_speed * 3.6).toFixed(1) : 0;
    const visKm = weather.visibility ? (weather.visibility / 1000).toFixed(1) : 10;
    const isFlyable = weather.wind_speed <= 10 && weather.visibility >= 2000;
    const precip = weather.rain ? `${weather.rain}mm Rain` : weather.snow ? `${weather.snow}mm Snow` : "None";

    updateWeatherCard({
      temp: weather.t2m !== undefined ? Math.round(weather.t2m) : 0,
      cond: weather.rain ? "Rain" : weather.snow ? "Snow" : "Clear",
      fly: isFlyable,
      wind: windKmh,
      windDir: weather.wind_deg ? `${weather.wind_deg}°` : "N/A",
      vis: visKm,
      clouds: weather.clouds !== undefined ? weather.clouds : 0,
      precip: precip
    });
  } catch (err) {
    console.error("Failed to fetch weather:", err);
  }
}

function updateWeatherCard(data) {
  document.getElementById("w-temp").textContent = (data.temp > 0 ? "+" : "") + data.temp + "°C";
  document.getElementById("w-temp").style.color = data.temp < 0 ? "#93c5fd" : data.temp < 10 ? "#4ade80" : "#fbbf24";
  document.getElementById("w-cond").textContent = data.cond;

  const flyBadge = document.getElementById("fly-badge");
  flyBadge.textContent = data.fly ? "DRONE OPS: GO" : "DRONE OPS: NO-GO";
  flyBadge.className = "fly-badge " + (data.fly ? "go" : "nogo");

  document.getElementById("w-wind-val").textContent = data.wind + " km/h " + data.windDir;
  document.getElementById("w-wind-bar").style.width = Math.min((data.wind / 40) * 100, 100) + "%";
  document.getElementById("w-wind-bar").className = "bar-fill " + (data.wind > 25 ? "r" : data.wind > 15 ? "y" : "g");

  document.getElementById("w-vis-val").textContent = data.vis + " km";
  document.getElementById("w-vis-bar").style.width = Math.min((data.vis / 15) * 100, 100) + "%";
  document.getElementById("w-vis-bar").className = "bar-fill " + (data.vis < 6 ? "r" : data.vis < 10 ? "y" : "g");

  document.getElementById("w-cloud-val").textContent = data.clouds + "%";
  document.getElementById("w-cloud-bar").style.width = data.clouds + "%";
  document.getElementById("w-cloud-bar").className = "bar-fill " + (data.clouds > 70 ? "r" : data.clouds > 50 ? "y" : "g");

  document.getElementById("w-precip").textContent = data.precip;
  document.getElementById("w-precip").className = "dval " + (data.precip === "None" ? "ok" : "warn");

  if (activeRegion) {
    const rb = document.getElementById("fly-rbadge-" + activeRegion);
    if (rb) {
      rb.textContent = data.fly ? "GO" : "NO-GO";
      rb.className = "rbadge " + (data.fly ? "go" : "nogo");
    }
  }
}

function renderRegionList() {
  document.getElementById("region-list").innerHTML = regions.map(r => `
    <div class="region-btn ${r.id === activeRegion ? "on" : ""}" data-id="${r.id}" onclick="selectRegion('${r.id}')">
      <div class="rdot" style="background:${r.color ?? "#4ade80"}"></div>
      <div class="rname">${r.name}</div>
      <div class="rbadge" id="fly-rbadge-${r.id}">—</div>
    </div>`).join("");
}

function toggleLayer(name, visible) {
  if (name === "drones" || name === "enemies") return;
  if (name === "satellite") {
    if (layers.satellite) { visible ? map.addLayer(layers.satellite) : map.removeLayer(layers.satellite); }
    if (visible) { map.removeLayer(baseMaps.normal); map.addLayer(baseMaps.topo); } 
    else { map.removeLayer(baseMaps.topo); map.addLayer(baseMaps.normal); }
  } else if (layers[name]) {
    visible ? map.addLayer(layers[name]) : map.removeLayer(layers[name]);
  }
}

function enemyIcon(threat) {
  const color = threat === "HIGH" ? "#f87171" : threat === "MED" ? "#fbbf24" : "#4ade80";
  return L.divIcon({ html: `<div style="width:12px; height:12px; background:${color}; border:1px solid rgba(0,0,0,.5); transform:rotate(45deg);"></div>`, className: "", iconSize: [12, 12], iconAnchor: [6, 6] });
}
function poiIcon() { return L.divIcon({ html: `<div style="width:10px; height:10px; background:#c084fc; border:1px solid #6b21a8; border-radius:50%;"></div>`, className: "", iconSize: [10, 10], iconAnchor: [5, 5] }); }
function droneIcon() { return L.divIcon({ html: `<div style="width:8px; height:8px; background:#fbbf24; border:1px solid #f59e0b; border-radius:50%;"></div>`, className: "", iconSize: [8, 8], iconAnchor: [4, 4] }); }
function showLoading(show) { document.getElementById("map-loading").style.display = show ? "flex" : "none"; }

function setBackendStatus(ok) {
  const badge = document.getElementById("backend-badge");
  const pulse = document.getElementById("sync-pulse");
  const txt = document.getElementById("sync-status");
  if (ok) {
    badge.textContent = "BACKEND: ONLINE"; badge.className = "conn-badge";
    pulse.className = "pulse"; txt.textContent = "SYNCED";
  } else {
    badge.textContent = "BACKEND: OFFLINE"; badge.className = "conn-badge error";
    pulse.className = "pulse error"; txt.textContent = "CONNECTION LOST";
  }
}

function switchTab(tab, el) {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("on"));
  document.querySelectorAll(".pane").forEach(p => p.classList.remove("on"));
  el.classList.add("on");
  document.getElementById("pane-" + tab).classList.add("on");
}
// =====================================================================
// RENDER SIMULATION TICK OBJECTS
// =====================================================================

function renderSimulationTick(tickKey) {
  layers.simulation.clearLayers();

  if (!localSimulationData || !localSimulationData.timeline[tickKey]) return;

  const region = regions.find((r) => r.id === activeRegion);
  if (!region) return;

  const tickData = localSimulationData.timeline[tickKey];
  const dimensions = localSimulationData.simulation_summary.map_dimensions;
  const objects = tickData.objects || [];

  // Update Left-Hand Panel List dynamically with Simulation Objects
  renderSimulationObjectList(objects, dimensions, region.bbox);

  // HUD Update element hook
  const hudLabel = document.getElementById("map-hud2");
  if (hudLabel) {
    hudLabel.textContent = `${region.name.toUpperCase()} — TICK ${tickData.tick} [${tickData.object_count} DETECTIONS]`;
  }

  objects.forEach((obj) => {
    // Fallback to local coordinates if global fields are empty
    const pixelCoordinates = obj.global_pixel_center || obj.local_pixel_center;
    if (!pixelCoordinates) return;

    // Run projection
    const latLng = projectPixelToLatLng(
      pixelCoordinates,
      dimensions,
      region.bbox
    );

    // Styling based on object classification types
    const isComms = obj.type === "COMMS_CENTER";
    const markerColor = isComms ? "#3b82f6" : "#ef4444"; // Comms Blue vs Command Red
    const borderRadius = isComms ? "3px" : "50%";

    // Build customized DOM asset node marker
    const icon = L.divIcon({
      html: `
                <div class="sim-marker" style="
                    width: 16px;
                    height: 16px;
                    background: ${markerColor};
                    border: 2px solid #ffffff;
                    border-radius: ${borderRadius};
                    box-shadow: 0 0 8px ${markerColor};
                    position: relative;
                ">
                    <span style="
                        position: absolute;
                        top: -18px;
                        left: 50%;
                        transform: translateX(-50%);
                        font-size: 9px;
                        color: #ffffff;
                        font-weight: bold;
                        background: rgba(0,0,0,0.7);
                        padding: 1px 3px;
                        border-radius: 2px;
                        white-space: nowrap;
                    ">ID:${obj.id}</span>
                </div>`,
      className: "",
      iconSize: [16, 16],
      iconAnchor: [8, 8],
    });

    // Add interactive popups including crop-snapshot preview structures
    const popupContent = `
            <div style="color: #ffffff; background: #111; padding: 5px; border-radius: 4px; font-family: monospace;">
                <b style="color: #4ade80;">${obj.type}</b><br>
                Sector ID: ${obj.sector}<br>
                Pixels: X:${pixelCoordinates[0]} Y:${pixelCoordinates[1]}<br>
                <hr style="border-color: #333; margin: 4px 0;">
                <div style="text-align:center; margin-top:5px;">
                    <img src="${BASE_URL}/${obj.image}" style="max-width:110px; border:1px solid #4ade80;" alt="crop snapshot"/>
                </div>
            </div>
        `;

    L.marker(latLng, { icon }).bindPopup(popupContent).addTo(layers.simulation);
  });
}

// =====================================================================
// NEW: RENDER SIMULATION OBJECTS TO LEFT SIDEBAR PANEL
// =====================================================================
function renderSimulationObjectList(simObjects, dimensions, bbox) {
  const el = document.getElementById("object-list");
  if (!simObjects || !simObjects.length) {
    el.innerHTML = '<div class="empty-msg">NO OBJECTS DETECTED</div>';
    return;
  }

  el.innerHTML = simObjects
    .map((obj) => {
      const coords = obj.global_pixel_center || obj.local_pixel_center;
      if (!coords) return "";

      // Calculate the explicit LatLng coordinate mapping layout for this target item row
      const projectedLatLng = projectPixelToLatLng(coords, dimensions, bbox);
      const markerColor = obj.type === "COMMS_CENTER" ? "#3b82f6" : "#ef4444";

      return `
      <div class="object-item" onclick="map.setView([${projectedLatLng[0]}, ${projectedLatLng[1]}], 14)">
        <div class="obj-icon" style="background:${markerColor}; border-radius:${obj.type === "COMMS_CENTER" ? "1px" : "50%"}"></div>
        <div class="obj-name">ID: ${obj.id} — Sector ${obj.sector}</div>
        <div class="obj-threat HIGH">${obj.type.replace("_", " ")}</div>
      </div>
    `;
    })
    .join("");
}
// =====================================================================
// TIMELINE PLAYBACK MANAGEMENT HUD CONTROLS
// =====================================================================
function setupSimulationControls() {
  if (document.getElementById("sim-control-deck")) return; // Guard duplicate builds

  const mapContainer = document.getElementById("map");
  const controlDeck = document.createElement("div");
  controlDeck.id = "sim-control-deck";

  // Style inline seamlessly matching your dark operational aesthetic layout design
  controlDeck.style = `
        position: absolute;
        bottom: 30px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 1000;
        background: rgba(6, 10, 6, 0.9);
        border: 1px solid #4b7a4b;
        padding: 10px 20px;
        border-radius: 4px;
        display: flex;
        align-items: center;
        gap: 15px;
        color: #fff;
        font-family: monospace;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    `;

  controlDeck.innerHTML = `
        <span style="color: #4ade80; font-weight: bold;">TACTICAL SIMULATION PLAYBACK:</span>
        <button id="sim-prev-btn" style="background:#111; border:1px solid #4b7a4b; color:#fff; padding:2px 8px; cursor:pointer;">◀</button>
        <span id="sim-tick-display">TICK 1/6</span>
        <button id="sim-next-btn" style="background:#111; border:1px solid #4b7a4b; color:#fff; padding:2px 8px; cursor:pointer;">▶</button>
        <button id="sim-autoplay-btn" style="background:#1b3a1b; border:1px solid #4ade80; color:#4ade80; padding:2px 8px; cursor:pointer; font-weight:bold;">AUTO PLAY</button>
    `;

  mapContainer.appendChild(controlDeck);

  // Click events binding hooks
  document
    .getElementById("sim-prev-btn")
    .addEventListener("click", () => shiftTick(-1));
  document
    .getElementById("sim-next-btn")
    .addEventListener("click", () => shiftTick(1));
  document
    .getElementById("sim-autoplay-btn")
    .addEventListener("click", toggleAutoplay);
}

function shiftTick(direction) {
  // Fix this line if it still says activeSimulationData
  if(!localSimulationData) return;
  
  const maxTicks = localSimulationData.simulation_summary.total_ticks_recorded;
  currentSimulationTick += direction;
  if (currentSimulationTick < 1) currentSimulationTick = maxTicks;
  if (currentSimulationTick > maxTicks) currentSimulationTick = 1;

  document.getElementById("sim-tick-display").textContent = `TICK ${currentSimulationTick}/${maxTicks}`;
  renderSimulationTick(`tick_${currentSimulationTick}`);
}

function toggleAutoplay() {
  const btn = document.getElementById("sim-autoplay-btn");
  if (simulationPlayInterval) {
    clearInterval(simulationPlayInterval);
    simulationPlayInterval = null;
    btn.textContent = "AUTO PLAY";
    btn.style.background = "#1b3a1b";
  } else {
    btn.textContent = "STOP LOOP";
    btn.style.background = "#7f1d1d";
    btn.style.color = "#f87171";
    btn.style.borderColor = "#f87171";

    // Loop automated tick steps dynamically utilizing configuration frame pacing metrics
    const intervalSec =
      localSimulationData?.simulation_summary.interval_seconds || 20;
    simulationPlayInterval = setInterval(() => {
      shiftTick(1);
    }, intervalSec * 100); // 2000ms playback presentation speeds feel perfect for debugging
  }
}
function projectPixelToLatLng(pixelCoords, mapDimensions, bbox) {
  const [px, py] = pixelCoords;
  const [width, height] = mapDimensions;
  
  // Destructure bounding box configuration limits
  const [[minLat, minLng], [maxLat, maxLng]] = bbox;

  // Linear Interpolation calculations mapping bounds accurately
  const lat = maxLat - (py / height) * (maxLat - minLat);
  const lng = minLng + (px / width) * (maxLng - minLng);

  return [lat, lng];
}
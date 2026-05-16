// =====================================================================
// CONFIG
// Change BASE_URL to your Python backend address (Flask / FastAPI)
// =====================================================================
const BASE_URL = "http://localhost:5000"
const SYNC_INTERVAL_MS = 10000 // poll backend every 10 seconds
const WEATHER_SYNC_INTERVAL_MS = 1800000 // poll weather every 30 minutes

// =====================================================================
// EXPECTED BACKEND API ENDPOINTS
//
// GET  /api/regions
//   Returns list of regions with satellite image path, bbox, elevation
//   [{ id, name, image_url, bbox, elevation: { min, max } }, ...]
//
// GET  /api/drones?region=<id>
//   Returns processed drone images for a region
//   [{ id, image_url, bounds: [[minLat,minLng],[maxLat,maxLng]], opacity }, ...]
//
// GET  /api/objects?region=<id>
//   Returns enemy objects and POIs detected in a region
//   [{ id, name, type, lat, lng, threat, category: 'enemy'|'poi' }, ...]
//
// GET  /api/intel?region=<id>
//   Returns intel summary for a region
//   { sorties, analyzed, pending, enemy_assessment: {...} }
//
// GET  /api/analysis?region=<id>
//   Returns strike analysis scores and recommendation
//   { strike, visibility, accessibility, intel, rec, recType }
//
// GET  /api/weather?lat=<lat>&lng=<lng>
//   Implemented by your team — call updateWeatherCard(data) with result
// =====================================================================

// =====================================================================
// STATE
// =====================================================================
let map = null
let activeRegion = null
let regions = []
let syncTimer = null
let weatherSyncTimer = null

// Leaflet layer groups — cleared and rebuilt on each sync
const layers = {
	satellite: null, // L.imageOverlay  — the region satellite PNG
	drones: L.layerGroup(),
	enemies: L.layerGroup(),
	pois: L.layerGroup(),
}

// =====================================================================
// INIT
// =====================================================================
window.addEventListener("load", async () => {
	updateClock()
	setInterval(updateClock, 1000)
	initMap()
	await fetchRegions()
})

// =====================================================================
// CLOCK
// =====================================================================
function updateClock() {
	const now = new Date()
	document.getElementById("clock").textContent =
		String(now.getHours()).padStart(2, "0") +
		":" +
		String(now.getMinutes()).padStart(2, "0") +
		":" +
		String(now.getSeconds()).padStart(2, "0")
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
		// Dark background while no satellite image is loaded
		background: "#060a06",
	})

	// Dark base tiles shown behind satellite PNG
	L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
		maxZoom: 18,
		opacity: 0.4,
	}).addTo(map)

	// Add layer groups to map
	layers.drones.addTo(map)
	layers.enemies.addTo(map)
	layers.pois.addTo(map)

	// HUD coordinate tracker
	map.on("mousemove", e => {
		document.getElementById("h-lat").textContent = e.latlng.lat.toFixed(4)
		document.getElementById("h-lng").textContent = e.latlng.lng.toFixed(4)
	})
	map.on("zoom", () => {
		document.getElementById("h-zoom").textContent = map.getZoom()
	})
}

// =====================================================================
// FETCH REGIONS FROM BACKEND
// =====================================================================
async function fetchRegions() {
	try {
		const res = await fetch(`${BASE_URL}/api/regions`)
		if (!res.ok) throw new Error(res.status)
		regions = await res.json()
		setBackendStatus(true)
		renderRegionList()
	} catch (err) {
		setBackendStatus(false)
		console.error("Failed to fetch regions:", err)
		// Retry after 5s
		setTimeout(fetchRegions, 5000)
	}
}

// =====================================================================
// REGION SELECTION
// =====================================================================
async function selectRegion(id) {
	activeRegion = id

	// Update left panel highlight
	document
		.querySelectorAll(".region-btn")
		.forEach(b => b.classList.toggle("on", b.dataset.id === id))

	const region = regions.find(r => r.id === id)
	if (!region) return

	// Update topbar and HUD
	document.getElementById("region-label").textContent =
		region.name.toUpperCase()
	document.getElementById("map-hud2").textContent =
		region.name.toUpperCase() + " — SELECTED AO"

	// Update terrain card
	document.getElementById("t-min").textContent = region.elevation.min + " m"
	document.getElementById("t-max").textContent = region.elevation.max + " m"
	document.getElementById("t-relief").textContent =
		region.elevation.max - region.elevation.min + " m"

	// Load satellite PNG for this region
	await loadSatelliteImage(region)

	// Fly map to region bounds
	map.fitBounds(region.bbox, { padding: [20, 20] })

	// Start syncing backend data for this region
	startSync(id)

	// Hook for your weather team:
	fetchWeather(region.center[0], region.center[1])
	if (weatherSyncTimer) clearInterval(weatherSyncTimer)
	weatherSyncTimer = setInterval(() => {
		fetchWeather(region.center[0], region.center[1])
	}, WEATHER_SYNC_INTERVAL_MS)
}

// =====================================================================
// SATELLITE IMAGE OVERLAY
// =====================================================================
async function loadSatelliteImage(region) {
	showLoading(true)

	// Remove previous satellite overlay if exists
	if (layers.satellite) {
		map.removeLayer(layers.satellite)
		layers.satellite = null
	}

	// region.image_url should be served by your Python backend
	// e.g. "http://localhost:5000/static/images/north_karelia_topo.png"
	const imageUrl = region.image_url.startsWith("http")
		? region.image_url
		: `${BASE_URL}${region.image_url}`

	layers.satellite = L.imageOverlay(imageUrl, region.bbox, {
		opacity: 1,
		interactive: false,
	}).addTo(map)

	layers.satellite.on("load", () => showLoading(false))
	layers.satellite.on("error", () => {
		showLoading(false)
		console.error("Failed to load satellite image:", imageUrl)
	})
}

// =====================================================================
// BACKEND SYNC — polls drones, objects, intel, analysis
// =====================================================================
function startSync(regionId) {
	if (syncTimer) clearInterval(syncTimer)
	syncOnce(regionId)
	syncTimer = setInterval(() => syncOnce(regionId), SYNC_INTERVAL_MS)
}

async function syncOnce(regionId) {
	try {
		// Fetch all data in parallel
		const [droneData, objectData, intelData, analysisData] = await Promise.all([
			fetch(`${BASE_URL}/api/drones?region=${regionId}`).then(r => r.json()),
			fetch(`${BASE_URL}/api/objects?region=${regionId}`).then(r => r.json()),
			fetch(`${BASE_URL}/api/intel?region=${regionId}`).then(r => r.json()),
			fetch(`${BASE_URL}/api/analysis?region=${regionId}`).then(r => r.json()),
		])

		renderDroneOverlays(droneData)
		renderObjectMarkers(objectData)
		renderObjectList(objectData)
		renderIntelPane(intelData, objectData)
		renderAnalysisPane(analysisData)

		setBackendStatus(true)
		document.getElementById("map-hud3").textContent =
			"LAST SYNC: " + new Date().toLocaleTimeString()
	} catch (err) {
		setBackendStatus(false)
		console.error("Sync failed:", err)
	}
}

// =====================================================================
// DRONE IMAGE OVERLAYS
// Each drone image from the backend is overlaid on the map at its coords
// =====================================================================
function renderDroneOverlays(drones) {
	layers.drones.clearLayers()

	drones.forEach(d => {
		// Drone image overlay
		const overlay = L.imageOverlay(
			d.image_url.startsWith("http")
				? d.image_url
				: `${BASE_URL}${d.image_url}`,
			d.bounds, // [[minLat, minLng], [maxLat, maxLng]]
			{ opacity: d.opacity ?? 0.8, interactive: true },
		)

		// Marker at center of drone image
		const center = [
			(d.bounds[0][0] + d.bounds[1][0]) / 2,
			(d.bounds[0][1] + d.bounds[1][1]) / 2,
		]
		const marker = L.marker(center, { icon: droneIcon() }).bindPopup(`
        <div>
          <span style="color:#fbbf24">${d.name ?? d.id}</span><br>
          <span style="color:#4b7a4b">Objects: </span>${d.object_count ?? "—"}<br>
          <span style="color:#4b7a4b">Status: </span>${d.status ?? "—"}
        </div>
      `)	

		layers.drones.addLayer(overlay)
		layers.drones.addLayer(marker)
	})
}

// =====================================================================
// OBJECT MARKERS — enemies and POIs
// =====================================================================
function renderObjectMarkers(objects) {
	layers.enemies.clearLayers()
	layers.pois.clearLayers()

	objects.forEach(obj => {
		const isEnemy = obj.category === "enemy"
		const icon = isEnemy ? enemyIcon(obj.threat) : poiIcon()
		const layer = isEnemy ? layers.enemies : layers.pois

		L.marker([obj.lat, obj.lng], { icon })
			.bindPopup(
				`
        <div>
          <span style="color:${isEnemy ? "#f87171" : "#fbbf24"}">${isEnemy ? "ENEMY OBJECT" : "POINT OF INTEREST"}</span><br>
          ${obj.name}<br>
          <span style="color:#4b7a4b">Type: </span>${obj.type}<br>
          ${isEnemy ? `<span style="color:#4b7a4b">Threat: </span><span style="color:#f87171">${obj.threat}</span>` : ""}
        </div>
      `,
			)
			.addTo(layer)
	})
}

// =====================================================================
// OBJECT LIST (left panel)
// =====================================================================
function renderObjectList(objects) {
	const el = document.getElementById("object-list")
	if (!objects.length) {
		el.innerHTML = '<div class="empty-msg">NO OBJECTS DETECTED</div>'
		return
	}
	el.innerHTML = objects
		.map(
			obj => `
    <div class="object-item" onclick="map.setView([${obj.lat},${obj.lng}], 12)">
      <div class="obj-icon" style="background:${obj.category === "enemy" ? "#f87171" : "#fbbf24"};transform:rotate(${obj.category === "enemy" ? "45" : "0"}deg);border-radius:${obj.category === "poi" ? "50%" : "1px"}"></div>
      <div class="obj-name">${obj.name}</div>
      <div class="obj-threat ${obj.threat ?? ""}">${obj.threat ?? obj.category.toUpperCase()}</div>
    </div>
  `,
		)
		.join("")
}

// =====================================================================
// INTEL PANE
// =====================================================================
function renderIntelPane(intel, objects) {
	const enemies = objects.filter(o => o.category === "enemy")
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
      ${
				enemies.length === 0
					? '<div class="empty-msg">NO TARGETS IN THIS AO</div>'
					: enemies
							.map(
								t => `
            <div class="target-item" onclick="map.setView([${t.lat},${t.lng}], 12)">
              <div class="ttype ${t.type ?? "log"}">${(t.type ?? "UNK").toUpperCase()}</div>
              <div class="tname">${t.name}</div>
              <div class="tthreat ${t.threat}">${t.threat}</div>
            </div>
          `,
							)
							.join("")
			}
    </div>
    <div class="dcard">
      <div class="dcard-title">Enemy Assessment</div>
      ${Object.entries(intel.enemy_assessment ?? {})
				.map(
					([k, v]) => `
        <div class="drow">
          <span class="dlabel">${k}</span>
          <span class="dval ${v === "EXPOSED" || v === "ACTIVE" ? "bad" : v === "LIMITED" ? "warn" : ""}">${v}</span>
        </div>
      `,
				)
				.join("")}
    </div>
  `
}

// =====================================================================
// ANALYSIS PANE
// =====================================================================
function renderAnalysisPane(a) {
	const scores = [
		{ label: "Strike viability", val: a.strike },
		{ label: "Visibility / ISR", val: a.visibility },
		{ label: "Accessibility", val: a.accessibility },
		{ label: "Intel confidence", val: a.intel },
	]
	document.getElementById("pane-analysis").innerHTML = `
    <div class="dcard">
      <div class="dcard-title">Strike Assessment</div>
      ${scores
				.map(s => {
					const color =
						s.val > 65 ? "#4ade80" : s.val > 40 ? "#fbbf24" : "#f87171"
					return `
          <div class="score-row">
            <div class="score-hdr"><span>${s.label}</span><span style="color:${color}">${s.val}%</span></div>
            <div class="score-trk"><div class="score-fill" style="width:${s.val}%;background:${color}"></div></div>
          </div>
        `
				})
				.join("")}
    </div>
    <div class="dcard">
      <div class="dcard-title">AI Recommendation</div>
      <div class="rec ${a.recType}">${a.rec}</div>
    </div>
    <div class="dcard">
      <div class="dcard-title">Optimal Strike Window</div>
      <div class="drow"><span class="dlabel">Window</span><span class="dval ${a.recType === "go" ? "ok" : "warn"}">${a.recType === "go" ? "NOW" : "TBD"}</span></div>
      <div class="drow"><span class="dlabel">Confidence</span><span class="dval">${a.intel}%</span></div>
    </div>
  `
}

// =====================================================================
// WEATHER CARD UPDATER
// Your weather team calls this function with their data
// =====================================================================
async function fetchWeather(lat, lng) {
	try {
		const res = await fetch(`${BASE_URL}/api/weather?lat=${lat}&lng=${lng}`)
		if (!res.ok) throw new Error(res.status)
		const wData = await res.json()

		// The main backend returns the weather data directly
		const weather = wData || {};

		// Convert metric values and verify fly zones based on your analysis.py logic
		const windKmh = weather.wind_speed ? (weather.wind_speed * 3.6).toFixed(1) : 0;
		const visKm = weather.visibility ? (weather.visibility / 1000).toFixed(1) : 10;
		const isFlyable = (weather.wind_speed <= 10 && weather.visibility >= 2000);

		let precip = "None";
		if (weather.rain) precip = `${weather.rain}mm Rain`;
		else if (weather.snow) precip = `${weather.snow}mm Snow`;

		const formattedData = {
			temp: weather.t2m !== undefined ? Math.round(weather.t2m) : 0,
			cond: weather.rain ? "Rain" : (weather.snow ? "Snow" : "Clear"),
			fly: isFlyable,
			wind: windKmh,
			windDir: weather.wind_deg ? `${weather.wind_deg}°` : "N/A",
			vis: visKm,
			clouds: 0, // Could be hooked up to OpenWeather 'clouds' param if added in backend
			clouds: weather.clouds !== undefined ? weather.clouds : 0,
			precip: precip
		}

		updateWeatherCard(formattedData)
	} catch (err) {
		console.error("Failed to fetch weather:", err)
	}
}

function updateWeatherCard(data) {
	document.getElementById("w-temp").textContent =
		(data.temp > 0 ? "+" : "") + data.temp + "°C"
	document.getElementById("w-temp").style.color =
		data.temp < 0 ? "#93c5fd" : data.temp < 10 ? "#4ade80" : "#fbbf24"
	document.getElementById("w-cond").textContent = data.cond

	const flyBadge = document.getElementById("fly-badge")
	flyBadge.textContent = data.fly ? "DRONE OPS: GO" : "DRONE OPS: NO-GO"
	flyBadge.className = "fly-badge " + (data.fly ? "go" : "nogo")

	document.getElementById("w-wind-val").textContent =
		data.wind + " km/h " + data.windDir
	document.getElementById("w-wind-bar").style.width =
		Math.min((data.wind / 40) * 100, 100) + "%"
	document.getElementById("w-wind-bar").className =
		"bar-fill " + (data.wind > 25 ? "r" : data.wind > 15 ? "y" : "g")

	document.getElementById("w-vis-val").textContent = data.vis + " km"
	document.getElementById("w-vis-bar").style.width =
		Math.min((data.vis / 15) * 100, 100) + "%"
	document.getElementById("w-vis-bar").className =
		"bar-fill " + (data.vis < 6 ? "r" : data.vis < 10 ? "y" : "g")

	document.getElementById("w-cloud-val").textContent = data.clouds + "%"
	document.getElementById("w-cloud-bar").style.width = data.clouds + "%"
	document.getElementById("w-cloud-bar").className =
		"bar-fill " + (data.clouds > 70 ? "r" : data.clouds > 50 ? "y" : "g")

	document.getElementById("w-precip").textContent = data.precip
	document.getElementById("w-precip").className =
		"dval " + (data.precip === "None" ? "ok" : "warn")

	// Update GO/NO-GO badge in region list
	if (activeRegion) {
		const rb = document.getElementById("fly-rbadge-" + activeRegion)
		if (rb) {
			rb.textContent = data.fly ? "GO" : "NO-GO"
			rb.className = "rbadge " + (data.fly ? "go" : "nogo")
		}
	}
}

// =====================================================================
// REGION LIST
// =====================================================================
function renderRegionList() {
	document.getElementById("region-list").innerHTML = regions
		.map(
			r => `
    <div class="region-btn ${r.id === activeRegion ? "on" : ""}" data-id="${r.id}" onclick="selectRegion('${r.id}')">
      <div class="rdot" style="background:${r.color ?? "#4ade80"}"></div>
      <div class="rname">${r.name}</div>
      <div class="rbadge" id="fly-rbadge-${r.id}">—</div>
    </div>
  `,
		)
		.join("")
}

// =====================================================================
// LAYER TOGGLES
// =====================================================================
function toggleLayer(name, visible) {
	if (name === "satellite" && layers.satellite) {
		visible ? map.addLayer(layers.satellite) : map.removeLayer(layers.satellite)
	} else if (layers[name]) {
		visible ? map.addLayer(layers[name]) : map.removeLayer(layers[name])
	}
}

// =====================================================================
// ICONS
// =====================================================================
function enemyIcon(threat) {
	const color =
		threat === "HIGH" ? "#f87171" : threat === "MED" ? "#fbbf24" : "#4ade80"
	return L.divIcon({
		html: `<div style="width:12px;height:12px;background:${color};border:1px solid rgba(0,0,0,.5);border-radius:1px;transform:rotate(45deg)"></div>`,
		className: "",
		iconSize: [12, 12],
		iconAnchor: [6, 6],
	})
}

function poiIcon() {
	return L.divIcon({
		html: `<div style="width:10px;height:10px;background:#c084fc;border:1px solid #6b21a8;border-radius:50%"></div>`,
		className: "",
		iconSize: [10, 10],
		iconAnchor: [5, 5],
	})
}

function droneIcon() {
	return L.divIcon({
		html: `<div style="width:8px;height:8px;background:#fbbf24;border:1px solid #f59e0b;border-radius:50%"></div>`,
		className: "",
		iconSize: [8, 8],
		iconAnchor: [4, 4],
	})
}

// =====================================================================
// HELPERS
// =====================================================================
function showLoading(show) {
	document.getElementById("map-loading").style.display = show ? "flex" : "none"
}

function setBackendStatus(ok) {
	const badge = document.getElementById("backend-badge")
	const pulse = document.getElementById("sync-pulse")
	const txt = document.getElementById("sync-status")
	if (ok) {
		badge.textContent = "BACKEND: ONLINE"
		badge.className = "conn-badge"
		pulse.className = "pulse"
		txt.textContent = "SYNCED"
	} else {
		badge.textContent = "BACKEND: OFFLINE"
		badge.className = "conn-badge error"
		pulse.className = "pulse error"
		txt.textContent = "CONNECTION LOST"
	}
}

// =====================================================================
// TABS
// =====================================================================
function switchTab(tab, el) {
	document.querySelectorAll(".tab").forEach(t => t.classList.remove("on"))
	document.querySelectorAll(".pane").forEach(p => p.classList.remove("on"))
	el.classList.add("on")
	document.getElementById("pane-" + tab).classList.add("on")
}

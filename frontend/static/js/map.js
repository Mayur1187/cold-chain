document.addEventListener("DOMContentLoaded", () => {
    if (document.body.dataset.page !== "map") {
        return;
    }

    const { endpoints, fetchJSON, escapeHTML, formatTemp, statusClass, renderError } = window.ColdChainUI;
    const mapTarget = document.getElementById("map");
    const fallbackBanner = document.getElementById("map-fallback");
    const routeFeed = document.getElementById("route-feed");
    const hubList = document.getElementById("hub-list");

    let mapInstance = null;
    let vehicleLayer = null;
    let routeLayer = null;
    let hubLayer = null;
    let hasFitBounds = false;

    function showFallback(message) {
        if (!fallbackBanner) {
            return;
        }
        fallbackBanner.textContent = message;
        fallbackBanner.classList.remove("hidden");
    }

    function initMap(center) {
        if (typeof window.L === "undefined") {
            showFallback("Leaflet is unavailable. Rendering live route summaries instead.");
            return;
        }
        if (mapInstance) {
            return;
        }
        mapInstance = L.map(mapTarget, { zoomControl: false }).setView([center.latitude, center.longitude], 6);
        L.control.zoom({ position: "bottomright" }).addTo(mapInstance);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 18,
            attribution: "&copy; OpenStreetMap contributors",
        })
            .on("tileerror", () => {
                showFallback("Map tiles are unavailable right now. Route data is still live in the side panel.");
            })
            .addTo(mapInstance);
        vehicleLayer = L.layerGroup().addTo(mapInstance);
        routeLayer = L.layerGroup().addTo(mapInstance);
        hubLayer = L.layerGroup().addTo(mapInstance);
    }

    function markerColor(status) {
        if (status === "Critical") {
            return "#d35e43";
        }
        if (["Watch", "Mitigating", "Stabilized"].includes(status)) {
            return "#dd9a38";
        }
        return "#2a9d8f";
    }

    function renderSidebar(payload) {
        const reroutes = (payload.routes || []).filter((route) => route.rerouted);
        if (!reroutes.length) {
            routeFeed.innerHTML = `<div class="empty-state">No reroutes yet. Vehicles are holding their planned routes.</div>`;
        } else {
            routeFeed.innerHTML = reroutes.map((route) => {
                const vehicle = (payload.vehicles || []).find((item) => item.id === route.vehicle_id);
                return `
                    <div class="route-card">
                        <strong>${escapeHTML(vehicle?.name || `Vehicle ${route.vehicle_id}`)}</strong>
                        <div class="vehicle-meta">
                            <span class="status-pill ${statusClass(vehicle?.status || "Watch")}">${escapeHTML(vehicle?.status || "Watch")}</span>
                            <span>${escapeHTML(route.rerouted_to || "Cold hub")}</span>
                        </div>
                        <div class="muted">${escapeHTML(route.route_name)}</div>
                    </div>
                `;
            }).join("");
        }

        hubList.innerHTML = (payload.hubs || []).map((hub) => `
            <div class="hub-card">
                <strong>${escapeHTML(hub.name)}</strong>
                <div class="muted">${escapeHTML(hub.capacity_label)}</div>
                <div class="vehicle-meta">
                    <span>${Number(hub.latitude).toFixed(2)}, ${Number(hub.longitude).toFixed(2)}</span>
                </div>
            </div>
        `).join("");
    }

    function renderMap(payload) {
        if (!mapInstance || typeof window.L === "undefined") {
            return;
        }

        vehicleLayer.clearLayers();
        routeLayer.clearLayers();
        hubLayer.clearLayers();

        const bounds = [];

        (payload.hubs || []).forEach((hub) => {
            const latLng = [hub.latitude, hub.longitude];
            bounds.push(latLng);
            L.circleMarker(latLng, {
                radius: 7,
                color: "#15758b",
                weight: 2,
                fillColor: "#dff4f8",
                fillOpacity: 1,
            })
                .bindPopup(`<strong>${escapeHTML(hub.name)}</strong><br>${escapeHTML(hub.capacity_label)}`)
                .addTo(hubLayer);
        });

        (payload.routes || []).forEach((route) => {
            const points = (route.points || []).map((point) => [point.latitude, point.longitude]);
            if (points.length) {
                points.forEach((point) => bounds.push(point));
                L.polyline(points, {
                    color: route.color || "#1f8ea3",
                    weight: route.rerouted ? 5 : 4,
                    opacity: route.rerouted ? 0.95 : 0.7,
                    dashArray: route.rerouted ? "12 8" : null,
                }).addTo(routeLayer);
            }
        });

        (payload.vehicles || []).forEach((vehicle) => {
            const latLng = [vehicle.latitude, vehicle.longitude];
            bounds.push(latLng);
            L.circleMarker(latLng, {
                radius: 8,
                color: "#ffffff",
                weight: 2,
                fillColor: markerColor(vehicle.status),
                fillOpacity: 0.95,
            })
                .bindPopup(`
                    <strong>${escapeHTML(vehicle.name)}</strong><br>
                    ${escapeHTML(vehicle.route_name)}<br>
                    ${escapeHTML(vehicle.status)} | ${escapeHTML(formatTemp(vehicle.temperature))}<br>
                    ETA ${escapeHTML(vehicle.eta_minutes)} min
                `)
                .addTo(vehicleLayer);
        });

        if (!hasFitBounds && bounds.length) {
            mapInstance.fitBounds(bounds, { padding: [30, 30] });
            hasFitBounds = true;
        }
    }

    async function refreshMap() {
        try {
            const payload = await fetchJSON(endpoints.map);
            initMap(payload.center);
            renderSidebar(payload);
            renderMap(payload);
        } catch (error) {
            showFallback("Map data is temporarily unavailable. Trying again automatically.");
            renderError(routeFeed, "Route action feed could not be loaded.");
            renderError(hubList, "Cold storage hub data could not be loaded.");
        }
    }

    refreshMap();
    window.setInterval(refreshMap, 6000);
});

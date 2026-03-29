document.addEventListener("DOMContentLoaded", () => {
    if (document.body.dataset.page !== "fleet") {
        return;
    }

    const { endpoints, fetchJSON, escapeHTML, formatTemp, formatTimestamp, statusClass, renderError, renderEmpty } = window.ColdChainUI;
    const tableBody = document.getElementById("fleet-table-body");
    const priorityQueue = document.getElementById("priority-queue");
    const fleetTotal = document.getElementById("fleet-total");
    const fleetCritical = document.getElementById("fleet-critical");
    const fleetWatch = document.getElementById("fleet-watch");

    function renderVehicles(payload) {
        const vehicles = payload.vehicles || [];
        if (fleetTotal) {
            fleetTotal.textContent = payload.summary?.total ?? vehicles.length;
        }
        if (fleetCritical) {
            fleetCritical.textContent = payload.summary?.critical ?? 0;
        }
        if (fleetWatch) {
            fleetWatch.textContent = payload.summary?.watchlist ?? 0;
        }

        if (!vehicles.length) {
            tableBody.innerHTML = `<tr><td colspan="6"><div class="empty-state">No vehicles are available.</div></td></tr>`;
            renderEmpty(priorityQueue, "No priority queue available.");
            return;
        }

        tableBody.innerHTML = vehicles.map((vehicle) => `
            <tr>
                <td>
                    <div class="table-title">${escapeHTML(vehicle.name)}</div>
                    <div class="table-subtle">${escapeHTML(vehicle.destination)}</div>
                </td>
                <td><span class="status-pill ${statusClass(vehicle.status)}">${escapeHTML(vehicle.status)}</span></td>
                <td>
                    <div class="table-title">${formatTemp(vehicle.temperature)}</div>
                    <div class="table-subtle">${vehicle.cooling_active ? "Cooling active" : "Cooling idle"}</div>
                </td>
                <td>
                    <div class="risk-line">
                        <div class="vehicle-meta">
                            <span>${escapeHTML(vehicle.risk_score)}</span>
                            <span>${escapeHTML(vehicle.risk_band)}</span>
                        </div>
                        <div class="risk-bar"><span style="width:${Math.min(vehicle.risk_score, 100)}%"></span></div>
                    </div>
                </td>
                <td>
                    <div class="table-title">${escapeHTML(vehicle.eta_minutes)} min</div>
                    <div class="table-subtle">${escapeHTML(vehicle.progress)}% progress</div>
                </td>
                <td>
                    <div class="table-title">${escapeHTML(vehicle.route_name)}</div>
                    <div class="table-subtle">${vehicle.rerouted ? `Rerouted to ${escapeHTML(vehicle.rerouted_to || vehicle.destination)}` : `Last seen ${escapeHTML(formatTimestamp(vehicle.last_seen))}`}</div>
                </td>
            </tr>
        `).join("");

        priorityQueue.innerHTML = vehicles.slice(0, 4).map((vehicle, index) => `
            <div class="priority-card">
                <header>
                    <strong>#${index + 1} ${escapeHTML(vehicle.name)}</strong>
                    <span class="status-pill ${statusClass(vehicle.status)}">${escapeHTML(vehicle.status)}</span>
                </header>
                <div class="vehicle-meta">
                    <span>Risk ${escapeHTML(vehicle.risk_score)}</span>
                    <span>${formatTemp(vehicle.temperature)}</span>
                </div>
                <div class="muted">${vehicle.rerouted ? `Autonomous reroute in progress to ${escapeHTML(vehicle.rerouted_to || vehicle.destination)}.` : `Monitoring route ${escapeHTML(vehicle.route_name)}.`}</div>
            </div>
        `).join("");
    }

    async function refreshVehicles() {
        try {
            const payload = await fetchJSON(endpoints.vehicles);
            renderVehicles(payload);
        } catch (error) {
            if (tableBody) {
                tableBody.innerHTML = `<tr><td colspan="6"><div class="error-state">Fleet telemetry is temporarily unavailable.</div></td></tr>`;
            }
            renderError(priorityQueue, "Risk ranking could not be loaded.");
        }
    }

    refreshVehicles();
    window.setInterval(refreshVehicles, 6000);
});

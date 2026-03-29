(function () {
    const endpoints = {
        summary: "/system-summary",
        vehicles: "/vehicles",
        logs: "/logs",
        map: "/map-data",
    };

    function activateNavigation() {
        const page = document.body.dataset.page;
        document.querySelectorAll("[data-nav]").forEach((link) => {
            if (link.dataset.nav === page) {
                link.classList.add("active");
            }
        });
    }

    async function fetchJSON(url) {
        const response = await fetch(url, {
            headers: { "Accept": "application/json" },
        });
        if (!response.ok) {
            throw new Error("Request failed");
        }
        return response.json();
    }

    function escapeHTML(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    function formatTemp(value) {
        if (value === null || value === undefined || Number.isNaN(Number(value))) {
            return "No reading";
        }
        return `${Number(value).toFixed(1)} C`;
    }

    function formatTimestamp(value) {
        if (!value) {
            return "Pending";
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return value;
        }
        return date.toLocaleString([], {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
        });
    }

    function statusClass(status) {
        if (status === "Critical") {
            return "critical";
        }
        if (["Watch", "Mitigating", "Stabilized"].includes(status)) {
            return "warning";
        }
        if (status === "Nominal") {
            return "good";
        }
        return "neutral";
    }

    function renderError(target, message) {
        if (!target) {
            return;
        }
        target.innerHTML = `<div class="error-state">${escapeHTML(message)}</div>`;
    }

    function renderEmpty(target, message) {
        if (!target) {
            return;
        }
        target.innerHTML = `<div class="empty-state">${escapeHTML(message)}</div>`;
    }

    function renderDashboard(summary, vehicles, logs) {
        const chip = document.getElementById("system-health-chip");
        const summaryText = document.getElementById("system-health-summary");
        const totalVehicles = document.getElementById("metric-total-vehicles");
        const activeAlerts = document.getElementById("metric-active-alerts");
        const anomalies = document.getElementById("metric-anomalies");
        const averageTemp = document.getElementById("metric-average-temp");
        const criticalVehicle = document.getElementById("critical-vehicle");
        const vehicleOverview = document.getElementById("vehicle-overview");
        const activeAlertsList = document.getElementById("active-alerts");

        if (chip) {
            chip.className = `status-pill ${summary.health.tone === "good" ? "good" : summary.health.tone}`;
            chip.textContent = summary.health.label;
        }
        if (summaryText) {
            summaryText.textContent = summary.health.summary;
        }
        if (totalVehicles) {
            totalVehicles.textContent = summary.metrics.total_vehicles ?? vehicles.length;
        }
        if (activeAlerts) {
            activeAlerts.textContent = summary.metrics.active_alerts ?? 0;
        }
        if (anomalies) {
            anomalies.textContent = summary.metrics.anomalies_detected ?? logs.length;
        }
        if (averageTemp) {
            averageTemp.textContent = `${Number(summary.metrics.average_temperature || 0).toFixed(1)} C avg`;
        }

        if (!summary.critical_vehicle) {
            renderEmpty(criticalVehicle, "No high-risk vehicle is currently above the escalation threshold.");
        } else if (criticalVehicle) {
            const vehicle = summary.critical_vehicle;
            criticalVehicle.innerHTML = `
                <div class="priority-card">
                    <header>
                        <div>
                            <strong>${escapeHTML(vehicle.name)}</strong>
                            <div class="table-subtle">${escapeHTML(vehicle.route_name)}</div>
                        </div>
                        <span class="status-pill ${statusClass(vehicle.status)}">${escapeHTML(vehicle.status)}</span>
                    </header>
                    <div class="vehicle-meta">
                        <span>${formatTemp(vehicle.temperature)}</span>
                        <span>ETA ${escapeHTML(vehicle.eta_minutes)} min</span>
                        <span>Destination ${escapeHTML(vehicle.destination)}</span>
                    </div>
                    <div class="risk-line">
                        <div class="vehicle-meta">
                            <span>Risk score ${escapeHTML(vehicle.risk_score)}</span>
                            <span>${escapeHTML(vehicle.risk_band)}</span>
                            <span>${vehicle.cooling_active ? "Cooling active" : "Cooling idle"}</span>
                        </div>
                        <div class="risk-bar"><span style="width:${Math.min(vehicle.risk_score, 100)}%"></span></div>
                    </div>
                </div>
            `;
        }

        if (!vehicles.length) {
            renderEmpty(vehicleOverview, "No vehicles are registered in the fleet.");
        } else if (vehicleOverview) {
            vehicleOverview.innerHTML = vehicles.slice(0, 4).map((vehicle) => `
                <div class="vehicle-card">
                    <header>
                        <strong>${escapeHTML(vehicle.name)}</strong>
                        <span class="status-pill ${statusClass(vehicle.status)}">${escapeHTML(vehicle.status)}</span>
                    </header>
                    <div class="vehicle-meta">
                        <span>${formatTemp(vehicle.temperature)}</span>
                        <span>${escapeHTML(vehicle.destination)}</span>
                        <span>${escapeHTML(vehicle.progress)}% route progress</span>
                    </div>
                </div>
            `).join("");
        }

        const alertsToRender = logs.filter((item) => item.severity !== "info").slice(0, 5);
        if (!alertsToRender.length) {
            renderEmpty(activeAlertsList, "No active alerts. The platform is monitoring normally.");
        } else if (activeAlertsList) {
            activeAlertsList.innerHTML = alertsToRender.map((log) => `
                <article class="alert-card">
                    <header>
                        <strong>${escapeHTML(log.vehicle_name)}</strong>
                        <span class="status-pill ${log.severity === "critical" ? "critical" : "warning"}">${escapeHTML(log.anomaly_type.replaceAll("_", " "))}</span>
                    </header>
                    <div class="alert-meta">
                        <span>${formatTimestamp(log.timestamp)}</span>
                        <span>${formatTemp(log.temperature)}</span>
                    </div>
                    <div><strong>${escapeHTML(log.action_taken)}</strong></div>
                    <div class="muted">${escapeHTML(log.reason)}</div>
                </article>
            `).join("");
        }
    }

    async function refreshDashboard() {
        try {
            const [summary, vehiclesData, logsData] = await Promise.all([
                fetchJSON(endpoints.summary),
                fetchJSON(endpoints.vehicles),
                fetchJSON(`${endpoints.logs}?limit=8`),
            ]);
            renderDashboard(summary, vehiclesData.vehicles || [], logsData.logs || []);
        } catch (error) {
            renderError(document.getElementById("critical-vehicle"), "Dashboard data is temporarily unavailable.");
            renderError(document.getElementById("vehicle-overview"), "Fleet snapshot could not be loaded.");
            renderError(document.getElementById("active-alerts"), "Alert feed could not be loaded.");
        }
    }

    function renderLogs(logs) {
        const summaryTarget = document.getElementById("logs-summary");
        const tableTarget = document.getElementById("logs-table-body");
        if (!tableTarget) {
            return;
        }

        const criticalCount = logs.filter((item) => item.severity === "critical").length;
        const warningCount = logs.filter((item) => item.severity === "warning").length;

        if (summaryTarget) {
            summaryTarget.innerHTML = `
                <span class="status-pill ${criticalCount ? "critical" : warningCount ? "warning" : "good"}">
                    ${criticalCount ? "Critical actions present" : warningCount ? "Warnings active" : "Stable log stream"}
                </span>
                <p class="muted">${logs.length} recent event(s), ${criticalCount} critical, ${warningCount} warning.</p>
            `;
        }

        if (!logs.length) {
            tableTarget.innerHTML = `<tr><td colspan="5"><div class="empty-state">No events have been logged yet.</div></td></tr>`;
            return;
        }

        tableTarget.innerHTML = logs.map((log) => `
            <tr>
                <td>${escapeHTML(formatTimestamp(log.timestamp))}</td>
                <td>
                    <div class="table-title">${escapeHTML(log.vehicle_name)}</div>
                    <div class="table-subtle">${formatTemp(log.temperature)}</div>
                </td>
                <td><span class="status-pill ${log.severity === "critical" ? "critical" : log.severity === "warning" ? "warning" : "neutral"}">${escapeHTML(log.anomaly_type.replaceAll("_", " "))}</span></td>
                <td>${escapeHTML(log.action_taken)}</td>
                <td class="muted">${escapeHTML(log.reason)}</td>
            </tr>
        `).join("");
    }

    async function refreshLogs() {
        try {
            const logsData = await fetchJSON(`${endpoints.logs}?limit=40`);
            renderLogs(logsData.logs || []);
        } catch (error) {
            renderError(document.getElementById("logs-summary"), "The event feed could not be loaded.");
            const tableTarget = document.getElementById("logs-table-body");
            if (tableTarget) {
                tableTarget.innerHTML = `<tr><td colspan="5"><div class="error-state">The event history is temporarily unavailable.</div></td></tr>`;
            }
        }
    }

    function initPage() {
        activateNavigation();
        const page = document.body.dataset.page;
        if (page === "dashboard") {
            refreshDashboard();
            window.setInterval(refreshDashboard, 5000);
        }
        if (page === "logs") {
            refreshLogs();
            window.setInterval(refreshLogs, 6000);
        }
    }

    document.addEventListener("DOMContentLoaded", initPage);

    window.ColdChainUI = {
        endpoints,
        fetchJSON,
        escapeHTML,
        formatTemp,
        formatTimestamp,
        statusClass,
        renderError,
        renderEmpty,
    };
})();

from flask import Blueprint, jsonify, render_template, request

from config import APP_NAME, COLD_STORAGE_HUBS, LEAFLET_FALLBACK_CENTER, MAX_LOG_ROWS
from database import fetch_all, fetch_one
from utils import risk_band, safe_json_loads


web = Blueprint("web", __name__)


def register_routes(app):
    app.register_blueprint(web)


@web.route("/")
def dashboard():
    return render_template("index.html", app_name=APP_NAME, page_key="dashboard", title="Control Tower")


@web.route("/fleet")
def fleet_page():
    return render_template("vehicles.html", app_name=APP_NAME, page_key="fleet", title="Fleet")


@web.route("/map")
def map_page():
    return render_template("map.html", app_name=APP_NAME, page_key="map", title="Map")


@web.route("/events")
def logs_page():
    return render_template("logs.html", app_name=APP_NAME, page_key="logs", title="Event Log")


@web.route("/system-summary")
def system_summary_api():
    vehicles = _vehicle_payload()
    active_alerts = [vehicle for vehicle in vehicles if vehicle["status"] != "Nominal"][:5]
    critical_vehicle = max(vehicles, key=lambda item: item["risk_score"], default=None)
    latest_metrics = fetch_one(
        """
        SELECT *
        FROM system_metrics
        ORDER BY id DESC
        LIMIT 1
        """
    ) or {
        "total_vehicles": 0,
        "anomalies_detected": 0,
        "active_alerts": 0,
        "average_temperature": 0,
    }
    recent_logs = _log_payload(limit=6)
    return jsonify(
        {
            "app_name": APP_NAME,
            "health": _health_status(vehicles),
            "metrics": latest_metrics,
            "critical_vehicle": critical_vehicle,
            "active_alerts": active_alerts,
            "recent_logs": recent_logs,
        }
    )


@web.route("/vehicles")
def vehicles_api():
    vehicles = _vehicle_payload()
    return jsonify(
        {
            "vehicles": vehicles,
            "summary": {
                "total": len(vehicles),
                "critical": sum(1 for item in vehicles if item["status"] == "Critical"),
                "watchlist": sum(1 for item in vehicles if item["status"] in {"Watch", "Mitigating", "Stabilized"}),
            },
        }
    )


@web.route("/logs")
def logs_api():
    requested_limit = request.args.get("limit", default=30, type=int)
    limit = max(1, min(requested_limit or 30, MAX_LOG_ROWS))
    return jsonify({"logs": _log_payload(limit=limit)})


@web.route("/map-data")
def map_data_api():
    vehicles = _vehicle_payload()
    route_rows = fetch_all("SELECT vehicle_id, route_data FROM routes ORDER BY vehicle_id")
    routes = []
    for row in route_rows:
        route_data = safe_json_loads(row["route_data"], {})
        routes.append(
            {
                "vehicle_id": row["vehicle_id"],
                "route_name": route_data.get("route_name", "Active route"),
                "points": route_data.get("points", []),
                "color": route_data.get("color", "#1f8ea3"),
                "rerouted": route_data.get("rerouted", False),
                "rerouted_to": route_data.get("rerouted_to"),
            }
        )
    return jsonify(
        {
            "center": LEAFLET_FALLBACK_CENTER,
            "vehicles": vehicles,
            "routes": routes,
            "hubs": COLD_STORAGE_HUBS,
        }
    )


def _vehicle_payload():
    rows = fetch_all(
        """
        SELECT v.*, r.route_data
        FROM vehicles v
        JOIN routes r ON r.vehicle_id = v.id
        ORDER BY v.risk_score DESC, v.id ASC
        """
    )
    vehicles = []
    for row in rows:
        route_data = safe_json_loads(row["route_data"], {})
        vehicles.append(
            {
                "id": row["id"],
                "name": row["name"],
                "temperature": row["temperature"],
                "status": row["status"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "destination": row["destination"],
                "eta_minutes": row["eta_minutes"],
                "risk_score": row["risk_score"],
                "risk_band": risk_band(row["risk_score"]),
                "cooling_active": bool(row["cooling_active"]),
                "last_seen": row["last_seen"],
                "speed_kmh": row["speed_kmh"],
                "route_name": route_data.get("route_name", "Active route"),
                "route_color": route_data.get("color", "#1f8ea3"),
                "rerouted": route_data.get("rerouted", False),
                "rerouted_to": route_data.get("rerouted_to"),
                "progress": round(route_data.get("progress", 0.0) * 100, 1),
            }
        )
    return vehicles


def _log_payload(limit=30):
    rows = fetch_all(
        """
        SELECT l.*, v.name AS vehicle_name
        FROM logs l
        LEFT JOIN vehicles v ON v.id = l.vehicle_id
        ORDER BY l.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    payload = []
    for row in rows:
        payload.append(
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "vehicle_id": row["vehicle_id"],
                "vehicle_name": row["vehicle_name"] or "System",
                "temperature": row["temperature"],
                "anomaly_type": row["anomaly_type"] or "system_update",
                "action_taken": row["action_taken"],
                "reason": row["reason"],
                "severity": row["severity"],
            }
        )
    return payload


def _health_status(vehicles):
    critical_count = sum(1 for vehicle in vehicles if vehicle["status"] == "Critical")
    warning_count = sum(1 for vehicle in vehicles if vehicle["status"] in {"Watch", "Mitigating", "Stabilized"})

    if critical_count:
        return {
            "label": "Intervention Active",
            "tone": "critical",
            "summary": f"{critical_count} vehicle(s) are in critical mitigation mode.",
        }
    if warning_count:
        return {
            "label": "Attention Required",
            "tone": "warning",
            "summary": f"{warning_count} vehicle(s) are being watched or actively stabilized.",
        }
    return {
        "label": "Fleet Healthy",
        "tone": "good",
        "summary": "All monitored shipments are operating inside the validated temperature band.",
    }

import json

from config import (
    COLD_STORAGE_HUBS,
    COOLING_RECOVERY_STEP_C,
    ROUTE_ALERT_COLOR,
    ROUTE_STABLE_COLOR,
    ROUTE_WARNING_COLOR,
    SAFE_TEMP_MAX_C,
)
from database import DATABASE_LOCK, fetch_all, get_connection
from utils import build_reroute_points, clamp, nearest_hub, safe_json_loads, utc_now_iso


class RouteOptimizationAgent:
    def reroute_vehicle(self, connection, vehicle):
        route_row = connection.execute(
            "SELECT route_data FROM routes WHERE vehicle_id = ?",
            (vehicle["id"],),
        ).fetchone()
        route_data = safe_json_loads(route_row["route_data"] if route_row else None, {})
        current_point = {"latitude": vehicle["latitude"], "longitude": vehicle["longitude"]}
        target_hub = nearest_hub(current_point, COLD_STORAGE_HUBS)

        route_data["points"] = build_reroute_points(current_point, target_hub)
        route_data["progress"] = 0.0
        route_data["rerouted"] = True
        route_data["rerouted_to"] = target_hub["name"]
        route_data["color"] = ROUTE_ALERT_COLOR
        route_data["route_name"] = f"Priority diversion to {target_hub['name']}"
        route_data["eta_base_minutes"] = max(18, int(route_data.get("eta_base_minutes", 60) * 0.6))

        connection.execute(
            "UPDATE routes SET route_data = ? WHERE vehicle_id = ?",
            (json.dumps(route_data), vehicle["id"]),
        )
        return target_hub


class ActionAgent:
    def __init__(self):
        self.route_optimizer = RouteOptimizationAgent()

    def execute_pending_decisions(self):
        pending_decisions = fetch_all(
            """
            SELECT *
            FROM agent_decisions
            WHERE executed = 0
            ORDER BY id ASC
            """
        )
        for decision in pending_decisions:
            with DATABASE_LOCK:
                with get_connection() as connection:
                    vehicle = connection.execute(
                        "SELECT * FROM vehicles WHERE id = ?",
                        (decision["vehicle_id"],),
                    ).fetchone()
                    if not vehicle:
                        continue
                    vehicle = dict(vehicle)

                    updated_temp = vehicle["temperature"]
                    updated_destination = vehicle["destination"]
                    updated_eta = vehicle["eta_minutes"]
                    route_color = ROUTE_WARNING_COLOR

                    if decision["cooling_command"]:
                        updated_temp = round(
                            clamp(
                                (updated_temp or SAFE_TEMP_MAX_C) - COOLING_RECOVERY_STEP_C * 0.45,
                                1.5,
                                14.0,
                            ),
                            2,
                        )

                    if decision["reroute_command"]:
                        reroute_target = self.route_optimizer.reroute_vehicle(connection, vehicle)
                        updated_destination = reroute_target["name"]
                        updated_eta = max(16, int(updated_eta * 0.65))
                        route_color = ROUTE_ALERT_COLOR
                    elif decision["target_status"] == "Watch":
                        route_color = ROUTE_WARNING_COLOR
                    else:
                        route_color = ROUTE_STABLE_COLOR

                    self._apply_route_color(connection, vehicle["id"], route_color)
                    connection.execute(
                        """
                        UPDATE vehicles
                        SET temperature = ?, status = ?, destination = ?, eta_minutes = ?,
                            risk_score = ?, cooling_active = ?, last_seen = ?
                        WHERE id = ?
                        """,
                        (
                            updated_temp,
                            decision["target_status"],
                            updated_destination,
                            updated_eta,
                            decision["risk_score"],
                            decision["cooling_command"],
                            utc_now_iso(),
                            vehicle["id"],
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO logs (
                            timestamp, vehicle_id, temperature, anomaly_type,
                            action_taken, reason, severity
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            utc_now_iso(),
                            vehicle["id"],
                            updated_temp,
                            decision["anomaly_type"],
                            decision["recommended_action"],
                            decision["reason"],
                            self._severity_from_status(decision["target_status"]),
                        ),
                    )
                    connection.execute(
                        "UPDATE agent_decisions SET executed = 1 WHERE id = ?",
                        (decision["id"],),
                    )
                    connection.commit()

    def _apply_route_color(self, connection, vehicle_id, color):
        route_row = connection.execute(
            "SELECT route_data FROM routes WHERE vehicle_id = ?",
            (vehicle_id,),
        ).fetchone()
        if not route_row:
            return
        route_data = safe_json_loads(route_row["route_data"], {})
        route_data["color"] = color
        connection.execute(
            "UPDATE routes SET route_data = ? WHERE vehicle_id = ?",
            (json.dumps(route_data), vehicle_id),
        )

    def _severity_from_status(self, status):
        if status == "Critical":
            return "critical"
        if status in {"Mitigating", "Watch"}:
            return "warning"
        return "info"

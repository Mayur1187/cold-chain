import json
import math
import threading
import time

from actions import ActionAgent
from config import (
    COOLING_RECOVERY_STEP_C,
    MISSING_DATA_INTERVAL,
    ROUTE_NORMAL_COLOR,
    ROUTE_STABLE_COLOR,
    SAFE_TEMP_MAX_C,
    SIMULATION_INTERVAL_SECONDS,
)
from database import DATABASE_LOCK, fetch_all, get_connection
from decision_engine import DecisionAgent
from detection import DetectionAgent
from utils import clamp, interpolate_polyline, rolling_average, safe_json_loads, utc_now_iso


class MonitoringAgent:
    def collect_cycle(self, cycle_number):
        fleet_rows = fetch_all(
            """
            SELECT v.*, r.route_data
            FROM vehicles v
            JOIN routes r ON r.vehicle_id = v.id
            ORDER BY v.id
            """
        )
        for row in fleet_rows:
            self._update_vehicle_state(row, cycle_number)

    def _update_vehicle_state(self, vehicle_row, cycle_number):
        route_data = safe_json_loads(vehicle_row["route_data"], {})
        recent_history = fetch_all(
            """
            SELECT temperature
            FROM sensor_history
            WHERE vehicle_id = ?
            ORDER BY id DESC
            LIMIT 5
            """,
            (vehicle_row["id"],),
        )
        previous_temp = vehicle_row["temperature"] if vehicle_row["temperature"] is not None else 4.5
        next_progress = clamp(
            route_data.get("progress", 0.0) + route_data.get("movement_step", 0.02),
            0.0,
            1.0,
        )
        route_data["progress"] = 0.02 if next_progress >= 1.0 else next_progress
        next_point = interpolate_polyline(route_data.get("points", []), route_data["progress"])

        missing_packet = cycle_number > 8 and (cycle_number + vehicle_row["id"]) % MISSING_DATA_INTERVAL == 0
        sampled_temperature = None if missing_packet else self._simulate_temperature(
            vehicle_row,
            route_data,
            recent_history,
            cycle_number,
            previous_temp,
        )

        if sampled_temperature is None:
            display_temperature = vehicle_row["temperature"]
        else:
            display_temperature = round(sampled_temperature, 2)

        next_eta = max(8, int(route_data.get("eta_base_minutes", 70) * (1 - route_data["progress"])))
        next_status = self._stabilize_status(vehicle_row, recent_history, display_temperature)
        next_risk = self._decay_risk(vehicle_row, display_temperature)
        next_cooling = 0 if next_status == "Nominal" else vehicle_row["cooling_active"]
        route_color = route_data.get("color", ROUTE_NORMAL_COLOR)
        if next_status == "Nominal" and not route_data.get("rerouted"):
            route_color = ROUTE_NORMAL_COLOR
        elif next_status == "Stabilized":
            route_color = ROUTE_STABLE_COLOR
        route_data["color"] = route_color

        with DATABASE_LOCK:
            with get_connection() as connection:
                connection.execute(
                    """
                    UPDATE vehicles
                    SET temperature = ?, latitude = ?, longitude = ?, eta_minutes = ?,
                        status = ?, risk_score = ?, cooling_active = ?, last_seen = ?
                    WHERE id = ?
                    """,
                    (
                        display_temperature,
                        next_point["latitude"],
                        next_point["longitude"],
                        next_eta,
                        next_status,
                        next_risk,
                        next_cooling,
                        utc_now_iso(),
                        vehicle_row["id"],
                    ),
                )
                connection.execute(
                    "UPDATE routes SET route_data = ? WHERE vehicle_id = ?",
                    (json.dumps(route_data), vehicle_row["id"]),
                )
                connection.execute(
                    """
                    INSERT INTO sensor_history (
                        timestamp, vehicle_id, temperature, latitude, longitude, status, missing
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        utc_now_iso(),
                        vehicle_row["id"],
                        sampled_temperature,
                        next_point["latitude"],
                        next_point["longitude"],
                        next_status,
                        1 if missing_packet else 0,
                    ),
                )
                connection.commit()

    def _simulate_temperature(self, vehicle_row, route_data, recent_history, cycle_number, previous_temp):
        pattern = route_data.get("simulation_pattern", "steady")
        recent_temperatures = [row["temperature"] for row in recent_history if row["temperature"] is not None]
        baseline = rolling_average(recent_temperatures) or previous_temp
        oscillation = math.sin((cycle_number + vehicle_row["id"]) / 2.6) * 0.17
        drift = 0.0

        if pattern == "gradual_rise":
            if cycle_number >= 5:
                drift += 0.55
            if cycle_number >= 8:
                drift += 0.22
        elif pattern == "spike":
            if cycle_number == 7:
                drift += 2.3
            elif cycle_number == 8:
                drift += 0.9
            elif cycle_number > 8:
                drift -= 0.28
        elif pattern == "oscillating":
            drift += math.sin(cycle_number / 1.4) * 0.24
        else:
            drift += math.sin(cycle_number / 3.1) * 0.08

        cooling_offset = COOLING_RECOVERY_STEP_C if vehicle_row["cooling_active"] else 0.0
        risk_heat = max(0, (vehicle_row["risk_score"] - 55) / 100)
        next_temp = previous_temp + oscillation + drift + risk_heat * 0.14 - cooling_offset
        if vehicle_row["cooling_active"] and baseline <= SAFE_TEMP_MAX_C - 1.0:
            next_temp -= 0.2
        return round(clamp(next_temp, 1.4, 14.8), 2)

    def _stabilize_status(self, vehicle_row, recent_history, display_temperature):
        recent_temperatures = [row["temperature"] for row in recent_history if row["temperature"] is not None]
        recent_average = rolling_average(recent_temperatures[:3]) if recent_temperatures else None
        if vehicle_row["cooling_active"] and display_temperature is not None and display_temperature <= SAFE_TEMP_MAX_C - 0.8:
            if recent_average is not None and recent_average <= SAFE_TEMP_MAX_C - 0.6:
                return "Stabilized"
            return "Mitigating"
        if vehicle_row["status"] == "Stabilized" and display_temperature is not None and display_temperature <= SAFE_TEMP_MAX_C - 1.0:
            return "Nominal"
        if vehicle_row["status"] in {"Watch", "Mitigating"} and display_temperature is not None and display_temperature < SAFE_TEMP_MAX_C:
            return vehicle_row["status"]
        return vehicle_row["status"]

    def _decay_risk(self, vehicle_row, display_temperature):
        base_risk = max(8, int(vehicle_row["risk_score"]) - 2)
        if display_temperature is not None and display_temperature > SAFE_TEMP_MAX_C:
            base_risk += 6
        if vehicle_row["status"] == "Critical":
            base_risk += 3
        return clamp(base_risk, 0, 100)


class AutonomousColdChainEngine:
    def __init__(self):
        self.monitoring_agent = MonitoringAgent()
        self.detection_agent = DetectionAgent()
        self.decision_agent = DecisionAgent()
        self.action_agent = ActionAgent()
        self._stop_event = threading.Event()
        self._thread = None
        self.cycle_number = 0

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop, name="cold-chain-engine", daemon=True)
        self._thread.start()

    def _run_loop(self):
        # This thread can later be promoted to a dedicated worker or task queue.
        while not self._stop_event.is_set():
            self.cycle_number += 1
            self.monitoring_agent.collect_cycle(self.cycle_number)
            self.detection_agent.detect_cycle()
            self.decision_agent.process_pending_events()
            self.action_agent.execute_pending_decisions()
            self._record_metrics()
            time.sleep(SIMULATION_INTERVAL_SECONDS)

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _record_metrics(self):
        snapshot = fetch_all(
            """
            SELECT
                COUNT(*) AS total_vehicles,
                SUM(CASE WHEN status IN ('Watch', 'Mitigating', 'Critical', 'Stabilized') THEN 1 ELSE 0 END) AS active_alerts,
                AVG(COALESCE(temperature, 0)) AS average_temperature
            FROM vehicles
            """
        )[0]
        log_count = fetch_all("SELECT COUNT(*) AS count FROM logs")[0]["count"]
        with DATABASE_LOCK:
            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO system_metrics (
                        timestamp, total_vehicles, anomalies_detected,
                        active_alerts, average_temperature
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        utc_now_iso(),
                        snapshot["total_vehicles"],
                        log_count,
                        snapshot["active_alerts"] or 0,
                        round(snapshot["average_temperature"] or 0, 2),
                    ),
                )
                connection.commit()

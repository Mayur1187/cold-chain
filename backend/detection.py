from datetime import datetime, timedelta, timezone

from config import (
    EVENT_COOLDOWN_SECONDS,
    RAPID_RISE_DELTA_C,
    SAFE_TEMP_MAX_C,
    SAFE_TEMP_MIN_C,
    SUSTAINED_ANOMALY_CYCLES,
)
from database import DATABASE_LOCK, fetch_all, fetch_one, get_connection
from utils import parse_iso_timestamp, rolling_average, utc_now_iso


class DetectionAgent:
    def detect_cycle(self):
        vehicles = fetch_all("SELECT * FROM vehicles ORDER BY id")
        for vehicle in vehicles:
            event = self._build_event(vehicle)
            if event and self._can_emit(vehicle["id"], event["anomaly_type"]):
                self._persist_event(vehicle["id"], event)

    def _build_event(self, vehicle):
        history = fetch_all(
            """
            SELECT temperature, timestamp, missing
            FROM sensor_history
            WHERE vehicle_id = ?
            ORDER BY id DESC
            LIMIT 6
            """,
            (vehicle["id"],),
        )
        if not history:
            return None

        latest = history[0]
        temperatures = [row["temperature"] for row in history if row["temperature"] is not None]
        recent_non_null = temperatures[:4]
        baseline = rolling_average(temperatures[1:6]) or vehicle.get("temperature") or 0

        if latest["missing"]:
            return {
                "temperature": vehicle.get("temperature"),
                "anomaly_type": "missing_data",
                "severity": "warning",
                "evidence": "Latest telemetry packet is missing, fallback values are being used.",
            }

        latest_temp = latest["temperature"]
        previous_temp = None
        for row in history[1:]:
            if row["temperature"] is not None:
                previous_temp = row["temperature"]
                break

        consecutive_hot = 0
        for row in history:
            if row["temperature"] is not None and row["temperature"] > SAFE_TEMP_MAX_C:
                consecutive_hot += 1
            else:
                break

        if consecutive_hot >= SUSTAINED_ANOMALY_CYCLES:
            return {
                "temperature": latest_temp,
                "anomaly_type": "sustained_anomaly",
                "severity": "critical",
                "evidence": (
                    f"Temperature exceeded {SAFE_TEMP_MAX_C:.1f}C for "
                    f"{consecutive_hot} consecutive cycles."
                ),
            }

        if latest_temp is not None and (
            latest_temp > SAFE_TEMP_MAX_C or latest_temp < SAFE_TEMP_MIN_C
        ):
            return {
                "temperature": latest_temp,
                "anomaly_type": "threshold_breach",
                "severity": "high",
                "evidence": (
                    f"Reading is {latest_temp:.1f}C against the safe band "
                    f"{SAFE_TEMP_MIN_C:.1f}-{SAFE_TEMP_MAX_C:.1f}C."
                ),
            }

        if (
            latest_temp is not None
            and previous_temp is not None
            and latest_temp - previous_temp >= RAPID_RISE_DELTA_C
        ):
            return {
                "temperature": latest_temp,
                "anomaly_type": "rapid_increase",
                "severity": "warning",
                "evidence": (
                    f"Temperature climbed {latest_temp - previous_temp:.1f}C in one cycle "
                    f"from a {baseline:.1f}C rolling baseline."
                ),
            }

        recent_average = rolling_average(recent_non_null)
        if recent_average and recent_average > SAFE_TEMP_MAX_C - 0.4:
            return {
                "temperature": latest_temp,
                "anomaly_type": "sustained_anomaly",
                "severity": "high",
                "evidence": "Temperature trend is persistently drifting toward a sustained breach.",
            }

        return None

    def _can_emit(self, vehicle_id, anomaly_type):
        latest_event = fetch_one(
            """
            SELECT timestamp
            FROM agent_events
            WHERE vehicle_id = ? AND anomaly_type = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (vehicle_id, anomaly_type),
        )
        if not latest_event:
            return True

        latest_timestamp = parse_iso_timestamp(latest_event["timestamp"])
        if not latest_timestamp:
            return True

        return datetime.now(timezone.utc) - latest_timestamp >= timedelta(
            seconds=EVENT_COOLDOWN_SECONDS
        )

    def _persist_event(self, vehicle_id, event):
        with DATABASE_LOCK:
            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO agent_events (
                        timestamp, vehicle_id, temperature, anomaly_type,
                        severity, evidence, processed
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        utc_now_iso(),
                        vehicle_id,
                        event["temperature"],
                        event["anomaly_type"],
                        event["severity"],
                        event["evidence"],
                    ),
                )
                connection.commit()

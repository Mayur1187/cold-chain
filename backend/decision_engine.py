from config import RISK_SCORE_CAP, SAFE_TEMP_MAX_C, SAFE_TEMP_MIN_C
from database import DATABASE_LOCK, fetch_all, fetch_one, get_connection
from utils import clamp, rolling_average, utc_now_iso


class DecisionAgent:
    def process_pending_events(self):
        pending_events = fetch_all(
            """
            SELECT *
            FROM agent_events
            WHERE processed = 0
            ORDER BY id ASC
            """
        )
        for event in pending_events:
            decision = self._build_decision(event)
            if not decision:
                continue
            with DATABASE_LOCK:
                with get_connection() as connection:
                    connection.execute(
                        """
                        INSERT INTO agent_decisions (
                            event_id, timestamp, vehicle_id, anomaly_type,
                            recommended_action, reason, target_status, risk_score,
                            cooling_command, reroute_command, executed
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                        """,
                        (
                            event["id"],
                            utc_now_iso(),
                            event["vehicle_id"],
                            event["anomaly_type"],
                            decision["recommended_action"],
                            decision["reason"],
                            decision["target_status"],
                            decision["risk_score"],
                            decision["cooling_command"],
                            decision["reroute_command"],
                        ),
                    )
                    connection.execute(
                        "UPDATE agent_events SET processed = 1 WHERE id = ?",
                        (event["id"],),
                    )
                    connection.commit()

    def _build_decision(self, event):
        vehicle = fetch_one("SELECT * FROM vehicles WHERE id = ?", (event["vehicle_id"],))
        history_rows = fetch_all(
            """
            SELECT temperature
            FROM sensor_history
            WHERE vehicle_id = ?
            ORDER BY id DESC
            LIMIT 8
            """,
            (event["vehicle_id"],),
        )
        temperatures = [row["temperature"] for row in history_rows if row["temperature"] is not None]
        rolling_baseline = rolling_average(temperatures[1:]) or vehicle["temperature"] or 0
        latest_temp = event["temperature"] if event["temperature"] is not None else vehicle["temperature"]
        excess = max(0, (latest_temp or rolling_baseline) - SAFE_TEMP_MAX_C)

        if event["anomaly_type"] == "rapid_increase":
            risk_score = clamp(52 + excess * 8 + vehicle["risk_score"] * 0.15, 0, RISK_SCORE_CAP)
            return {
                "recommended_action": "Activate preemptive cooling and raise watch alert",
                "reason": (
                    f"Temperature is climbing faster than expected: {event['evidence']} "
                    f"Baseline behavior was {rolling_baseline:.1f}C."
                ),
                "target_status": "Watch",
                "risk_score": int(risk_score),
                "cooling_command": 1,
                "reroute_command": 0,
            }

        if event["anomaly_type"] == "threshold_breach":
            needs_reroute = True
            target_status = "Critical"
            risk_score = clamp(64 + excess * 12 + vehicle["risk_score"] * 0.1, 0, RISK_SCORE_CAP)
            return {
                "recommended_action": "Activate cooling, alert operations, and reroute to cold hub",
                "reason": (
                    f"Reading moved outside the validated band of {SAFE_TEMP_MIN_C:.1f}-{SAFE_TEMP_MAX_C:.1f}C. "
                    f"Historical baseline was {rolling_baseline:.1f}C."
                ),
                "target_status": target_status,
                "risk_score": int(risk_score),
                "cooling_command": 1,
                "reroute_command": 1 if needs_reroute else 0,
            }

        if event["anomaly_type"] == "sustained_anomaly":
            risk_score = clamp(78 + excess * 10 + vehicle["risk_score"] * 0.12, 0, RISK_SCORE_CAP)
            return {
                "recommended_action": "Escalate, force cooling, and reroute to nearest cold storage hub",
                "reason": (
                    f"{event['evidence']} The vehicle has diverged from its {rolling_baseline:.1f}C trend "
                    "for long enough to threaten product integrity."
                ),
                "target_status": "Critical",
                "risk_score": int(risk_score),
                "cooling_command": 1,
                "reroute_command": 1,
            }

        if event["anomaly_type"] == "missing_data":
            risk_score = clamp(max(vehicle["risk_score"], 35), 0, RISK_SCORE_CAP)
            return {
                "recommended_action": "Switch to fallback telemetry, notify fleet ops, continue monitoring",
                "reason": (
                    "A telemetry gap was detected. The platform is preserving last-known-safe values while "
                    "waiting for the next sensor packet."
                ),
                "target_status": "Watch",
                "risk_score": int(risk_score),
                "cooling_command": 0,
                "reroute_command": 0,
            }

        return None

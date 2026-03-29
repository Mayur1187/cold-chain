import json
import math
from datetime import datetime, timedelta, timezone

from config import RESET_DEMO_STATE, SEED_VEHICLES, SIMULATION_INTERVAL_SECONDS
from database import get_connection


SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        temperature REAL,
        status TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        destination TEXT NOT NULL,
        eta_minutes INTEGER NOT NULL,
        risk_score INTEGER NOT NULL DEFAULT 10,
        cooling_active INTEGER NOT NULL DEFAULT 0,
        speed_kmh REAL NOT NULL DEFAULT 50,
        last_seen TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        vehicle_id INTEGER,
        temperature REAL,
        anomaly_type TEXT,
        action_taken TEXT NOT NULL,
        reason TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'info',
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER UNIQUE NOT NULL,
        route_data TEXT NOT NULL,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS system_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        total_vehicles INTEGER NOT NULL,
        anomalies_detected INTEGER NOT NULL,
        active_alerts INTEGER NOT NULL,
        average_temperature REAL NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS sensor_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        vehicle_id INTEGER NOT NULL,
        temperature REAL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        status TEXT NOT NULL,
        missing INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        vehicle_id INTEGER NOT NULL,
        temperature REAL,
        anomaly_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        evidence TEXT NOT NULL,
        processed INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        vehicle_id INTEGER NOT NULL,
        anomaly_type TEXT NOT NULL,
        recommended_action TEXT NOT NULL,
        reason TEXT NOT NULL,
        target_status TEXT NOT NULL,
        risk_score INTEGER NOT NULL,
        cooling_command INTEGER NOT NULL DEFAULT 0,
        reroute_command INTEGER NOT NULL DEFAULT 0,
        executed INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (event_id) REFERENCES agent_events(id),
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
    );
    """,
]


def initialize_database(reset_demo_state=RESET_DEMO_STATE):
    with get_connection() as connection:
        for statement in SCHEMA:
            connection.execute(statement)

        if reset_demo_state:
            _reset_demo_tables(connection)

        vehicle_count = connection.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        if vehicle_count == 0:
            _seed_demo_data(connection)

        connection.commit()


def _reset_demo_tables(connection):
    connection.executescript(
        """
        DELETE FROM agent_decisions;
        DELETE FROM agent_events;
        DELETE FROM logs;
        DELETE FROM sensor_history;
        DELETE FROM system_metrics;
        DELETE FROM routes;
        DELETE FROM vehicles;
        DELETE FROM sqlite_sequence WHERE name IN (
            'agent_decisions', 'agent_events', 'logs', 'sensor_history',
            'system_metrics', 'routes', 'vehicles'
        );
        """
    )


def _seed_demo_data(connection):
    inserted_vehicle_ids = []
    for vehicle in SEED_VEHICLES:
        cursor = connection.execute(
            """
            INSERT INTO vehicles (
                name, temperature, status, latitude, longitude, destination,
                eta_minutes, risk_score, cooling_active, speed_kmh, last_seen
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                vehicle["name"],
                vehicle["temperature"],
                vehicle["status"],
                vehicle["latitude"],
                vehicle["longitude"],
                vehicle["destination"],
                vehicle["eta_minutes"],
                12,
                0,
                vehicle["speed_kmh"],
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        vehicle_id = cursor.lastrowid
        inserted_vehicle_ids.append(vehicle_id)

        route_data = dict(vehicle["route"])
        route_data["simulation_pattern"] = vehicle["simulation_pattern"]
        route_data["original_destination"] = vehicle["destination"]
        route_data["rerouted"] = False
        connection.execute(
            "INSERT INTO routes (vehicle_id, route_data) VALUES (?, ?)",
            (vehicle_id, json.dumps(route_data)),
        )

        _seed_history_for_vehicle(connection, vehicle_id, vehicle)

    connection.execute(
        """
        INSERT INTO system_metrics (timestamp, total_vehicles, anomalies_detected, active_alerts, average_temperature)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            len(inserted_vehicle_ids),
            0,
            0,
            round(sum(vehicle["temperature"] for vehicle in SEED_VEHICLES) / len(SEED_VEHICLES), 2),
        ),
    )
    connection.execute(
        """
        INSERT INTO logs (timestamp, vehicle_id, temperature, anomaly_type, action_taken, reason, severity)
        VALUES (?, NULL, NULL, NULL, ?, ?, 'info')
        """,
        (
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "Autonomous monitoring online",
            "Monitoring, detection, decision, action, and reroute agents are active.",
        ),
    )


def _seed_history_for_vehicle(connection, vehicle_id, vehicle):
    baseline_temp = vehicle["temperature"]
    route_points = vehicle["route"]["points"]
    now = datetime.now(timezone.utc)
    for offset in range(12, 0, -1):
        ratio = max(0.0, vehicle["route"]["progress"] - offset * 0.004)
        point_index = min(int(ratio * (len(route_points) - 1)), len(route_points) - 1)
        point = route_points[point_index]
        history_temp = round(
            baseline_temp
            + math.sin((offset + vehicle_id) / 2.7) * 0.18
            - (0.08 if vehicle["simulation_pattern"] == "gradual_rise" and offset < 3 else 0),
            2,
        )
        connection.execute(
            """
            INSERT INTO sensor_history (timestamp, vehicle_id, temperature, latitude, longitude, status, missing)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (
                (now - timedelta(seconds=offset * SIMULATION_INTERVAL_SECONDS)).isoformat(timespec="seconds"),
                vehicle_id,
                history_temp,
                point["latitude"],
                point["longitude"],
                vehicle["status"],
            ),
        )

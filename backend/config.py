import os
import tempfile


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
FRONTEND_TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "frontend", "templates")
FRONTEND_STATIC_DIR = os.path.join(PROJECT_ROOT, "frontend", "static")
IS_VERCEL = os.environ.get("VERCEL") == "1"
DATABASE_PATH = os.path.join(tempfile.gettempdir(), "cold_chain.db") if IS_VERCEL else os.path.join(BASE_DIR, "cold_chain.db")

APP_NAME = "Autonomous Cold Chain Intelligence Platform"
APP_HOST = "127.0.0.1"
APP_PORT = 5000

# Demo-oriented bootstrap. Set to False to preserve state across restarts.
RESET_DEMO_STATE = True

SIMULATION_INTERVAL_SECONDS = 4
EVENT_COOLDOWN_SECONDS = 12
SUSTAINED_ANOMALY_CYCLES = 3
RAPID_RISE_DELTA_C = 1.4
SAFE_TEMP_MIN_C = 2.0
SAFE_TEMP_MAX_C = 8.0
COOLING_RECOVERY_STEP_C = 0.9
RISK_SCORE_CAP = 100
MAX_LOG_ROWS = 150
MISSING_DATA_INTERVAL = 15

ROUTE_NORMAL_COLOR = "#1f8ea3"
ROUTE_WARNING_COLOR = "#e9a03b"
ROUTE_ALERT_COLOR = "#df6a4d"
ROUTE_STABLE_COLOR = "#2a9d8f"

LEAFLET_FALLBACK_CENTER = {"latitude": 39.9526, "longitude": -75.1652}

COLD_STORAGE_HUBS = [
    {
        "name": "Newark Cold Hub",
        "latitude": 40.7357,
        "longitude": -74.1724,
        "capacity_label": "High-capacity pharma dock",
    },
    {
        "name": "Boston Med Storage",
        "latitude": 42.3601,
        "longitude": -71.0589,
        "capacity_label": "Ultra-low vaccine storage",
    },
    {
        "name": "Baltimore Bio Hub",
        "latitude": 39.2904,
        "longitude": -76.6122,
        "capacity_label": "Regulated biologics handling",
    },
    {
        "name": "Raleigh Food Reserve",
        "latitude": 35.7796,
        "longitude": -78.6382,
        "capacity_label": "Fresh food contingency storage",
    },
]

SEED_VEHICLES = [
    {
        "name": "Polar-01",
        "temperature": 4.4,
        "status": "Nominal",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "destination": "Boston Medical Hub",
        "eta_minutes": 92,
        "speed_kmh": 58,
        "simulation_pattern": "steady",
        "route": {
            "route_name": "Northeast Vaccine Corridor",
            "eta_base_minutes": 92,
            "movement_step": 0.026,
            "progress": 0.12,
            "color": ROUTE_NORMAL_COLOR,
            "points": [
                {"latitude": 40.7128, "longitude": -74.0060},
                {"latitude": 41.3083, "longitude": -72.9279},
                {"latitude": 41.8240, "longitude": -71.4128},
                {"latitude": 42.3601, "longitude": -71.0589},
            ],
        },
    },
    {
        "name": "Atlas-07",
        "temperature": 4.8,
        "status": "Nominal",
        "latitude": 39.9526,
        "longitude": -75.1652,
        "destination": "Washington Clinical Node",
        "eta_minutes": 84,
        "speed_kmh": 54,
        "simulation_pattern": "gradual_rise",
        "route": {
            "route_name": "Mid-Atlantic Biologics Run",
            "eta_base_minutes": 84,
            "movement_step": 0.029,
            "progress": 0.08,
            "color": ROUTE_NORMAL_COLOR,
            "points": [
                {"latitude": 39.9526, "longitude": -75.1652},
                {"latitude": 39.7684, "longitude": -75.5294},
                {"latitude": 39.2904, "longitude": -76.6122},
                {"latitude": 38.9072, "longitude": -77.0369},
            ],
        },
    },
    {
        "name": "Harbor-12",
        "temperature": 5.1,
        "status": "Nominal",
        "latitude": 35.7796,
        "longitude": -78.6382,
        "destination": "Richmond Cross Dock",
        "eta_minutes": 74,
        "speed_kmh": 52,
        "simulation_pattern": "steady",
        "route": {
            "route_name": "Fresh Freight Southbound",
            "eta_base_minutes": 74,
            "movement_step": 0.024,
            "progress": 0.18,
            "color": ROUTE_NORMAL_COLOR,
            "points": [
                {"latitude": 35.7796, "longitude": -78.6382},
                {"latitude": 36.0726, "longitude": -79.7920},
                {"latitude": 36.8508, "longitude": -76.2859},
                {"latitude": 37.5407, "longitude": -77.4360},
            ],
        },
    },
    {
        "name": "Nova-21",
        "temperature": 4.1,
        "status": "Nominal",
        "latitude": 41.7637,
        "longitude": -72.6851,
        "destination": "Newark Cold Hub",
        "eta_minutes": 81,
        "speed_kmh": 56,
        "simulation_pattern": "spike",
        "route": {
            "route_name": "Critical Immunization Lane",
            "eta_base_minutes": 81,
            "movement_step": 0.027,
            "progress": 0.05,
            "color": ROUTE_NORMAL_COLOR,
            "points": [
                {"latitude": 41.7637, "longitude": -72.6851},
                {"latitude": 41.0534, "longitude": -73.5387},
                {"latitude": 40.7357, "longitude": -74.1724},
            ],
        },
    },
    {
        "name": "Mercury-03",
        "temperature": 5.0,
        "status": "Nominal",
        "latitude": 42.6526,
        "longitude": -73.7562,
        "destination": "Hudson Regional Dock",
        "eta_minutes": 88,
        "speed_kmh": 50,
        "simulation_pattern": "oscillating",
        "route": {
            "route_name": "Regional Produce Priority",
            "eta_base_minutes": 88,
            "movement_step": 0.023,
            "progress": 0.1,
            "color": ROUTE_NORMAL_COLOR,
            "points": [
                {"latitude": 42.6526, "longitude": -73.7562},
                {"latitude": 42.0987, "longitude": -75.9180},
                {"latitude": 41.7658, "longitude": -72.6734},
                {"latitude": 40.7357, "longitude": -74.1724},
            ],
        },
    },
]

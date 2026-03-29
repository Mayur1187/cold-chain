# Autonomous Cold Chain Intelligence Platform

Production-inspired, hackathon-ready prototype for autonomous cold-chain monitoring with Flask, SQLite, and a multi-page vanilla frontend.

## Folder Structure

```text
backend/
    app.py
    routes.py
    simulation.py
    detection.py
    decision_engine.py
    actions.py
    database.py
    models.py
    config.py
    utils.py
frontend/
    templates/
        base.html
        index.html
        vehicles.html
        map.html
        logs.html
    static/
        css/
            styles.css
        js/
            main.js
            map.js
            vehicles.js
requirements.txt
README.md
```

## What It Does

- Simulates a live fleet of cold-chain vehicles.
- Writes telemetry, logs, routes, and metrics into SQLite.
- Detects threshold breaches, rapid rises, and sustained anomalies.
- Makes rule-based decisions with explanations.
- Executes autonomous actions such as alerts, cooling activation, and rerouting.
- Shows a clean dashboard, fleet view, map view, and logs view.

## Run It

1. Create and activate a virtual environment:

```powershell
cd c:\test
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the app:

```bash
python backend/app.py
```

4. Open `http://127.0.0.1:5000`

## Deploy on Railway

This project is now deployment-ready for Railway with:

- `Procfile` for the production web start command
- `gunicorn` included in `requirements.txt`
- `runtime.txt` for Python version pinning

### One-time setup

1. Push this project to GitHub.
2. In Railway, create a new project from that GitHub repo.
3. Railway will auto-detect Python and install dependencies from `requirements.txt`.
4. Railway will run the `web` process from `Procfile`.

### Required Railway service settings

- Start command is already defined in `Procfile`:
  `cd backend && gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
- No extra environment variables are required for a basic deploy.

### Important SQLite note for Railway

SQLite works for demo/hackathon deployment, but Railway containers have ephemeral filesystems by default.

- Without a persistent volume, `backend/cold_chain.db` resets on redeploy/restart.
- For persistent data, attach a Railway volume and point `DATABASE_PATH` to that mounted path, or move to Postgres for production.

### Quick deploy check

After deployment:

1. Open your Railway public URL.
2. Confirm dashboard loads.
3. Wait about 20 to 40 seconds.
4. Confirm anomaly -> action -> log behavior appears automatically.

## Beginner Guide: Understand and Use the System

If you are using this for the first time, think of it as a self-running control tower.

- You do not need to click any "start simulation" button.
- As soon as `python backend/app.py` runs, the system starts autonomous monitoring.
- Data updates every few seconds in the background.

### What is happening behind the scenes

The platform runs a continuous loop with independent agents:

1. Monitoring Agent collects vehicle telemetry.
2. Detection Agent checks for anomalies.
3. Decision Agent chooses what action to take.
4. Action Agent executes interventions.
5. Route Optimization Agent reroutes critical vehicles.

All agents share state through SQLite tables, so this behaves like a real modular backend rather than a one-file script.

### How to read each page

- Dashboard: high-level system health, active alerts, and most critical vehicle.
- Vehicles: full fleet state including temperature, risk score, ETA, and status.
- Map: live vehicle locations, route lines, hubs, and reroutes.
- Logs: event history with action and reason ("why this decision happened").

### What to expect in the first 20 to 40 seconds

For demo clarity, the simulation is tuned to show visible autonomous behavior quickly:

- A vehicle temperature pattern becomes abnormal.
- Status changes from nominal to warning/critical flow.
- Cooling and/or reroute actions are applied automatically.
- The logs page shows clear reasons for each action.

### Common terms (quick glossary)

- Nominal: operating in safe range.
- Watch: early warning state.
- Mitigating: active intervention in progress.
- Critical: high risk, escalation and reroute likely.
- Risk score: urgency value from low to high.

### If something looks broken

- If no data appears, refresh the page once after server startup.
- If map tiles fail to load, the system still works; route and hub summaries remain visible.
- If you changed config values and want a clean demo reset, restart the app.

## Notes

- The simulation starts automatically when the Flask app starts.
- Demo anomalies are intentionally scheduled to appear within roughly 20 to 40 seconds.
- The SQLite database is stored at `backend/cold_chain.db`.
- The config is intentionally centralized in `backend/config.py` for easy scaling and tuning.
- For production scale, the autonomous loop can be moved from a background thread to a worker queue or scheduler.

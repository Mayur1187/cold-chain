import os
import sys

from flask import Flask

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from config import APP_HOST, APP_NAME, APP_PORT, FRONTEND_STATIC_DIR, FRONTEND_TEMPLATE_DIR, IS_VERCEL
from models import initialize_database
from routes import register_routes
from simulation import AutonomousColdChainEngine


engine = None


def create_app():
    app = Flask(
        __name__,
        template_folder=FRONTEND_TEMPLATE_DIR,
        static_folder=FRONTEND_STATIC_DIR,
        static_url_path="/static",
    )
    app.config["APP_NAME"] = APP_NAME

    initialize_database()
    register_routes(app)

    global engine
    if engine is None and not IS_VERCEL:
        engine = AutonomousColdChainEngine()
        engine.start()
        app.extensions["autonomous_engine"] = engine

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=False, use_reloader=False, threaded=True)

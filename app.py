"""
DataLens — Application entry point
Run with: python app.py
"""

import os
from flask import Flask
from extensions import db
from routes import bp

def create_app() -> Flask:
    app = Flask(__name__)

    # ── Configuration ──────────────────────────────────────────────────
    app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-in-production")

    # SQLite DB stored in the instance/ folder (auto-created, excluded from git)
    db_path = os.path.join(app.instance_path, "datalens.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Upload folder
    upload_folder = os.path.join(os.path.dirname(__file__), "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = upload_folder

    # ── Extensions ─────────────────────────────────────────────────────
    db.init_app(app)

    # ── Blueprints ─────────────────────────────────────────────────────
    app.register_blueprint(bp)

    # ── Create tables ──────────────────────────────────────────────────
    with app.app_context():
        os.makedirs(app.instance_path, exist_ok=True)
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)

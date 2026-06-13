"""
DataLens — Shared extensions
Create extension objects here so they can be imported by both
app.py and models.py without circular-import issues.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

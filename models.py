"""
DataLens — Database models (SQLite via SQLAlchemy)
Replaces Flask cookie sessions so multiple concurrent users work correctly.
"""

from datetime import datetime, timezone
from extensions import db


class UploadSession(db.Model):
    """
    Stores per-upload state so the /configure → /dashboard flow is stateless
    from Flask's perspective.  Each browser visit gets a UUID token that lives
    in a short-lived cookie; the real payload is server-side in SQLite.
    """
    __tablename__ = "upload_session"

    id          = db.Column(db.Integer, primary_key=True)
    token       = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # File metadata
    file_path   = db.Column(db.String(512))
    filename    = db.Column(db.String(256))
    file_rows   = db.Column(db.Integer)
    file_cols   = db.Column(db.Integer)

    # JSON blobs — stored as TEXT (SQLite is fine with this)
    columns_json  = db.Column(db.Text)   # list of column names
    guesses_json  = db.Column(db.Text)   # {col: role}
    samples_json  = db.Column(db.Text)   # {col: [sample values]}
    schema_json   = db.Column(db.Text)   # confirmed {col: role}
    warnings_json = db.Column(db.Text)   # {col: warning_msg}

    # ── comparison dataset (optional) ──
    file_path_b   = db.Column(db.String(512))
    filename_b    = db.Column(db.String(256))
    columns_json_b  = db.Column(db.Text)
    guesses_json_b  = db.Column(db.Text)
    samples_json_b  = db.Column(db.Text)
    schema_json_b   = db.Column(db.Text)

    def __repr__(self):
        return f"<UploadSession {self.token[:8]}… {self.filename}>"

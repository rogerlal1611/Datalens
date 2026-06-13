"""
DataLens — Route handlers
"""

import json
import os
import uuid

import pandas as pd
from flask import (
    Blueprint, redirect, render_template, request,
    make_response, send_file, url_for, abort,
)
from werkzeug.utils import secure_filename

from analysis import build_analysis, build_comparison
from extensions import db
from models import UploadSession
from utils import COLUMN_ROLES, guess_role, validate_schema

bp = Blueprint("main", __name__)

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}
MAX_FILE_MB        = 50
UPLOAD_FOLDER      = "uploads"
_TOKEN_COOKIE      = "dl_token"


# ── helpers ──────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def check_file_size(file) -> float:
    file.seek(0, 2)
    mb = file.tell() / (1024 * 1024)
    file.seek(0)
    return mb


def read_file(path: str) -> pd.DataFrame:
    if path.endswith(".csv"):
        if os.path.getsize(path) / (1024 * 1024) > 10:
            return pd.concat(pd.read_csv(path, chunksize=5000), ignore_index=True)
        return pd.read_csv(path)
    return pd.read_excel(path)


def get_session(token: str):
    if not token:
        return None
    return UploadSession.query.filter_by(token=token).first()


def _save_file(file) -> tuple[str, str]:
    filename = secure_filename(file.filename)
    unique   = f"{uuid.uuid4().hex}_{filename}"
    path     = os.path.join(UPLOAD_FOLDER, unique)
    file.save(path)
    return path, filename


def _build_samples(df: pd.DataFrame) -> dict:
    samples = {}
    for col in df.columns:
        vals = df[col].dropna().unique()[:4].tolist()
        samples[col] = [str(v) for v in vals]
    return samples


def _set_token_cookie(response, token: str):
    response.set_cookie(
        _TOKEN_COOKIE, token,
        max_age=3600, httponly=True, samesite="Lax"
    )
    return response


# ── HOME ─────────────────────────────────────────────────────────────────

@bp.route("/")
def home():
    return render_template("index.html")


# ── SINGLE UPLOAD ─────────────────────────────────────────────────────────

@bp.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file or not file.filename or not allowed_file(file.filename):
        return redirect(url_for("main.home", error="invalid"))

    if check_file_size(file) > MAX_FILE_MB:
        return redirect(url_for("main.home", error="toolarge"))

    try:
        path, filename = _save_file(file)
        df = read_file(path)
        if len(df) > 100_000:
            df = df.sample(100_000, random_state=42)

        sess = UploadSession(
            token        = uuid.uuid4().hex,
            file_path    = path,
            filename     = filename,
            file_rows    = len(df),
            file_cols    = len(df.columns),
            columns_json = json.dumps(df.columns.tolist()),
            guesses_json = json.dumps({c: guess_role(c) for c in df.columns}),
            samples_json = json.dumps(_build_samples(df)),
        )
        db.session.add(sess)
        db.session.commit()

    except Exception:
        return redirect(url_for("main.home", error="parse"))

    resp = make_response(redirect(url_for("main.configure")))
    return _set_token_cookie(resp, sess.token)


# ── COMPARE UPLOAD (both files in one POST) ───────────────────────────────

@bp.route("/upload/compare", methods=["POST"])
def upload_compare():
    """
    Receives file_a and file_b in a single multipart POST.
    Saves both, stores metadata for A on the session, stores B metadata too,
    then redirects to configure A first.
    """
    file_a = request.files.get("file_a")
    file_b = request.files.get("file_b")

    # Validate both files present
    if not file_a or not file_a.filename or not file_b or not file_b.filename:
        return redirect(url_for("main.home", error="nofiles", tab="compare"))

    if not allowed_file(file_a.filename) or not allowed_file(file_b.filename):
        return redirect(url_for("main.home", error="invalid", tab="compare"))

    if check_file_size(file_a) > MAX_FILE_MB or check_file_size(file_b) > MAX_FILE_MB:
        return redirect(url_for("main.home", error="toolarge", tab="compare"))

    try:
        path_a, fname_a = _save_file(file_a)
        path_b, fname_b = _save_file(file_b)

        df_a = read_file(path_a)
        df_b = read_file(path_b)
        if len(df_a) > 100_000:
            df_a = df_a.sample(100_000, random_state=42)
        if len(df_b) > 100_000:
            df_b = df_b.sample(100_000, random_state=42)

        sess = UploadSession(
            token           = uuid.uuid4().hex,
            # Dataset A
            file_path       = path_a,
            filename        = fname_a,
            file_rows       = len(df_a),
            file_cols       = len(df_a.columns),
            columns_json    = json.dumps(df_a.columns.tolist()),
            guesses_json    = json.dumps({c: guess_role(c) for c in df_a.columns}),
            samples_json    = json.dumps(_build_samples(df_a)),
            # Dataset B — stored now, configured later
            file_path_b     = path_b,
            filename_b      = fname_b,
            columns_json_b  = json.dumps(df_b.columns.tolist()),
            guesses_json_b  = json.dumps({c: guess_role(c) for c in df_b.columns}),
            samples_json_b  = json.dumps(_build_samples(df_b)),
        )
        db.session.add(sess)
        db.session.commit()

    except Exception:
        return redirect(url_for("main.home", error="parse", tab="compare"))

    # Go to configure A first; configure A's POST will redirect to configure B
    resp = make_response(redirect(url_for("main.configure_a")))
    return _set_token_cookie(resp, sess.token)


# ── CONFIGURE A (compare flow) ────────────────────────────────────────────

@bp.route("/configure/a", methods=["GET", "POST"])
def configure_a():
    """Map columns for Dataset A (compare mode). On POST → go to configure B."""
    token = request.cookies.get(_TOKEN_COOKIE)
    sess  = get_session(token)
    if not sess or not sess.file_path_b:          # must be a compare session
        return redirect(url_for("main.home"))

    columns = json.loads(sess.columns_json  or "[]")
    guesses = json.loads(sess.guesses_json  or "{}")
    samples = json.loads(sess.samples_json  or "{}")
    shape   = [sess.file_rows, sess.file_cols]

    if request.method == "POST":
        schema_a = {
            col: request.form.get(f"role_{col}", "ignore")
            for col in columns
            if request.form.get(f"enable_{col}") == "on"
        }
        df_a = read_file(sess.file_path)
        warnings_a = validate_schema(df_a, schema_a)

        sess.schema_json   = json.dumps(schema_a)
        sess.warnings_json = json.dumps(warnings_a)
        db.session.commit()

        return redirect(url_for("main.configure_b"))

    return render_template(
        "configure.html",
        columns      = columns,
        guesses      = guesses,
        samples      = samples,
        shape        = shape,
        roles        = COLUMN_ROLES,
        configure_b  = False,       # this is A
        is_compare   = True,
        step_label   = f"Configure Dataset A — {sess.filename}",
        next_label   = "Next: Map Dataset B →",
    )


# ── CONFIGURE B (compare flow) ────────────────────────────────────────────

@bp.route("/configure/b", methods=["GET", "POST"])
def configure_b():
    """Map columns for Dataset B. On POST → go to compare dashboard."""
    token = request.cookies.get(_TOKEN_COOKIE)
    sess  = get_session(token)
    if not sess or not sess.file_path_b:
        return redirect(url_for("main.home"))

    columns = json.loads(sess.columns_json_b or "[]")
    guesses = json.loads(sess.guesses_json_b or "{}")
    samples = json.loads(sess.samples_json_b or "{}")

    if request.method == "POST":
        schema_b = {
            col: request.form.get(f"role_{col}", "ignore")
            for col in columns
            if request.form.get(f"enable_{col}") == "on"
        }
        sess.schema_json_b = json.dumps(schema_b)
        db.session.commit()
        return redirect(url_for("main.compare_dashboard"))

    return render_template(
        "configure.html",
        columns     = columns,
        guesses     = guesses,
        samples     = samples,
        shape       = [0, len(columns)],
        roles       = COLUMN_ROLES,
        configure_b = True,
        is_compare  = True,
        step_label  = f"Configure Dataset B — {sess.filename_b}",
        next_label  = "Build Comparison →",
    )


# ── COMPARE DASHBOARD ─────────────────────────────────────────────────────

@bp.route("/compare")
def compare_dashboard():
    token = request.cookies.get(_TOKEN_COOKIE)
    sess  = get_session(token)

    if not sess:
        return redirect(url_for("main.home"))
    if not sess.schema_json:
        return redirect(url_for("main.home", error="noschema"))
    if not sess.schema_json_b:
        return redirect(url_for("main.configure_b"))
    if not sess.file_path or not os.path.exists(sess.file_path):
        return redirect(url_for("main.home", error="expired"))
    if not sess.file_path_b or not os.path.exists(sess.file_path_b):
        return redirect(url_for("main.home", error="expired"))

    df_a     = read_file(sess.file_path)
    df_b     = read_file(sess.file_path_b)
    schema_a = json.loads(sess.schema_json)
    schema_b = json.loads(sess.schema_json_b)

    comp = build_comparison(
        df_a, schema_a, df_b, schema_b,
        label_a = sess.filename  or "Dataset A",
        label_b = sess.filename_b or "Dataset B",
    )

    resp = make_response(render_template("compare.html", comp=comp, roles=COLUMN_ROLES))
    resp.headers.update({
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    })
    return resp


# ── SINGLE CONFIGURE ──────────────────────────────────────────────────────

@bp.route("/configure", methods=["GET", "POST"])
def configure():
    token = request.cookies.get(_TOKEN_COOKIE)
    sess  = get_session(token)
    if not sess or not sess.file_path or not os.path.exists(sess.file_path):
        return redirect(url_for("main.home"))

    columns = json.loads(sess.columns_json or "[]")
    guesses = json.loads(sess.guesses_json or "{}")
    samples = json.loads(sess.samples_json or "{}")
    shape   = [sess.file_rows, sess.file_cols]

    if request.method == "POST":
        schema = {
            col: request.form.get(f"role_{col}", "ignore")
            for col in columns
            if request.form.get(f"enable_{col}") == "on"
        }
        df = read_file(sess.file_path)
        warnings = validate_schema(df, schema)

        sess.schema_json   = json.dumps(schema)
        sess.warnings_json = json.dumps(warnings)
        db.session.commit()

        return redirect(url_for("main.dashboard"))

    return render_template(
        "configure.html",
        columns    = columns,
        guesses    = guesses,
        samples    = samples,
        shape      = shape,
        roles      = COLUMN_ROLES,
        is_compare = False,
        configure_b= False,
        step_label = None,
        next_label = "Build Dashboard →",
    )


# ── DASHBOARD ─────────────────────────────────────────────────────────────

@bp.route("/dashboard")
def dashboard():
    token = request.cookies.get(_TOKEN_COOKIE)
    sess  = get_session(token)
    if not sess or not sess.schema_json:
        return redirect(url_for("main.home"))
    if not sess.file_path or not os.path.exists(sess.file_path):
        return redirect(url_for("main.home", error="expired"))

    schema = json.loads(sess.schema_json)
    df     = read_file(sess.file_path)

    if not set(schema.keys()).issubset(set(df.columns.tolist())):
        return redirect(url_for("main.home", error="mismatch"))

    analysis = build_analysis(df, schema)
    warnings = json.loads(sess.warnings_json or "{}")
    shape    = [sess.file_rows or len(df), sess.file_cols or len(df.columns)]

    resp = make_response(render_template(
        "dashboard.html",
        analysis           = analysis,
        schema             = schema,
        shape              = shape,
        roles              = COLUMN_ROLES,
        validation_warnings= warnings,
        filename           = sess.filename,
    ))
    resp.headers.update({
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    })
    return resp


# ── API — date range filter ───────────────────────────────────────────────

@bp.route("/api/filter")
def api_filter():
    token = request.cookies.get(_TOKEN_COOKIE)
    sess  = get_session(token)
    if not sess or not sess.schema_json:
        return {"error": "no session"}, 400

    schema    = json.loads(sess.schema_json)
    date_from = request.args.get("from")
    date_to   = request.args.get("to")

    df = read_file(sess.file_path)

    date_col = next((c for c, r in schema.items() if r == "date"), None)
    if date_col and date_from and date_to:
        from utils import parse_dates_robust
        df[date_col] = parse_dates_robust(df[date_col].astype(str))
        mask = (
            (df[date_col] >= pd.Timestamp(date_from)) &
            (df[date_col] <= pd.Timestamp(date_to))
        )
        df = df[mask]

    analysis = build_analysis(df, schema)
    return analysis


# ── PDF EXPORT ────────────────────────────────────────────────────────────

@bp.route("/export/pdf")
def export_pdf():
    token = request.cookies.get(_TOKEN_COOKIE)
    sess  = get_session(token)
    if not sess or not sess.schema_json:
        abort(400)

    schema   = json.loads(sess.schema_json)
    df       = read_file(sess.file_path)
    analysis = build_analysis(df, schema)
    warnings = json.loads(sess.warnings_json or "{}")

    html_content = render_template(
        "pdf_export.html",
        analysis           = analysis,
        schema             = schema,
        roles              = COLUMN_ROLES,
        validation_warnings= warnings,
        filename           = sess.filename,
    )

    try:
        import pdfkit
        from io import BytesIO
        pdf_bytes = pdfkit.from_string(html_content, False, options={
            "page-size": "A4", "orientation": "Landscape",
            "margin-top": "10mm", "margin-right": "10mm",
            "margin-bottom": "10mm", "margin-left": "10mm",
            "encoding": "UTF-8", "quiet": "",
        })
        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"datalens_{sess.filename or 'report'}.pdf",
        )
    except Exception:
        return make_response(html_content, 200, {"Content-Type": "text/html"})


# ── ERROR HANDLERS ────────────────────────────────────────────────────────

@bp.app_errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@bp.app_errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500

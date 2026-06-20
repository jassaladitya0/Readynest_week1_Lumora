"""
app.py — Lumora
Flask backend: upload any dataset (CSV/XLSX/JSON), auto-clean it, run EDA,
generate charts + insights, and let the user download either the cleaned
dataset (in any format) or a full PDF report.

Architecture (Render-safe):
  POST /api/upload     → saves file, starts background thread, returns {session_id} immediately
  GET  /api/status/<id> → returns {status, data} so the frontend can poll
  GET  /api/download/... → download cleaned data or PDF report

Made by Aditya Jassal.
"""
import os
import io
import uuid
import pickle
import logging
import threading
from flask import Flask, render_template, request, jsonify, send_file

from cleaning import load_dataset, clean_dataset, save_dataset
from analysis import descriptive_stats, univariate_charts, bivariate_charts, extract_insights
from report import build_pdf_report

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Directories (writable on Render free tier) ─────────────────────────────────
UPLOAD_DIR = "/tmp/lumora_uploads"
OUTPUT_DIR = "/tmp/lumora_outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

ALLOWED_EXT = {"csv", "xlsx", "xls", "json", "tsv"}
MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200 MB

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "lumora-secret-key-change-me")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# ── In-memory job tracker ──────────────────────────────────────────────────────
# { session_id: {"status": "processing"|"done"|"error", "data": {...}, "error": "..."} }
JOBS: dict = {}
JOBS_LOCK = threading.Lock()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


# ── Background worker ──────────────────────────────────────────────────────────

def _process_job(session_id: str, saved_path: str, original_filename: str):
    """Run in a background thread. Heavy lifting: load → clean → analyse → persist."""
    try:
        logger.info(f"[job:{session_id}] Loading dataset from {saved_path}")
        raw_df = load_dataset(saved_path)
        logger.info(f"[job:{session_id}] Loaded shape: {raw_df.shape}")

        cleaned_df, clean_report = clean_dataset(raw_df)
        logger.info(f"[job:{session_id}] Cleaned shape: {cleaned_df.shape}")

        stats      = descriptive_stats(cleaned_df)
        uni_charts = univariate_charts(cleaned_df)
        bi_charts  = bivariate_charts(cleaned_df)
        insights   = extract_insights(cleaned_df, clean_report)
        logger.info(f"[job:{session_id}] Analysis complete")

        # Persist to disk so download endpoints can find it later
        session_path = os.path.join(OUTPUT_DIR, f"{session_id}.pkl")
        with open(session_path, "wb") as fh:
            pickle.dump({
                "df": cleaned_df,
                "clean_report": clean_report,
                "dataset_name": original_filename,
                "stats": stats,
                "uni_charts": uni_charts,
                "bi_charts": bi_charts,
                "insights": insights,
            }, fh)
        logger.info(f"[job:{session_id}] Session pickled")

        preview      = cleaned_df.head(10).fillna("").astype(str).to_dict(orient="records")
        preview_cols = list(cleaned_df.columns)

        result = {
            "session_id":   session_id,
            "dataset_name": original_filename,
            "clean_report": {
                "original_shape":      list(clean_report["original_shape"]),
                "cleaned_shape":       list(clean_report["cleaned_shape"]),
                "duplicates_removed":  clean_report["duplicates_removed"],
                "missing_values_filled": clean_report["missing_values_filled"],
            },
            "stats":        stats,
            "uni_charts":   uni_charts,
            "bi_charts":    bi_charts,
            "insights":     insights,
            "preview_cols": preview_cols,
            "preview_rows": preview,
        }

        with JOBS_LOCK:
            JOBS[session_id] = {"status": "done", "data": result}
        logger.info(f"[job:{session_id}] Done")

    except Exception as exc:
        logger.error(f"[job:{session_id}] Error: {exc}", exc_info=True)
        with JOBS_LOCK:
            JOBS[session_id] = {"status": "error", "error": str(exc)}
    finally:
        # Always clean up the uploaded file
        if os.path.exists(saved_path):
            os.remove(saved_path)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    """Accept the file, save it, kick off background processing, return immediately."""
    if "file" not in request.files:
        return jsonify({"error": "No file part in request."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type. Please upload CSV, XLSX, JSON, or TSV."}), 400

    session_id  = str(uuid.uuid4())
    ext         = file.filename.rsplit(".", 1)[1].lower()
    saved_path  = os.path.join(UPLOAD_DIR, f"{session_id}.{ext}")

    try:
        file.save(saved_path)
        logger.info(f"[upload] Saved to {saved_path}")
    except Exception as exc:
        logger.error(f"[upload] Save failed: {exc}")
        return jsonify({"error": f"Server could not save file: {str(exc)}"}), 500

    # Register job as "processing" before spawning thread
    with JOBS_LOCK:
        JOBS[session_id] = {"status": "processing"}

    # Spawn daemon thread — Flask/gunicorn stays responsive
    t = threading.Thread(
        target=_process_job,
        args=(session_id, saved_path, file.filename),
        daemon=True,
    )
    t.start()

    return jsonify({"session_id": session_id, "status": "processing"}), 202


@app.route("/api/status/<session_id>")
def status(session_id):
    """Poll endpoint — returns current job status."""
    with JOBS_LOCK:
        job = JOBS.get(session_id)

    if job is None:
        # Also check disk in case the server restarted (best-effort)
        session_path = os.path.join(OUTPUT_DIR, f"{session_id}.pkl")
        if os.path.exists(session_path):
            return jsonify({"status": "done"})
        return jsonify({"error": "Session not found."}), 404

    if job["status"] == "done":
        return jsonify({"status": "done", "data": job["data"]})
    elif job["status"] == "error":
        return jsonify({"status": "error", "error": job.get("error", "Unknown error")}), 500
    else:
        return jsonify({"status": "processing"})


@app.route("/api/download/cleaned/<session_id>/<fmt>")
def download_cleaned(session_id, fmt):
    session_path = os.path.join(OUTPUT_DIR, f"{session_id}.pkl")
    if not os.path.exists(session_path):
        return jsonify({"error": "Session not found or expired."}), 404

    fmt = fmt.lower()
    if fmt not in ("csv", "xlsx", "json"):
        return jsonify({"error": "Unsupported format."}), 400

    with open(session_path, "rb") as fh:
        data = pickle.load(fh)

    df        = data["df"]
    base_name = os.path.splitext(data["dataset_name"])[0]
    dl_name   = f"{base_name}_cleaned_by_lumora.{fmt}"

    if fmt == "csv":
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        return send_file(buf, mimetype="text/csv", as_attachment=True, download_name=dl_name)

    elif fmt == "json":
        buf = io.BytesIO(df.to_json(orient="records", indent=2).encode("utf-8"))
        buf.seek(0)
        return send_file(buf, mimetype="application/json", as_attachment=True, download_name=dl_name)

    else:  # xlsx
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=dl_name,
        )


@app.route("/api/download/report/<session_id>")
def download_report(session_id):
    session_path = os.path.join(OUTPUT_DIR, f"{session_id}.pkl")
    if not os.path.exists(session_path):
        return jsonify({"error": "Session not found or expired."}), 404

    with open(session_path, "rb") as fh:
        data = pickle.load(fh)

    buf = io.BytesIO()
    build_pdf_report(
        buf,
        data["dataset_name"],
        data["stats"],
        data["insights"],
        data["uni_charts"],
        data["bi_charts"],
    )
    buf.seek(0)

    base_name = os.path.splitext(data["dataset_name"])[0]
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{base_name}_Lumora_Report.pdf",
    )


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)

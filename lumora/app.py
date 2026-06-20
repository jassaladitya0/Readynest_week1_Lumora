"""
app.py — Lumora
Flask backend: upload any dataset (CSV/XLSX/JSON), auto-clean it, run EDA,
generate charts + insights, and let the user download either the cleaned
dataset (in any format) or a full PDF report.

Made by Aditya Jassal.
"""
import os
import io
import uuid
import pickle
from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context

from cleaning import load_dataset, clean_dataset, save_dataset
from analysis import descriptive_stats, univariate_charts, bivariate_charts, extract_insights
from report import build_pdf_report

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
ALLOWED_EXT = {"csv", "xlsx", "xls", "json", "tsv"}
MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200 MB — "any size" dataset support

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = "lumora-secret-key-change-me"
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# In-memory session store: session_id -> {df, clean_report, dataset_name}
SESSIONS = {}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file part in request."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type. Please upload CSV, XLSX, JSON, or TSV."}), 400

    session_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[1].lower()
    saved_path = os.path.join(UPLOAD_DIR, f"{session_id}.{ext}")
    file.save(saved_path)

    try:
        raw_df = load_dataset(saved_path)
        cleaned_df, clean_report = clean_dataset(raw_df)
    except Exception as e:
        return jsonify({"error": f"Failed to process file: {str(e)}"}), 500
    finally:
        if os.path.exists(saved_path):
            os.remove(saved_path)

    # Run analysis
    stats = descriptive_stats(cleaned_df)
    uni_charts = univariate_charts(cleaned_df)
    bi_charts = bivariate_charts(cleaned_df)
    insights = extract_insights(cleaned_df, clean_report)

    # Persist session data to disk (pickle) keyed by session_id
    session_path = os.path.join(OUTPUT_DIR, f"{session_id}.pkl")
    with open(session_path, "wb") as f:
        pickle.dump({
            "df": cleaned_df,
            "clean_report": clean_report,
            "dataset_name": file.filename,
            "stats": stats,
            "uni_charts": uni_charts,
            "bi_charts": bi_charts,
            "insights": insights,
        }, f)

    preview = cleaned_df.head(10).fillna("").astype(str).to_dict(orient="records")
    preview_cols = list(cleaned_df.columns)

    return jsonify({
        "session_id": session_id,
        "dataset_name": file.filename,
        "clean_report": {
            "original_shape": clean_report["original_shape"],
            "cleaned_shape": clean_report["cleaned_shape"],
            "duplicates_removed": clean_report["duplicates_removed"],
            "missing_values_filled": clean_report["missing_values_filled"],
        },
        "stats": stats,
        "uni_charts": uni_charts,
        "bi_charts": bi_charts,
        "insights": insights,
        "preview_cols": preview_cols,
        "preview_rows": preview,
    })


@app.route("/api/download/cleaned/<session_id>/<fmt>")
def download_cleaned(session_id, fmt):
    session_path = os.path.join(OUTPUT_DIR, f"{session_id}.pkl")
    if not os.path.exists(session_path):
        return jsonify({"error": "Session not found or expired."}), 404

    fmt = fmt.lower()
    if fmt not in ("csv", "xlsx", "json"):
        return jsonify({"error": "Unsupported format."}), 400

    # Load only df + dataset_name — skip heavy chart data
    with open(session_path, "rb") as f:
        data = pickle.load(f)

    df = data["df"]
    base_name = os.path.splitext(data["dataset_name"])[0]
    download_name = f"{base_name}_cleaned_by_lumora.{fmt}"

    if fmt == "csv":
        # Stream CSV directly from memory — no disk write
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        return send_file(
            buf,
            mimetype="text/csv",
            as_attachment=True,
            download_name=download_name,
        )

    elif fmt == "json":
        # Stream JSON directly from memory
        buf = io.BytesIO(df.to_json(orient="records", indent=2).encode("utf-8"))
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/json",
            as_attachment=True,
            download_name=download_name,
        )

    else:  # xlsx
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=download_name,
        )


@app.route("/api/download/report/<session_id>")
def download_report(session_id):
    session_path = os.path.join(OUTPUT_DIR, f"{session_id}.pkl")
    if not os.path.exists(session_path):
        return jsonify({"error": "Session not found or expired."}), 404

    with open(session_path, "rb") as f:
        data = pickle.load(f)

    # Build PDF into memory — no temp file needed
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

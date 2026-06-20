---
title: Lumora
emoji: 💡
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# LUMORA — Illuminate Your Data

A web app that takes any dataset (CSV, XLSX, JSON, TSV — any size), automatically
cleans it, performs full exploratory data analysis, builds an interactive dashboard,
and lets you download either the **cleaned dataset** (in any format) or a complete
**PDF analysis report**.

Made by **Aditya Jassal**.

---

## Features

- **Upload any format**: CSV, XLSX, XLS, JSON, TSV — drag & drop or browse
- **Large dataset support**: Handles millions of rows via chunked loading & smart 300k-row sampling
- **Auto data cleaning**:
  - Drops empty rows/columns
  - Standardizes column names, trims whitespace
  - Auto-detects numbers/dates stored as text
  - Fills missing values (median for numeric, mode for categorical)
  - Removes duplicate rows
- **Descriptive statistics**: mean, median, std dev, count, missing values, etc.
- **Univariate analysis**: histograms + box plots (numeric), bar charts (categorical)
- **Bivariate analysis**: correlation heatmap, strongest-pair scatter plot, category share pie chart, time-series line chart
- **Auto-extracted insights**: plain-English bullet points (correlations, skew, dominant categories, cleaning summary)
- **Interactive dashboard**: all charts + stats rendered live in the browser
- **Download cleaned dataset**: as CSV, XLSX, or JSON — streamed instantly (no disk write delay)
- **Download full report**: as a polished multi-page PDF — streamed instantly

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Analysis | pandas, NumPy |
| Charts | Matplotlib, Seaborn |
| PDF Report | ReportLab |
| Frontend | HTML, Vanilla CSS, JavaScript |
| Deployment | Docker, Gunicorn |

---

## Local Setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd lumora/lumora

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Then open **http://localhost:5000** in your browser.

---

## Project Structure

```
lumora/
├── app.py              # Flask routes (upload, download cleaned data, download report)
├── cleaning.py         # Dataset loading + auto-cleaning logic (chunked for large files)
├── analysis.py         # Stats, parallel chart generation, insight extraction
├── report.py           # PDF report builder (ReportLab)
├── requirements.txt
├── templates/
│   └── index.html      # Single-page UI
├── static/
│   ├── css/style.css
│   ├── js/script.js
│   └── img/logo.svg    # Lumora logo
├── uploads/            # Temp storage (auto-cleared after processing)
└── outputs/            # Session cache (.pkl files — gitignored)
```

---

## Performance Notes

- **Large CSVs (>500k rows)**: Reads in 200k-row chunks, caps at 300k rows for analysis
- **Charts**: Always sampled to ≤50k rows before rendering — stays fast even on huge datasets
- **Parallel chart generation**: Uses 4 worker threads — up to 4x faster chart output
- **Downloads**: All files streamed from memory (BytesIO) — no disk write bottleneck
- Max upload size: **200 MB** (set `MAX_CONTENT_LENGTH` in `app.py` to increase)

---

## Deployment

Deployed on **Hugging Face Spaces** via Docker.
Also deployable on **Render** using `render.yaml`.

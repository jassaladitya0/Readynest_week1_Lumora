# LUMORA — Illuminate Your Data

A web app that takes any dataset (CSV, XLSX, JSON, TSV — any size), automatically
cleans it, performs full exploratory data analysis, builds an interactive dashboard,
and lets you download either the **cleaned dataset** (in any format) or a complete
**PDF analysis report**.

Made by **Aditya Jassal**.

## Features

- **Upload any format**: CSV, XLSX, XLS, JSON, TSV — drag & drop or browse.
- **Auto data cleaning**:
  - Drops empty rows/columns
  - Standardizes column names, trims whitespace
  - Auto-detects numbers/dates stored as text
  - Fills missing values (median for numeric, mode for categorical)
  - Removes duplicate rows
- **Descriptive statistics**: mean, median, std dev, count, missing values, etc.
- **Univariate analysis**: histograms + box plots (numeric), bar charts (categorical)
- **Bivariate analysis**: correlation heatmap, strongest-pair scatter plot,
  category share pie chart, time-series line chart (when a date column exists)
- **Auto-extracted insights**: plain-English bullet points (correlations, skew,
  dominant categories, cleaning summary)
- **Interactive dashboard**: all charts + stats rendered live in the browser
- **Download cleaned dataset**: as CSV, XLSX, or JSON
- **Download full report**: as a polished multi-page PDF

## Tech Stack

- **Backend**: Python, Flask
- **Analysis**: pandas, NumPy
- **Charts**: Matplotlib, Seaborn
- **PDF report**: ReportLab
- **Frontend**: HTML, CSS, JavaScript (vanilla, no framework)

## Setup

```bash
cd lumora
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000** in your browser.

## Project Structure

```
lumora/
├── app.py              # Flask routes (upload, download cleaned data, download report)
├── cleaning.py          # Dataset loading + auto-cleaning logic
├── analysis.py          # Stats, chart generation, insight extraction
├── report.py            # PDF report builder (ReportLab)
├── requirements.txt
├── templates/
│   └── index.html       # Single-page UI
├── static/
│   ├── css/style.css
│   ├── js/script.js
│   └── img/logo.svg     # Lumora logo
├── uploads/              # temp storage (auto-cleared after processing)
└── outputs/              # generated cleaned files + PDF reports
```

## Notes

- Max upload size is set to 200 MB (`MAX_CONTENT_LENGTH` in `app.py`) — raise it
  if you need to handle larger files.
- Each upload gets a unique session ID; cleaned data + analysis are cached on
  disk (`outputs/<session_id>.pkl`) so report/download requests don't need to
  reprocess the file.
- For production use, swap the Flask dev server for Gunicorn/Waitress and add
  a periodic cleanup job for old files in `uploads/` and `outputs/`.

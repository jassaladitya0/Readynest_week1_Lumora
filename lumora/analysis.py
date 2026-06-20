"""
analysis.py — Lumora
Generates descriptive statistics, univariate/bivariate charts, and auto-extracted
insights from a cleaned DataFrame. Charts are returned as base64 PNG strings so they
can be embedded directly into the dashboard HTML and the PDF report.

Performance: All chart functions automatically sample the DataFrame to MAX_PLOT_ROWS
before rendering so even 300k-row datasets produce charts in seconds.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import io
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed

sns.set_theme(style="whitegrid")
PALETTE = ["#7C3AED", "#22D3EE", "#F472B6", "#34D399", "#FBBF24", "#60A5FA"]

# ─── Sampling cap for chart rendering ─────────────────────────────────────────
MAX_PLOT_ROWS = 50_000   # never plot more than 50k points — keeps charts fast


def _sample(df: pd.DataFrame, n: int = MAX_PLOT_ROWS) -> pd.DataFrame:
    """Return a random sample of df if it exceeds n rows."""
    if len(df) > n:
        return df.sample(n=n, random_state=42)
    return df


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=96)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


# ─── Stats ────────────────────────────────────────────────────────────────────

def descriptive_stats(df: pd.DataFrame) -> dict:
    numeric_df = df.select_dtypes(include=np.number)
    stats = {}

    if not numeric_df.empty:
        desc = numeric_df.describe().T
        desc["missing"] = df[numeric_df.columns].isna().sum()
        stats["numeric"] = (
            desc.round(2)
            .reset_index()
            .rename(columns={"index": "column"})
            .to_dict(orient="records")
        )
    else:
        stats["numeric"] = []

    cat_df = df.select_dtypes(include=["object", "category", "bool"])
    cat_summary = []
    for col in cat_df.columns:
        vc = df[col].value_counts()
        cat_summary.append({
            "column": col,
            "unique": int(df[col].nunique()),
            "top": str(vc.index[0]) if len(vc) else "N/A",
            "freq": int(vc.iloc[0]) if len(vc) else 0,
        })
    stats["categorical"] = cat_summary
    stats["row_count"] = int(len(df))
    stats["col_count"] = int(len(df.columns))
    return stats


# ─── Chart helpers ────────────────────────────────────────────────────────────

def _numeric_chart(col: str, series: pd.Series) -> dict:
    """Histogram + boxplot for one numeric column."""
    data = series.dropna()
    fig, axes = plt.subplots(1, 2, figsize=(8, 3))
    sns.histplot(data, kde=True, color=PALETTE[0], ax=axes[0], bins=min(60, len(data) // 10 or 10))
    axes[0].set_title(f"Histogram: {col}")
    sns.boxplot(x=data, color=PALETTE[1], ax=axes[1])
    axes[1].set_title(f"Box Plot: {col}")
    fig.tight_layout()
    return {"title": f"Distribution of {col}", "img": _fig_to_base64(fig), "type": "univariate-numeric"}


def _cat_chart(col: str, series: pd.Series) -> dict:
    """Bar chart for top categories of one categorical column."""
    vc = series.value_counts().head(8)
    n = len(vc)
    # Cycle palette to exactly match bar count — avoids seaborn warning
    colors_for_bars = (PALETTE * ((n // len(PALETTE)) + 1))[:n]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    sns.barplot(x=vc.values, y=vc.index.astype(str), hue=vc.index.astype(str),
                palette=colors_for_bars, legend=False, ax=ax)
    ax.set_title(f"Top categories: {col}")
    fig.tight_layout()
    return {"title": f"Top values of {col}", "img": _fig_to_base64(fig), "type": "univariate-categorical"}


# ─── Public analysis functions ────────────────────────────────────────────────

def univariate_charts(df: pd.DataFrame, max_cols: int = 6) -> list[dict]:
    """Generate univariate charts in parallel using a thread pool."""
    plot_df = _sample(df)  # sample once before spawning threads

    numeric_cols = list(plot_df.select_dtypes(include=np.number).columns)[:max_cols]
    cat_cols = list(plot_df.select_dtypes(include=["object", "category", "bool"]).columns)[:max_cols]

    tasks = []
    results_map = {}

    with ThreadPoolExecutor(max_workers=4) as pool:
        for col in numeric_cols:
            fut = pool.submit(_numeric_chart, col, plot_df[col])
            tasks.append((col, fut, "num"))
        for col in cat_cols:
            try:
                converted_dt = pd.to_datetime(plot_df[col], errors="coerce", format="mixed")
                non_null = plot_df[col].notna().sum()
                if non_null > 0 and converted_dt.notna().sum() >= 0.8 * non_null:
                    continue
            except Exception:
                pass
            fut = pool.submit(_cat_chart, col, plot_df[col])
            tasks.append((col, fut, "cat"))

        for col, fut, kind in tasks:
            try:
                results_map[(col, kind)] = fut.result()
            except Exception:
                pass   # skip failed charts silently

    charts = []
    for col in numeric_cols:
        if (col, "num") in results_map:
            charts.append(results_map[(col, "num")])
    for col in cat_cols:
        if (col, "cat") in results_map:
            charts.append(results_map[(col, "cat")])

    return charts


def bivariate_charts(df: pd.DataFrame) -> list[dict]:
    """Correlation heatmap, scatter of strongest pair, pie chart, and time-series line."""
    plot_df = _sample(df)
    numeric_df = plot_df.select_dtypes(include=np.number)
    charts = []

    # Correlation heatmap
    if numeric_df.shape[1] >= 2:
        corr = numeric_df.corr(numeric_only=True)
        fig, ax = plt.subplots(figsize=(6, 5))
        sns.heatmap(corr, annot=True, fmt=".2f", cmap="mako", ax=ax)
        ax.set_title("Correlation Heatmap")
        fig.tight_layout()
        charts.append({"title": "Correlation Heatmap", "img": _fig_to_base64(fig), "type": "bivariate-heatmap"})

        # Strongest-pair scatter (sample to 10k for speed)
        scatter_df = _sample(plot_df, n=10_000)
        corr_abs = corr.abs()
        np.fill_diagonal(corr_abs.values, 0)
        if corr_abs.values.max() > 0:
            idx = np.unravel_index(np.argmax(corr_abs.values), corr_abs.shape)
            c1, c2 = corr.columns[idx[0]], corr.columns[idx[1]]
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.scatter(scatter_df[c1], scatter_df[c2],
                       alpha=0.4, s=8, color=PALETTE[2])
            ax.set_xlabel(c1)
            ax.set_ylabel(c2)
            ax.set_title(f"Scatter: {c1} vs {c2}")
            fig.tight_layout()
            charts.append({"title": f"{c1} vs {c2}", "img": _fig_to_base64(fig), "type": "bivariate-scatter"})

    # Categorical pie chart
    cat_cols = df.select_dtypes(include=["object", "category", "bool"]).columns
    if len(cat_cols) > 0:
        col = cat_cols[0]
        vc = df[col].value_counts().head(6)
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.pie(vc.values, labels=vc.index.astype(str), autopct="%1.1f%%", colors=PALETTE)
        ax.set_title(f"Share of {col}")
        fig.tight_layout()
        charts.append({"title": f"Distribution share — {col}", "img": _fig_to_base64(fig), "type": "bivariate-pie"})

    # Time-series line (downsample to 5k points for smooth render)
    dt_cols = df.select_dtypes(include="datetime64[ns]").columns
    if len(dt_cols) > 0 and numeric_df.shape[1] >= 1:
        dcol = dt_cols[0]
        ncol = numeric_df.columns[0]
        line_df = df[[dcol, ncol]].dropna().sort_values(dcol)
        if len(line_df) > 1:
            if len(line_df) > 5_000:
                # Resample to ~5k evenly-spaced points
                step = max(1, len(line_df) // 5_000)
                line_df = line_df.iloc[::step]
            fig, ax = plt.subplots(figsize=(7, 3.5))
            ax.plot(line_df[dcol], line_df[ncol], color=PALETTE[3], linewidth=0.8)
            ax.set_title(f"{ncol} over time ({dcol})")
            fig.autofmt_xdate()
            fig.tight_layout()
            charts.append({"title": f"{ncol} trend over {dcol}", "img": _fig_to_base64(fig), "type": "bivariate-line"})

    return charts


def extract_insights(df: pd.DataFrame, clean_report: dict) -> list[str]:
    insights = []
    numeric_df = df.select_dtypes(include=np.number)

    insights.append(
        f"Dataset contains {clean_report['cleaned_shape'][0]:,} rows and "
        f"{clean_report['cleaned_shape'][1]} columns after cleaning "
        f"(started at {clean_report['original_shape'][0]:,} rows)."
    )

    if clean_report.get("duplicates_removed", 0) > 0:
        insights.append(f"Removed {clean_report['duplicates_removed']:,} duplicate rows during cleaning.")

    if clean_report.get("missing_values_filled"):
        n_cols_fixed = len(clean_report["missing_values_filled"])
        insights.append(f"Filled missing values in {n_cols_fixed} column(s) using median/mode imputation.")

    if numeric_df.shape[1] >= 2:
        corr = numeric_df.corr(numeric_only=True)
        corr_abs = corr.abs()
        np.fill_diagonal(corr_abs.values, 0)
        if corr_abs.values.max() > 0:
            idx = np.unravel_index(np.argmax(corr_abs.values), corr_abs.shape)
            c1, c2 = corr.columns[idx[0]], corr.columns[idx[1]]
            val = corr.loc[c1, c2]
            direction = "positive" if val > 0 else "negative"
            insights.append(
                f"Strongest relationship: '{c1}' and '{c2}' show a {direction} "
                f"correlation of {val:.2f}."
            )

    for col in numeric_df.columns[:5]:
        skew = numeric_df[col].skew()
        if abs(skew) > 1:
            direction = "right" if skew > 0 else "left"
            insights.append(
                f"Column '{col}' is heavily skewed to the {direction} "
                f"(skew={skew:.2f}) — consider a log transform."
            )

    cat_cols = df.select_dtypes(include=["object", "category", "bool"]).columns
    for col in cat_cols[:3]:
        vc = df[col].value_counts(normalize=True)
        if len(vc) > 0 and vc.iloc[0] > 0.6:
            insights.append(
                f"'{col}' is dominated by a single value "
                f"('{vc.index[0]}') at {vc.iloc[0]*100:.1f}% of records."
            )

    if len(insights) < 3:
        insights.append("Dataset is fairly clean and balanced — no major anomalies detected.")

    return insights[:8]

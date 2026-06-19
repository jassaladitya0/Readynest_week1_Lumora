"""
analysis.py — Lumora
Generates descriptive statistics, univariate/bivariate charts, and auto-extracted
insights from a cleaned DataFrame. Charts are returned as base64 PNG strings so they
can be embedded directly into the dashboard HTML and the PDF report.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import io
import base64

sns.set_theme(style="whitegrid")
PALETTE = ["#7C3AED", "#22D3EE", "#F472B6", "#34D399", "#FBBF24", "#60A5FA"]


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def descriptive_stats(df: pd.DataFrame) -> dict:
    numeric_df = df.select_dtypes(include=np.number)
    stats = {}
    if not numeric_df.empty:
        desc = numeric_df.describe().T
        desc["missing"] = df[numeric_df.columns].isna().sum()
        stats["numeric"] = desc.round(2).reset_index().rename(columns={"index": "column"}).to_dict(orient="records")
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


def univariate_charts(df: pd.DataFrame, max_cols: int = 6) -> list[dict]:
    charts = []
    numeric_cols = list(df.select_dtypes(include=np.number).columns)[:max_cols]
    cat_cols = list(df.select_dtypes(include=["object", "category", "bool"]).columns)[:max_cols]

    for col in numeric_cols:
        fig, axes = plt.subplots(1, 2, figsize=(8, 3))
        sns.histplot(df[col].dropna(), kde=True, color=PALETTE[0], ax=axes[0])
        axes[0].set_title(f"Histogram: {col}")
        sns.boxplot(x=df[col].dropna(), color=PALETTE[1], ax=axes[1])
        axes[1].set_title(f"Box Plot: {col}")
        fig.tight_layout()
        charts.append({"title": f"Distribution of {col}", "img": _fig_to_base64(fig), "type": "univariate-numeric"})

    for col in cat_cols:
        vc = df[col].value_counts().head(8)
        fig, ax = plt.subplots(figsize=(6, 3.5))
        sns.barplot(x=vc.values, y=vc.index.astype(str), hue=vc.index.astype(str),
                    palette=PALETTE, legend=False, ax=ax)
        ax.set_title(f"Top categories: {col}")
        fig.tight_layout()
        charts.append({"title": f"Top values of {col}", "img": _fig_to_base64(fig), "type": "univariate-categorical"})

    return charts


def bivariate_charts(df: pd.DataFrame) -> list[dict]:
    charts = []
    numeric_df = df.select_dtypes(include=np.number)

    if numeric_df.shape[1] >= 2:
        fig, ax = plt.subplots(figsize=(6, 5))
        corr = numeric_df.corr(numeric_only=True)
        sns.heatmap(corr, annot=True, fmt=".2f", cmap="mako", ax=ax)
        ax.set_title("Correlation Heatmap")
        fig.tight_layout()
        charts.append({"title": "Correlation Heatmap", "img": _fig_to_base64(fig), "type": "bivariate-heatmap"})

        # strongest pair scatter
        corr_abs = corr.abs()
        np.fill_diagonal(corr_abs.values, 0)
        if corr_abs.values.max() > 0:
            idx = np.unravel_index(np.argmax(corr_abs.values), corr_abs.shape)
            c1, c2 = corr.columns[idx[0]], corr.columns[idx[1]]
            fig, ax = plt.subplots(figsize=(6, 4))
            sns.scatterplot(x=df[c1], y=df[c2], color=PALETTE[2], ax=ax)
            ax.set_title(f"Scatter: {c1} vs {c2}")
            fig.tight_layout()
            charts.append({"title": f"{c1} vs {c2}", "img": _fig_to_base64(fig), "type": "bivariate-scatter"})

    # categorical pie chart
    cat_cols = df.select_dtypes(include=["object", "category", "bool"]).columns
    if len(cat_cols) > 0:
        col = cat_cols[0]
        vc = df[col].value_counts().head(6)
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.pie(vc.values, labels=vc.index.astype(str), autopct="%1.1f%%", colors=PALETTE)
        ax.set_title(f"Share of {col}")
        fig.tight_layout()
        charts.append({"title": f"Distribution share — {col}", "img": _fig_to_base64(fig), "type": "bivariate-pie"})

    # line chart if a datetime column + numeric exists
    dt_cols = df.select_dtypes(include="datetime64[ns]").columns
    if len(dt_cols) > 0 and numeric_df.shape[1] >= 1:
        dcol = dt_cols[0]
        ncol = numeric_df.columns[0]
        line_df = df[[dcol, ncol]].dropna().sort_values(dcol)
        if len(line_df) > 1:
            fig, ax = plt.subplots(figsize=(7, 3.5))
            ax.plot(line_df[dcol], line_df[ncol], color=PALETTE[3])
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
            insights.append(f"Strongest relationship found: '{c1}' and '{c2}' show a {direction} correlation of {val:.2f}.")

    for col in numeric_df.columns[:5]:
        skew = numeric_df[col].skew()
        if abs(skew) > 1:
            direction = "right" if skew > 0 else "left"
            insights.append(f"Column '{col}' is heavily skewed to the {direction} (skew={skew:.2f}) — consider a log transform.")

    cat_cols = df.select_dtypes(include=["object", "category", "bool"]).columns
    for col in cat_cols[:3]:
        vc = df[col].value_counts(normalize=True)
        if len(vc) > 0 and vc.iloc[0] > 0.6:
            insights.append(f"'{col}' is dominated by a single value ('{vc.index[0]}') at {vc.iloc[0]*100:.1f}% of records.")

    if len(insights) < 3:
        insights.append("Dataset is fairly clean and balanced — no major anomalies detected.")

    return insights[:8]

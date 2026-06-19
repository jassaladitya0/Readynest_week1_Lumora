"""
cleaning.py — Lumora
Handles automatic loading and cleaning of CSV / Excel / JSON datasets of any size.
"""
import pandas as pd
import numpy as np
import os


def load_dataset(filepath: str) -> pd.DataFrame:
    """Load a dataset from CSV, XLSX/XLS, or JSON into a DataFrame."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".csv":
        try:
            df = pd.read_csv(filepath, encoding="utf-8", low_memory=False)
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding="latin1", low_memory=False)
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(filepath)
    elif ext == ".json":
        df = pd.read_json(filepath)
    elif ext == ".tsv":
        df = pd.read_csv(filepath, sep="\t", low_memory=False)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    return df


def clean_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Auto-clean a DataFrame:
      - drop fully empty rows/columns
      - standardize column names
      - trim whitespace in text fields
      - fix obvious dtype issues
      - fill missing values (median for numeric, mode/"Unknown" for categorical)
      - remove duplicate rows
    Returns (cleaned_df, report_dict) where report_dict logs what was done.
    """
    report = {}
    original_shape = df.shape

    # 1. Standardize column names
    df.columns = [str(c).strip().replace("\n", " ") for c in df.columns]

    # 2. Drop fully empty rows/columns
    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")

    # 3. Trim whitespace in object/text columns
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": np.nan, "None": np.nan, "": np.nan, "NaT": np.nan})

    # 4. Try to auto-convert object columns that are actually numeric or dates
    for col in df.select_dtypes(include="object").columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().sum() >= 0.8 * df[col].notna().sum() and df[col].notna().sum() > 0:
            df[col] = converted
            continue
        try:
            converted_dt = pd.to_datetime(df[col], errors="coerce")
            if converted_dt.notna().sum() >= 0.8 * df[col].notna().sum() and df[col].notna().sum() > 0:
                df[col] = converted_dt
        except Exception:
            pass

    # 5. Missing value report (before fill)
    missing_before = df.isna().sum()
    report["missing_values_filled"] = {}

    # 6. Fill missing values
    for col in df.columns:
        n_missing = df[col].isna().sum()
        if n_missing == 0:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            fill_val = df[col].median()
            df[col] = df[col].fillna(fill_val)
            report["missing_values_filled"][col] = f"{n_missing} filled with median ({round(fill_val, 2) if pd.notna(fill_val) else 'N/A'})"
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].fillna(method="ffill")
            report["missing_values_filled"][col] = f"{n_missing} filled (forward-fill)"
        else:
            mode_vals = df[col].mode()
            fill_val = mode_vals[0] if len(mode_vals) > 0 else "Unknown"
            df[col] = df[col].fillna(fill_val)
            report["missing_values_filled"][col] = f"{n_missing} filled with mode ('{fill_val}')"

    # 7. Remove duplicate rows
    dup_count = df.duplicated().sum()
    df = df.drop_duplicates()

    report["original_shape"] = original_shape
    report["cleaned_shape"] = df.shape
    report["duplicates_removed"] = int(dup_count)
    report["columns"] = list(df.columns)
    report["dtypes"] = {c: str(t) for c, t in df.dtypes.items()}

    return df, report


def save_dataset(df: pd.DataFrame, filepath: str, fmt: str):
    """Save a DataFrame to csv / xlsx / json based on fmt."""
    fmt = fmt.lower()
    if fmt == "csv":
        df.to_csv(filepath, index=False)
    elif fmt == "xlsx":
        df.to_excel(filepath, index=False)
    elif fmt == "json":
        df.to_json(filepath, orient="records", indent=2)
    else:
        raise ValueError(f"Unsupported export format: {fmt}")

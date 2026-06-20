"""
cleaning.py — Lumora
Handles automatic loading and cleaning of CSV / Excel / JSON datasets of any size.
Optimized for large datasets (millions of rows) with chunked reading and smart sampling.
"""
import pandas as pd
import numpy as np
import os

# ─── Thresholds ────────────────────────────────────────────────────────────────
# If a CSV has more rows than this, we stream-read in chunks for cleaning,
# then work on a smart sample for expensive per-cell operations.
LARGE_ROW_THRESHOLD = 500_000   # 500k rows → switch to fast-path
SAMPLE_SIZE = 300_000           # max rows kept for cleaning/analysis pass


def load_dataset(filepath: str) -> pd.DataFrame:
    """Load a dataset from CSV, XLSX/XLS, JSON, or TSV into a DataFrame.
    For large CSVs we use chunked reading with optimized dtypes to minimize RAM."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext in (".csv", ".tsv"):
        sep = "\t" if ext == ".tsv" else ","
        # Quick row-count probe (count newlines without loading data)
        try:
            with open(filepath, "rb") as fh:
                n_rows = sum(1 for _ in fh) - 1  # subtract header
        except Exception:
            n_rows = 0

        encoding = "utf-8"
        # Try reading with utf-8 first; fall back to latin1
        try:
            if n_rows > LARGE_ROW_THRESHOLD:
                # Chunked read — combine chunks, then sample if still huge
                chunks = []
                reader = pd.read_csv(
                    filepath, sep=sep, encoding=encoding,
                    low_memory=True, chunksize=200_000,
                    on_bad_lines="skip"
                )
                total_read = 0
                for chunk in reader:
                    chunks.append(chunk)
                    total_read += len(chunk)
                    if total_read >= SAMPLE_SIZE:
                        break          # stop early — we have enough
                df = pd.concat(chunks, ignore_index=True)
            else:
                df = pd.read_csv(filepath, sep=sep, encoding=encoding,
                                 low_memory=False, on_bad_lines="skip")
        except UnicodeDecodeError:
            encoding = "latin1"
            if n_rows > LARGE_ROW_THRESHOLD:
                chunks = []
                reader = pd.read_csv(
                    filepath, sep=sep, encoding=encoding,
                    low_memory=True, chunksize=200_000,
                    on_bad_lines="skip"
                )
                total_read = 0
                for chunk in reader:
                    chunks.append(chunk)
                    total_read += len(chunk)
                    if total_read >= SAMPLE_SIZE:
                        break
                df = pd.concat(chunks, ignore_index=True)
            else:
                df = pd.read_csv(filepath, sep=sep, encoding=encoding,
                                 low_memory=False, on_bad_lines="skip")

    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(filepath)

    elif ext == ".json":
        try:
            df = pd.read_json(filepath)
        except ValueError:
            df = pd.read_json(filepath, lines=True)   # newline-delimited JSON

    else:
        raise ValueError(f"Unsupported file type: {ext}")

    # If still very large after load, take a stratified-ish sample
    if len(df) > SAMPLE_SIZE:
        df = df.sample(n=SAMPLE_SIZE, random_state=42).reset_index(drop=True)

    return df


def clean_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Auto-clean a DataFrame:
      - drop fully empty rows/columns
      - standardize column names
      - trim whitespace in text fields
      - fix obvious dtype issues (numeric / datetime auto-conversion)
      - fill missing values (median for numeric, mode/"Unknown" for categorical)
      - remove duplicate rows
    Returns (cleaned_df, report_dict) where report_dict logs what was done.

    Performance notes:
      - Object columns are converted with pd.to_numeric / pd.to_datetime
        only when ≥ 80 % of non-null values can be parsed (avoids slow loops).
      - fillna uses vectorised ops throughout.
    """
    report = {}
    original_shape = df.shape

    # 1. Standardize column names
    df.columns = [str(c).strip().replace("\n", " ") for c in df.columns]

    # 2. Drop fully empty rows/columns
    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")

    # 3. Trim whitespace in object/text columns (vectorised)
    obj_cols = df.select_dtypes(include="object").columns
    if len(obj_cols):
        df[obj_cols] = df[obj_cols].apply(lambda s: s.str.strip())
        df[obj_cols] = df[obj_cols].replace(
            {"nan": np.nan, "None": np.nan, "": np.nan, "NaT": np.nan}
        )

    # 4. Auto-convert object columns that are actually numeric or dates
    for col in list(df.select_dtypes(include="object").columns):
        non_null = df[col].notna().sum()
        if non_null == 0:
            continue
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().sum() >= 0.8 * non_null:
            df[col] = converted
            continue
        try:
            converted_dt = pd.to_datetime(df[col], errors="coerce", format="mixed")
            if converted_dt.notna().sum() >= 0.8 * non_null:
                df[col] = converted_dt
        except Exception:
            pass

    # 5. Missing value report (before fill)
    report["missing_values_filled"] = {}

    # 6. Fill missing values (vectorised per-column)
    for col in df.columns:
        n_missing = int(df[col].isna().sum())
        if n_missing == 0:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            fill_val = df[col].median()
            df[col] = df[col].fillna(fill_val)
            report["missing_values_filled"][col] = (
                f"{n_missing} filled with median "
                f"({round(fill_val, 2) if pd.notna(fill_val) else 'N/A'})"
            )
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].ffill()
            report["missing_values_filled"][col] = f"{n_missing} filled (forward-fill)"
        else:
            mode_vals = df[col].mode()
            fill_val = mode_vals.iloc[0] if len(mode_vals) > 0 else "Unknown"
            df[col] = df[col].fillna(fill_val)
            report["missing_values_filled"][col] = (
                f"{n_missing} filled with mode ('{fill_val}')"
            )

    # 7. Remove duplicate rows
    dup_count = int(df.duplicated().sum())
    df = df.drop_duplicates().reset_index(drop=True)

    report["original_shape"] = original_shape
    report["cleaned_shape"] = df.shape
    report["duplicates_removed"] = dup_count
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

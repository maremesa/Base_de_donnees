from pathlib import Path
from datetime import date, datetime

import pandas as pd
import psycopg2


"""
Import clinical metadata into the BHRe PostgreSQL database.

This script reads an Excel metadata file, standardizes its column names,
cleans text, numeric and date values, then replaces the content of the
`clinical_data` table with the cleaned records.

Main steps
----------
1. Read the Excel file defined by `EXCEL_PATH`.
2. Normalize column names.
3. Validate that all expected columns are present.
4. Clean dates, integers and text fields.
5. Truncate the PostgreSQL `clinical_data` table.
6. Insert all cleaned rows.
7. Create useful indexes for querying by `glims` and `sample_id`.

Author
------
Mareme SARR
"""


DB_CONFIG = {
    "dbname": "bd_bhre",
    "user": "msarr",
    "host": "localhost",
    "port": 55432,
}

EXCEL_PATH = "/data/msarr/metadata.xlsx"


def to_date(series: pd.Series) -> pd.Series:
    """
    Convert a pandas Series to Python date objects.

    Invalid or missing values are converted to NaT first, then to null-like
    date values compatible with PostgreSQL insertion.

    Parameters
    ----------
    series : pandas.Series
        Input column containing dates or date-like values.

    Returns
    -------
    pandas.Series
        Series containing Python `date` objects or missing values.
    """
    return pd.to_datetime(series, errors="coerce").dt.date


def clean_text(value):
    """
    Clean a text value before database insertion.

    Missing values are converted to None. Non-empty values are converted to
    strings and stripped of leading and trailing spaces.

    Parameters
    ----------
    value : Any
        Input value to clean.

    Returns
    -------
    str | None
        Cleaned string, or None if the value is missing or empty.
    """
    if pd.isna(value):
        return None

    text = str(value).strip()
    return text if text else None


def clean_scalar(value):
    """
    Clean a scalar value for PostgreSQL insertion.

    This function converts pandas missing values to None and converts pandas
    or Python datetime values to Python date objects. Other values are
    returned unchanged.

    Parameters
    ----------
    value : Any
        Input scalar value.

    Returns
    -------
    Any
        Cleaned scalar value suitable for database insertion.
    """
    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.date()

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return value


def main():
    """
    Run the clinical metadata import workflow.

    The function loads the Excel metadata file, validates the expected schema,
    cleans the dataframe and inserts the records into the PostgreSQL
    `clinical_data` table.

    Raises
    ------
    FileNotFoundError
        If the Excel metadata file does not exist.

    ValueError
        If one or more expected columns are missing from the Excel file.

    psycopg2.Error
        If an error occurs during the PostgreSQL transaction.
    """
    path = Path(EXCEL_PATH)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Read metadata from Excel.
    df = pd.read_excel(path)

    # Standardize column names to match the PostgreSQL table schema.
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
    )

    # Remove automatically generated unnamed column if present.
    df = df.drop(columns=["unnamed:_34"], errors="ignore")

    expected_cols = [
        "sample_id",
        "ordre_chronologique",
        "cluster_id",
        "flag_epitrack",
        "flag_uhe",
        "valid_genom",
        "glims",
        "ipp",
        "date_prelevement",
        "species",
        "type_prelevement",
        "bmr_bhre",
        "mlst_species",
        "identification",
        "transplanting_date",
        "isolation_media_1",
        "isolation_media_2",
        "extraction_date",
        "extraction_statut",
        "quantification",
        "seq_illumina_date",
        "illumina_statut",
        "seq_nanopore_date",
        "seq_nanopore_batch",
        "seq_nanopore_batch_bis",
        "seq_nanopore_date_bis",
        "seq_nanopore_batch_ter",
        "seq_nanopore_date_ter",
        "nanopore_statut",
        "station_ngs",
        "assemblage",
        "annotation",
        "rendu",
        "cluster_rendu",
    ]

    missing = [col for col in expected_cols if col not in df.columns]

    if missing:
        raise ValueError(f"Missing columns in Excel file: {missing}")

    # Keep only the expected columns and preserve their target order.
    df = df[expected_cols].copy()

    # Convert integer-like columns.
    int_cols = ["ordre_chronologique"]

    for col in int_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Convert date columns.
    date_cols = [
        "date_prelevement",
        "transplanting_date",
        "extraction_date",
        "seq_illumina_date",
        "seq_nanopore_date",
        "seq_nanopore_date_bis",
        "seq_nanopore_date_ter",
    ]

    for col in date_cols:
        df[col] = to_date(df[col])

    # Clean all remaining text columns.
    text_cols = [col for col in df.columns if col not in int_cols + date_cols]

    for col in text_cols:
        df[col] = df[col].map(clean_text)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        # Replace all existing clinical metadata.
        cur.execute("TRUNCATE TABLE clinical_data RESTART IDENTITY;")

        insert_sql = """
            INSERT INTO clinical_data (
                sample_id,
                ordre_chronologique,
                cluster_id,
                flag_epitrack,
                flag_uhe,
                valid_genom,
                glims,
                ipp,
                date_prelevement,
                species,
                type_prelevement,
                bmr_bhre,
                mlst_species,
                identification,
                transplanting_date,
                isolation_media_1,
                isolation_media_2,
                extraction_date,
                extraction_statut,
                quantification,
                seq_illumina_date,
                illumina_statut,
                seq_nanopore_date,
                seq_nanopore_batch,
                seq_nanopore_batch_bis,
                seq_nanopore_date_bis,
                seq_nanopore_batch_ter,
                seq_nanopore_date_ter,
                nanopore_statut,
                station_ngs,
                assemblage,
                annotation,
                rendu,
                cluster_rendu
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            );
        """

        rows = []

        for _, row in df.iterrows():
            ordre_val = (
                None
                if pd.isna(row["ordre_chronologique"])
                else int(row["ordre_chronologique"])
            )

            rows.append((
                clean_scalar(row["sample_id"]),
                ordre_val,
                clean_scalar(row["cluster_id"]),
                clean_scalar(row["flag_epitrack"]),
                clean_scalar(row["flag_uhe"]),
                clean_scalar(row["valid_genom"]),
                clean_scalar(row["glims"]),
                clean_scalar(row["ipp"]),
                clean_scalar(row["date_prelevement"]),
                clean_scalar(row["species"]),
                clean_scalar(row["type_prelevement"]),
                clean_scalar(row["bmr_bhre"]),
                clean_scalar(row["mlst_species"]),
                clean_scalar(row["identification"]),
                clean_scalar(row["transplanting_date"]),
                clean_scalar(row["isolation_media_1"]),
                clean_scalar(row["isolation_media_2"]),
                clean_scalar(row["extraction_date"]),
                clean_scalar(row["extraction_statut"]),
                clean_scalar(row["quantification"]),
                clean_scalar(row["seq_illumina_date"]),
                clean_scalar(row["illumina_statut"]),
                clean_scalar(row["seq_nanopore_date"]),
                clean_scalar(row["seq_nanopore_batch"]),
                clean_scalar(row["seq_nanopore_batch_bis"]),
                clean_scalar(row["seq_nanopore_date_bis"]),
                clean_scalar(row["seq_nanopore_batch_ter"]),
                clean_scalar(row["seq_nanopore_date_ter"]),
                clean_scalar(row["nanopore_statut"]),
                clean_scalar(row["station_ngs"]),
                clean_scalar(row["assemblage"]),
                clean_scalar(row["annotation"]),
                clean_scalar(row["rendu"]),
                clean_scalar(row["cluster_rendu"]),
            ))

        cur.executemany(insert_sql, rows)

        # Create indexes to improve query performance in the dashboard.
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_clinical_data_glims "
            "ON clinical_data(glims);"
        )

        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_clinical_data_sample_id "
            "ON clinical_data(sample_id);"
        )

        conn.commit()

        print(f"Import completed: {len(rows)} rows inserted into clinical_data.")

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
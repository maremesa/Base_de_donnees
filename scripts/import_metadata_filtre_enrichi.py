#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Import enriched clinical metadata into the BHRe PostgreSQL database.

This script loads an Excel spreadsheet containing epidemiological,
clinical, sequencing, and laboratory metadata associated with BHRe
samples. The data are cleaned, standardized, and inserted into the
`clinical_data` table of the PostgreSQL database.

Main workflow
-------------
1. Load the Excel metadata file.
2. Rename Excel columns to match the database schema.
3. Validate the expected structure.
4. Clean text and date fields.
5. Insert all records into PostgreSQL using batch insertion.
6. Verify the final number of imported records.

Author
------
Mareme SARR
Bioinformatics Engineer
Hospices Civils de Lyon (HCL)
"""

from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch


# ============================================================================
# Configuration
# ============================================================================

FILE = Path("/data/msarr/metadata_filtre_enrichi.xlsx")

DB_CONFIG = {
    "dbname": "bd_bhre",
    "user": "msarr",
    "host": "localhost",
    "port": 55432,
}


# ============================================================================
# Data cleaning utilities
# ============================================================================

def clean_text(x):
    """
    Clean a text value before database insertion.

    Missing values, empty strings, and textual representations of
    missing values (e.g. "nan") are converted to None.

    Parameters
    ----------
    x : Any
        Input value.

    Returns
    -------
    str | None
        Cleaned string or None.
    """
    if pd.isna(x):
        return None

    x = str(x).strip()

    if x == "" or x.lower() == "nan":
        return None

    return x


def clean_date(x):
    """
    Convert a date-like value into a Python date object.

    Invalid dates are converted to None.

    Parameters
    ----------
    x : Any
        Input date value.

    Returns
    -------
    datetime.date | None
        Parsed date or None if conversion fails.
    """
    if pd.isna(x):
        return None

    dt = pd.to_datetime(x, errors="coerce")

    if pd.isna(dt):
        return None

    return dt.date()


# ============================================================================
# Main import workflow
# ============================================================================

def main():
    """
    Execute the metadata import pipeline.

    The function loads the Excel metadata file, validates the schema,
    cleans the dataset, and inserts all records into the PostgreSQL
    `clinical_data` table using optimized batch insertion.

    Raises
    ------
    FileNotFoundError
        If the Excel metadata file cannot be found.

    ValueError
        If required columns are missing.

    psycopg2.Error
        If a database error occurs during insertion.
    """

    # ------------------------------------------------------------------------
    # Verify that the input file exists
    # ------------------------------------------------------------------------
    if not FILE.exists():
        raise FileNotFoundError(f"File not found: {FILE}")

    # ------------------------------------------------------------------------
    # Load Excel metadata
    # ------------------------------------------------------------------------
    df = pd.read_excel(FILE, dtype=str)

    # ------------------------------------------------------------------------
    # Rename Excel column names to PostgreSQL-compatible names
    # ------------------------------------------------------------------------
    df = df.rename(columns={
        "Sample_Epi": "sample_epi",
        "ordre chronologique": "ordre_chronologique",
        "CLUSTER_ID": "cluster_id",
        "Flag_Epitrack": "flag_epitrack",
        "Flag_UHE": "flag_uhe",
        "VALID_GENOM": "valid_genom",
        "SAMPLE_ID": "sample_id",
        "IPP": "ipp",
        "DATE_PRELEVEMENT": "date_prelevement",
        "SPECIES": "species",
        "TYPE_PRELEVEMENT": "type_prelevement",
        "BMR-BHRE": "bmr_bhre",
        "MLST_SPECIES": "mlst_species",
        "IDENTIFICATION": "identification",
        "TRANSPLANTING_DATE ": "transplanting_date",
        "TRANSPLANTING_DATE": "transplanting_date",
        "ISOLATION_MEDIA_1": "isolation_media_1",
        "ISOLATION_MEDIA_2": "isolation_media_2",
        "EXTRACTION_DATE": "extraction_date",
        "EXTRACTION_STATUT": "extraction_statut",
        "QUANTIFICATION": "quantification",
        "SEQ_ILLUMINA_DATE": "seq_illumina_date",
        "ILLUMINA_STATUT": "illumina_statut",
        "SEQ_NANOPORE_DATE": "seq_nanopore_date",
        "SEQ_NANOPORE_BATCH": "seq_nanopore_batch",
        "SEQ_NANOPORE_BATCH_BIS": "seq_nanopore_batch_bis",
        "SEQ_NANOPORE_DATE_BIS": "seq_nanopore_date_bis",
        "SEQ_NANOPORE_BATCH_TER": "seq_nanopore_batch_ter",
        "SEQ_NANOPORE_DATE_TER": "seq_nanopore_date_ter",
        "NANOPORE_STATUT": "nanopore_statut",
        "STATION_NGS": "station_ngs",
        "ASSEMBLAGE": "assemblage",
        "ANNOTATION": "annotation",
        "RENDU": "rendu",
        "CLUSTER_RENDU": "cluster_rendu",
        "Unnamed: 34": "unnamed_34",
    })

    # ------------------------------------------------------------------------
    # Expected schema validation
    # ------------------------------------------------------------------------
    expected_cols = [
        "sample_epi",
        "ordre_chronologique",
        "cluster_id",
        "flag_epitrack",
        "flag_uhe",
        "valid_genom",
        "sample_id",
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
        "unnamed_34",
    ]

    missing = [c for c in expected_cols if c not in df.columns]

    if missing:
        raise ValueError(
            f"Missing columns in Excel file: {missing}"
        )

    # ------------------------------------------------------------------------
    # Clean text columns
    # ------------------------------------------------------------------------
    text_cols = [
        "sample_epi",
        "ordre_chronologique",
        "cluster_id",
        "flag_epitrack",
        "flag_uhe",
        "valid_genom",
        "sample_id",
        "ipp",
        "species",
        "type_prelevement",
        "bmr_bhre",
        "mlst_species",
        "identification",
        "isolation_media_1",
        "isolation_media_2",
        "extraction_statut",
        "quantification",
        "illumina_statut",
        "seq_nanopore_batch",
        "seq_nanopore_batch_bis",
        "seq_nanopore_batch_ter",
        "nanopore_statut",
        "station_ngs",
        "assemblage",
        "annotation",
        "rendu",
        "cluster_rendu",
        "unnamed_34",
    ]

    for col in text_cols:
        df[col] = df[col].apply(clean_text)

    # ------------------------------------------------------------------------
    # Clean date columns
    # ------------------------------------------------------------------------
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
        df[col] = df[col].apply(clean_date)

    # Convert DataFrame to dictionaries for batch insertion.
    rows = df[expected_cols].to_dict(orient="records")

    # ------------------------------------------------------------------------
    # Database connection
    # ------------------------------------------------------------------------
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    insert_sql = """
        INSERT INTO clinical_data (
            sample_epi,
            ordre_chronologique,
            cluster_id,
            flag_epitrack,
            flag_uhe,
            valid_genom,
            sample_id,
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
            cluster_rendu,
            unnamed_34
        )
        VALUES (
            %(sample_epi)s,
            %(ordre_chronologique)s,
            %(cluster_id)s,
            %(flag_epitrack)s,
            %(flag_uhe)s,
            %(valid_genom)s,
            %(sample_id)s,
            %(ipp)s,
            %(date_prelevement)s,
            %(species)s,
            %(type_prelevement)s,
            %(bmr_bhre)s,
            %(mlst_species)s,
            %(identification)s,
            %(transplanting_date)s,
            %(isolation_media_1)s,
            %(isolation_media_2)s,
            %(extraction_date)s,
            %(extraction_statut)s,
            %(quantification)s,
            %(seq_illumina_date)s,
            %(illumina_statut)s,
            %(seq_nanopore_date)s,
            %(seq_nanopore_batch)s,
            %(seq_nanopore_batch_bis)s,
            %(seq_nanopore_date_bis)s,
            %(seq_nanopore_batch_ter)s,
            %(seq_nanopore_date_ter)s,
            %(nanopore_statut)s,
            %(station_ngs)s,
            %(assemblage)s,
            %(annotation)s,
            %(rendu)s,
            %(cluster_rendu)s,
            %(unnamed_34)s
        )
    """

    # ------------------------------------------------------------------------
    # Batch insertion
    # ------------------------------------------------------------------------
    execute_batch(
        cur,
        insert_sql,
        rows,
        page_size=1000
    )

    conn.commit()

    # ------------------------------------------------------------------------
    # Import verification
    # ------------------------------------------------------------------------
    cur.execute("SELECT COUNT(*) FROM clinical_data;")
    n = cur.fetchone()[0]

    cur.close()
    conn.close()

    print(
        f"Import completed successfully: "
        f"{n} rows inserted into clinical_data."
    )


if __name__ == "__main__":
    main()
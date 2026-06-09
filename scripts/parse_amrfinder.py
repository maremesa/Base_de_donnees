from pathlib import Path
import csv

import psycopg2


"""
Parse AMRFinderPlus results into a generic analysis results table.

This script scans all sample directories in the BHRe project structure,
locates AMRFinderPlus result files, extracts selected result columns, and
stores them in the generic `analysis_results` PostgreSQL table.

Unlike the dedicated `amrfinder_hits` import script, this script stores
results in a key-value format:

    sample_id | tool_name | result_key | result_value | source_file

This structure is useful for generic dashboards, flexible result browsing,
or storing heterogeneous outputs from multiple bioinformatics tools.

Main workflow
-------------
1. Iterate through all sample directories.
2. Locate each AMRFinderPlus result file.
3. Parse selected columns from each AMRFinderPlus hit.
4. Store each selected value as a key-value result.
5. Commit the transaction.

Author
------
Mareme SARR
Bioinformatics Engineer
Hospices Civils de Lyon
"""


# ============================================================================
# Configuration
# ============================================================================

ROOT_DIR = Path("/data/msarr/BD_BHRe")

DB_CONFIG = {
    "dbname": "bd_bhre",
    "user": "msarr",
    "host": "localhost",
    "port": 55432,
}

AMRFINDER_COLUMNS = [
    "Gene symbol",
    "Sequence name",
    "Scope",
    "Element type",
    "Element subtype",
    "Class",
    "Subclass",
    "Method",
    "% Coverage of reference sequence",
    "% Identity to reference sequence",
    "Name of closest sequence",
]


# ============================================================================
# Data cleaning utilities
# ============================================================================

def clean_value(value):
    """
    Clean a raw AMRFinderPlus value.

    Empty values and missing values are converted to None.

    Parameters
    ----------
    value : str | None
        Raw value extracted from the AMRFinderPlus TSV file.

    Returns
    -------
    str | None
        Cleaned value or None.
    """
    if value is None:
        return None

    value = value.strip()

    if value == "":
        return None

    return value


# ============================================================================
# AMRFinderPlus parsing workflow
# ============================================================================

def parse_amrfinder_results():
    """
    Parse AMRFinderPlus outputs and insert them into `analysis_results`.

    The function scans each sample directory under `ROOT_DIR` and searches
    for the expected AMRFinderPlus output file:

        <sample_dir>/amrfinder/amrfinder.tsv

    For each detected AMRFinderPlus hit, selected columns are stored as
    key-value pairs in the `analysis_results` table.

    The generated `result_key` follows this format:

        hit_<hit_number>:<AMRFinderPlus column name>

    Example
    -------
    For the first AMRFinderPlus hit, the gene symbol is stored as:

        hit_1:Gene symbol

    Raises
    ------
    FileNotFoundError
        If the root directory does not exist.

    psycopg2.Error
        If a database error occurs during insertion.
    """
    if not ROOT_DIR.exists():
        raise FileNotFoundError(f"Root directory not found: {ROOT_DIR}")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        # Remove previous AMRFinderPlus entries from the generic results table.
        cur.execute(
            "DELETE FROM analysis_results WHERE tool_name = 'amrfinder';"
        )

        for sample_dir in ROOT_DIR.iterdir():
            if not sample_dir.is_dir():
                continue

            sample_id = sample_dir.name
            amr_file = sample_dir / "amrfinder" / "amrfinder.tsv"

            if not amr_file.exists():
                continue

            with open(
                amr_file,
                "r",
                encoding="utf-8",
                errors="replace",
                newline=""
            ) as handle:
                reader = csv.DictReader(handle, delimiter="\t")

                hit_count = 0

                for row in reader:
                    hit_count += 1

                    for column in AMRFINDER_COLUMNS:
                        value = clean_value(row.get(column))

                        if value is None:
                            continue

                        cur.execute("""
                            INSERT INTO analysis_results (
                                sample_id,
                                tool_name,
                                result_key,
                                result_value,
                                source_file
                            )
                            VALUES (
                                %s, %s, %s, %s, %s
                            )
                        """, (
                            sample_id,
                            "amrfinder",
                            f"hit_{hit_count}:{column}",
                            value,
                            str(amr_file)
                        ))

            print(
                f"[AMRFINDER] "
                f"{sample_id} -> {hit_count} hit(s)"
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    print("AMRFinderPlus parsing completed successfully.")


if __name__ == "__main__":
    parse_amrfinder_results()
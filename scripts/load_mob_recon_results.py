from pathlib import Path
import csv

import psycopg2


"""
Load MOB-recon plasmid reconstruction results into the BHRe PostgreSQL database.

This script scans all sample directories in the BHRe project structure,
locates MOB-recon result files, parses plasmid reconstruction and mobility
prediction information, and stores the results in the `mob_recon_results`
PostgreSQL table.

Main workflow
-------------
1. Iterate through all sample directories.
2. Locate the MOB-recon result file (`mobtyper_results.txt`).
3. Parse plasmid metadata, mobility predictions, and host range information.
4. Clean missing values and convert numeric fields.
5. Insert MOB-recon results into PostgreSQL.
6. Commit the transaction.

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


# ============================================================================
# Data cleaning utilities
# ============================================================================

def clean_value(row: dict, key: str):
    """
    Extract and clean a value from a MOB-recon result row.

    Empty strings and "-" values are converted to None so they can be
    inserted as SQL NULL values.

    Parameters
    ----------
    row : dict
        One row from the MOB-recon TSV output file.

    key : str
        Column name to extract.

    Returns
    -------
    str | None
        Cleaned value or None.
    """
    value = row.get(key)

    if value is None:
        return None

    value = value.strip()

    if value == "" or value == "-":
        return None

    return value


def to_int(row: dict, key: str):
    """
    Convert a MOB-recon field to an integer.

    Missing values are returned as None.

    Parameters
    ----------
    row : dict
        One row from the MOB-recon TSV output file.

    key : str
        Column name containing an integer value.

    Returns
    -------
    int | None
        Converted integer value or None.
    """
    value = clean_value(row, key)

    if value is None:
        return None

    return int(value)


def to_float(row: dict, key: str):
    """
    Convert a MOB-recon field to a float.

    Missing values are returned as None.

    Parameters
    ----------
    row : dict
        One row from the MOB-recon TSV output file.

    key : str
        Column name containing a numeric value.

    Returns
    -------
    float | None
        Converted float value or None.
    """
    value = clean_value(row, key)

    if value is None:
        return None

    return float(value)


# ============================================================================
# MOB-recon import workflow
# ============================================================================

def load_mob_recon_results():
    """
    Import MOB-recon results into the PostgreSQL database.

    The function scans each sample directory under `ROOT_DIR` and searches
    for the expected MOB-recon output file:

        <sample_dir>/mob_recon/mobtyper_results.txt

    For each plasmid row, the function extracts:
    - plasmid identifier
    - number of contigs
    - plasmid size
    - GC content
    - replicon type
    - relaxase type
    - MPF type
    - predicted mobility
    - Mash neighbor identification
    - predicted host range

    Results are inserted into the `mob_recon_results` table.

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
        # Remove previous MOB-recon results before reloading.
        cur.execute("TRUNCATE TABLE mob_recon_results;")

        for sample_dir in ROOT_DIR.iterdir():
            if not sample_dir.is_dir():
                continue

            sample_id = sample_dir.name
            mob_file = sample_dir / "mob_recon" / "mobtyper_results.txt"

            if not mob_file.exists():
                continue

            n_plasmids = 0

            with open(
                mob_file,
                "r",
                encoding="utf-8",
                errors="replace",
                newline=""
            ) as handle:
                reader = csv.DictReader(handle, delimiter="\t")

                for row in reader:
                    raw_plasmid = clean_value(row, "sample_id")

                    plasmid_id = None
                    if raw_plasmid and ":" in raw_plasmid:
                        plasmid_id = raw_plasmid.split(":")[-1]

                    host_range = clean_value(
                        row,
                        "predicted_host_range_overall_name"
                    )

                    cur.execute("""
                        INSERT INTO mob_recon_results (
                            sample_id,
                            plasmid_id,
                            num_contigs,
                            size,
                            gc,
                            rep_type,
                            relaxase_type,
                            mpf_type,
                            predicted_mobility,
                            mash_neighbor,
                            host_range,
                            source_file
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        sample_id,
                        plasmid_id,
                        to_int(row, "num_contigs"),
                        to_int(row, "size"),
                        to_float(row, "gc"),
                        clean_value(row, "rep_type(s)"),
                        clean_value(row, "relaxase_type(s)"),
                        clean_value(row, "mpf_type"),
                        clean_value(row, "predicted_mobility"),
                        clean_value(row, "mash_neighbor_identification"),
                        host_range,
                        str(mob_file),
                    ))

                    n_plasmids += 1

            print(
                f"[MOB_RECON] "
                f"{sample_id} -> {n_plasmids} plasmid(s)"
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    print("MOB-recon results loading completed successfully.")


if __name__ == "__main__":
    load_mob_recon_results()
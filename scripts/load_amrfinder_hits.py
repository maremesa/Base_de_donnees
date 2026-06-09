from pathlib import Path
import csv

import psycopg2


"""
Load AMRFinderPlus results into the BHRe PostgreSQL database.

This script scans all sample directories in the BHRe project directory,
looks for AMRFinderPlus result files, parses each `amrfinder.tsv` file,
and inserts the detected antimicrobial resistance hits into the
`amrfinder_hits` PostgreSQL table.

Main workflow
-------------
1. Iterate over all sample directories.
2. Locate each sample's AMRFinderPlus TSV output.
3. Parse AMR hits from the TSV file.
4. Clean missing or empty values.
5. Convert coverage and identity values to floats.
6. Insert results into the `amrfinder_hits` table.
7. Commit the transaction.

Author
------
Mareme SARR
Bioinformatics Engineer
Hospices Civils de Lyon
"""


ROOT_DIR = Path("/data/msarr/BD_BHRe")

DB_CONFIG = {
    "dbname": "bd_bhre",
    "user": "msarr",
    "host": "localhost",
    "port": 55432,
}


def clean_value(row: dict, key: str):
    """
    Extract and clean a value from an AMRFinderPlus TSV row.

    Empty strings and "NA" values are converted to None so they can be
    inserted as SQL NULL values.

    Parameters
    ----------
    row : dict
        One row from the AMRFinderPlus TSV file.

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

    if value == "" or value == "NA":
        return None

    return value


def to_float(row: dict, key: str):
    """
    Convert a numeric AMRFinderPlus field to float.

    Missing or empty values are returned as None.

    Parameters
    ----------
    row : dict
        One row from the AMRFinderPlus TSV file.

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


def load_amrfinder_hits():
    """
    Load AMRFinderPlus hits into the PostgreSQL database.

    The function truncates the existing `amrfinder_hits` table, then scans
    every sample directory under `ROOT_DIR`. For each sample, it expects an
    AMRFinderPlus output file at:

        <sample_dir>/amrfinder/amrfinder.tsv

    Each row is inserted into the `amrfinder_hits` table with the associated
    sample identifier and source file path.

    Raises
    ------
    psycopg2.Error
        If a database error occurs.

    FileNotFoundError
        If `ROOT_DIR` does not exist.
    """
    if not ROOT_DIR.exists():
        raise FileNotFoundError(f"Root directory not found: {ROOT_DIR}")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        cur.execute("TRUNCATE TABLE amrfinder_hits;")

        for sample_dir in ROOT_DIR.iterdir():
            if not sample_dir.is_dir():
                continue

            sample_id = sample_dir.name
            amr_file = sample_dir / "amrfinder" / "amrfinder.tsv"

            if not amr_file.exists():
                continue

            n_hits = 0

            with open(
                amr_file,
                "r",
                encoding="utf-8",
                errors="replace",
                newline=""
            ) as handle:
                reader = csv.DictReader(handle, delimiter="\t")

                for row in reader:
                    cur.execute("""
                        INSERT INTO amrfinder_hits (
                            sample_id,
                            gene_symbol,
                            sequence_name,
                            scope,
                            element_type,
                            element_subtype,
                            class,
                            subclass,
                            method,
                            coverage,
                            identity,
                            closest_sequence,
                            source_file
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        sample_id,
                        clean_value(row, "Gene symbol"),
                        clean_value(row, "Sequence name"),
                        clean_value(row, "Scope"),
                        clean_value(row, "Element type"),
                        clean_value(row, "Element subtype"),
                        clean_value(row, "Class"),
                        clean_value(row, "Subclass"),
                        clean_value(row, "Method"),
                        to_float(row, "% Coverage of reference sequence"),
                        to_float(row, "% Identity to reference sequence"),
                        clean_value(row, "Name of closest sequence"),
                        str(amr_file),
                    ))

                    n_hits += 1

            print(f"[AMR_HITS] {sample_id} -> {n_hits} hit(s)")

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    print("AMRFinderPlus loading completed successfully.")


if __name__ == "__main__":
    load_amrfinder_hits()
from pathlib import Path
import csv

import psycopg2


"""
Load Prokka genome annotation results into the BHRe PostgreSQL database.

This script scans all sample directories in the BHRe project structure,
locates Prokka annotation TSV files, parses functional annotation results,
and stores them in the `prokka_annotations` PostgreSQL table.

Main workflow
-------------
1. Iterate through all sample directories.
2. Locate the Prokka output directory.
3. Select the first available Prokka TSV annotation file.
4. Parse annotation fields such as locus tag, feature type, gene, COG,
   EC number, product description, and feature length.
5. Insert parsed annotations into PostgreSQL.
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
    Extract and clean a value from a Prokka annotation row.

    Empty strings are converted to None so they can be inserted as SQL NULL
    values.

    Parameters
    ----------
    row : dict
        One row from a Prokka TSV annotation file.

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

    if value == "":
        return None

    return value


def to_int(row: dict, key: str):
    """
    Convert a Prokka numeric field to an integer.

    Missing or empty values are returned as None.

    Parameters
    ----------
    row : dict
        One row from a Prokka TSV annotation file.

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


# ============================================================================
# Prokka import workflow
# ============================================================================

def load_prokka_annotations():
    """
    Import Prokka annotations into the PostgreSQL database.

    The function scans each sample directory under `ROOT_DIR` and searches
    for Prokka annotation TSV files in:

        <sample_dir>/prokka/*.tsv

    The first TSV file found is parsed and inserted into the
    `prokka_annotations` table.

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
        # Remove previous Prokka annotations before reloading.
        cur.execute("TRUNCATE TABLE prokka_annotations;")

        for sample_dir in ROOT_DIR.iterdir():
            if not sample_dir.is_dir():
                continue

            sample_id = sample_dir.name
            prokka_dir = sample_dir / "prokka"

            if not prokka_dir.exists():
                continue

            tsv_files = list(prokka_dir.glob("*.tsv"))

            if not tsv_files:
                continue

            prokka_file = tsv_files[0]
            n_annotations = 0

            with open(
                prokka_file,
                "r",
                encoding="utf-8",
                errors="replace",
                newline=""
            ) as handle:
                reader = csv.DictReader(handle, delimiter="\t")

                for row in reader:
                    cur.execute("""
                        INSERT INTO prokka_annotations (
                            sample_id,
                            locus_tag,
                            ftype,
                            length_bp,
                            gene,
                            ec_number,
                            cog,
                            product,
                            source_file
                        )
                        VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s
                        )
                    """, (
                        sample_id,
                        clean_value(row, "locus_tag"),
                        clean_value(row, "ftype"),
                        to_int(row, "length_bp"),
                        clean_value(row, "gene"),
                        clean_value(row, "EC_number"),
                        clean_value(row, "COG"),
                        clean_value(row, "product"),
                        str(prokka_file),
                    ))

                    n_annotations += 1

            print(
                f"[PROKKA] "
                f"{sample_id} -> {n_annotations} annotation(s)"
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    print("Prokka annotation loading completed successfully.")


if __name__ == "__main__":
    load_prokka_annotations()
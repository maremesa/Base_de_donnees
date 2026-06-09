from pathlib import Path
import csv

import psycopg2


"""
Load QUAST assembly quality metrics into the BHRe PostgreSQL database.

This script scans all sample directories in the BHRe project structure,
locates QUAST report files, parses assembly quality metrics, and stores
them in the `quast_metrics` PostgreSQL table.

Main workflow
-------------
1. Iterate through all sample directories.
2. Locate the QUAST report file (`report.tsv`).
3. Skip the header line.
4. Parse metric names and metric values.
5. Insert metrics into PostgreSQL.
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
# QUAST import workflow
# ============================================================================

def load_quast_metrics():
    """
    Import QUAST metrics into the PostgreSQL database.

    The function scans each sample directory under `ROOT_DIR` and searches
    for the expected QUAST report file:

        <sample_dir>/quast/report.tsv

    Each metric is inserted into the `quast_metrics` table with the
    corresponding sample identifier and source file path.

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
        # Remove previous QUAST metrics before reloading.
        cur.execute("TRUNCATE TABLE quast_metrics;")

        for sample_dir in ROOT_DIR.iterdir():
            if not sample_dir.is_dir():
                continue

            sample_id = sample_dir.name
            quast_file = sample_dir / "quast" / "report.tsv"

            if not quast_file.exists():
                continue

            n_metrics = 0

            with open(
                quast_file,
                "r",
                encoding="utf-8",
                errors="replace",
                newline=""
            ) as handle:
                reader = csv.reader(handle, delimiter="\t")
                header_skipped = False

                for row in reader:
                    if not row:
                        continue

                    if not header_skipped:
                        header_skipped = True
                        continue

                    if len(row) < 2:
                        continue

                    metric_name = row[0].strip()
                    metric_value = row[1].strip()

                    cur.execute("""
                        INSERT INTO quast_metrics (
                            sample_id,
                            metric_name,
                            metric_value,
                            source_file
                        )
                        VALUES (
                            %s, %s, %s, %s
                        )
                    """, (
                        sample_id,
                        metric_name,
                        metric_value,
                        str(quast_file)
                    ))

                    n_metrics += 1

            print(
                f"[QUAST] "
                f"{sample_id} -> {n_metrics} metric(s)"
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    print("QUAST metrics loading completed successfully.")


if __name__ == "__main__":
    load_quast_metrics()
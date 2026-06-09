from pathlib import Path

import psycopg2


"""
Parse MLST results into a generic analysis results table.

This script scans all sample directories in the BHRe project structure,
locates MLST result files, extracts species, sequence type, sequence file,
and allele profiles, then stores them in the generic `analysis_results`
PostgreSQL table.

The results are stored in a key-value format:

    sample_id | tool_name | result_key | result_value | source_file

Main workflow
-------------
1. Iterate through all sample directories.
2. Locate each MLST result file.
3. Parse species, ST, sequence file, and alleles.
4. Insert parsed values into `analysis_results`.
5. Commit the transaction.

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


def parse_mlst_results():
    """
    Parse MLST outputs and insert them into `analysis_results`.

    The function scans each sample directory under `ROOT_DIR` and searches
    for the expected MLST output file:

        <sample_dir>/mlst/mlst.tsv

    Each valid MLST line is expected to contain at least:

        sequence_file species ST

    Additional values are joined and stored as the allele profile.

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
        cur.execute(
            "DELETE FROM analysis_results WHERE tool_name = 'mlst';"
        )

        for sample_dir in ROOT_DIR.iterdir():
            if not sample_dir.is_dir():
                continue

            sample_id = sample_dir.name
            mlst_file = sample_dir / "mlst" / "mlst.tsv"

            if not mlst_file.exists():
                continue

            with open(
                mlst_file,
                "r",
                encoding="utf-8",
                errors="replace"
            ) as handle:
                for line in handle:
                    line = line.strip()

                    if not line:
                        continue

                    parts = line.split()

                    if len(parts) < 3:
                        print(
                            f"[SKIP] Short malformed line in "
                            f"{mlst_file}: {line}"
                        )
                        continue

                    sequence_file = parts[0]
                    species = parts[1]
                    st = parts[2]
                    alleles = (
                        " ".join(parts[3:])
                        if len(parts) > 3
                        else None
                    )

                    rows = [
                        (
                            sample_id,
                            "mlst",
                            "sequence_file",
                            sequence_file,
                            str(mlst_file)
                        ),
                        (
                            sample_id,
                            "mlst",
                            "species",
                            species,
                            str(mlst_file)
                        ),
                        (
                            sample_id,
                            "mlst",
                            "ST",
                            st,
                            str(mlst_file)
                        ),
                    ]

                    if alleles:
                        rows.append((
                            sample_id,
                            "mlst",
                            "alleles",
                            alleles,
                            str(mlst_file)
                        ))

                    cur.executemany("""
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
                    """, rows)

                    print(
                        f"[MLST] {sample_id} -> "
                        f"species={species}, ST={st}"
                    )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()

    print("MLST parsing completed successfully.")


if __name__ == "__main__":
    parse_mlst_results()
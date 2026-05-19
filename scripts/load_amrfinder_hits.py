from pathlib import Path
import csv
import psycopg2

ROOT_DIR = Path("/data/msarr/BD_BHRe")

conn = psycopg2.connect(
    dbname="bd_bhre",
    user="msarr",
    host="localhost",
    port=55432
)

cur = conn.cursor()

cur.execute("TRUNCATE TABLE amrfinder_hits;")

for sample_dir in ROOT_DIR.iterdir():
    if not sample_dir.is_dir():
        continue

    sample_id = sample_dir.name
    amr_file = sample_dir / "amrfinder" / "amrfinder.tsv"

    if not amr_file.exists():
        continue

    n = 0
    with open(amr_file, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            def val(key):
                x = row.get(key)
                if x is None:
                    return None
                x = x.strip()
                return None if x == "" or x == "NA" else x

            def to_float(key):
                x = val(key)
                return float(x) if x is not None else None

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
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                sample_id,
                val("Gene symbol"),
                val("Sequence name"),
                val("Scope"),
                val("Element type"),
                val("Element subtype"),
                val("Class"),
                val("Subclass"),
                val("Method"),
                to_float("% Coverage of reference sequence"),
                to_float("% Identity to reference sequence"),
                val("Name of closest sequence"),
                str(amr_file)
            ))
            n += 1

    print(f"[AMR_HITS] {sample_id} -> {n} hit(s)")

conn.commit()
cur.close()
conn.close()

print("Chargement amrfinder_hits terminé")

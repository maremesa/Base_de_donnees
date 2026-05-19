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
    n = 0

    with open(prokka_file, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            def val(key):
                x = row.get(key)
                if x is None:
                    return None
                x = x.strip()
                return None if x == "" else x

            def to_int(key):
                x = val(key)
                return int(x) if x is not None else None

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
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                sample_id,
                val("locus_tag"),
                val("ftype"),
                to_int("length_bp"),
                val("gene"),
                val("EC_number"),
                val("COG"),
                val("product"),
                str(prokka_file)
            ))
            n += 1

    print(f"[PROKKA] {sample_id} -> {n} annotation(s)")

conn.commit()
cur.close()
conn.close()

print("Chargement prokka_annotations terminé")

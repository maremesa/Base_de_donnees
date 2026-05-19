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

cur.execute("TRUNCATE TABLE quast_metrics;")

for sample_dir in ROOT_DIR.iterdir():
    if not sample_dir.is_dir():
        continue

    sample_id = sample_dir.name
    quast_file = sample_dir / "quast" / "report.tsv"

    if not quast_file.exists():
        continue

    n = 0
    with open(quast_file, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
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
                VALUES (%s, %s, %s, %s)
            """, (
                sample_id,
                metric_name,
                metric_value,
                str(quast_file)
            ))
            n += 1

    print(f"[QUAST] {sample_id} -> {n} métrique(s)")

conn.commit()
cur.close()
conn.close()

print("Chargement quast_metrics terminé")

from pathlib import Path
import psycopg2

ROOT_DIR = Path("/data/msarr/BD_BHRe")

conn = psycopg2.connect(
    dbname="bd_bhre",
    user="msarr",
    host="localhost",
    port=55432
)

cur = conn.cursor()

cur.execute("TRUNCATE TABLE mlst_results;")

for sample_dir in ROOT_DIR.iterdir():
    if not sample_dir.is_dir():
        continue

    sample_id = sample_dir.name
    mlst_file = sample_dir / "mlst" / "mlst.tsv"

    if not mlst_file.exists():
        continue

    n = 0
    with open(mlst_file, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) < 3:
                continue

            sequence_file = parts[0]
            species = parts[1]
            st = parts[2]
            alleles = " ".join(parts[3:]) if len(parts) > 3 else None

            cur.execute("""
                INSERT INTO mlst_results (
                    sample_id,
                    sequence_file,
                    species,
                    st,
                    alleles,
                    source_file
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                sample_id,
                sequence_file,
                species,
                st,
                alleles,
                str(mlst_file)
            ))
            n += 1

    print(f"[MLST_RESULTS] {sample_id} -> {n} ligne(s)")

conn.commit()
cur.close()
conn.close()

print("Chargement mlst_results terminé")

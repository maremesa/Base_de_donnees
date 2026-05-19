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

# Optionnel: on supprime les anciennes entrées mlst pour pouvoir relancer proprement
cur.execute("DELETE FROM analysis_results WHERE tool_name = 'mlst';")

for sample_dir in ROOT_DIR.iterdir():
    if not sample_dir.is_dir():
        continue

    sample_id = sample_dir.name
    mlst_file = sample_dir / "mlst" / "mlst.tsv"

    if not mlst_file.exists():
        continue

    with open(mlst_file, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split()

            if len(parts) < 3:
                print(f"[SKIP] ligne trop courte dans {mlst_file}: {line}")
                continue

            seq_file = parts[0]
            species = parts[1]
            st = parts[2]
            alleles = " ".join(parts[3:]) if len(parts) > 3 else None

            rows = [
                (sample_id, "mlst", "sequence_file", seq_file, str(mlst_file)),
                (sample_id, "mlst", "species", species, str(mlst_file)),
                (sample_id, "mlst", "ST", st, str(mlst_file)),
            ]

            if alleles:
                rows.append((sample_id, "mlst", "alleles", alleles, str(mlst_file)))

            cur.executemany("""
                INSERT INTO analysis_results
                (sample_id, tool_name, result_key, result_value, source_file)
                VALUES (%s, %s, %s, %s, %s)
            """, rows)

            print(f"[MLST] {sample_id} -> species={species}, ST={st}")

conn.commit()
cur.close()
conn.close()

print("Parsing MLST terminé")

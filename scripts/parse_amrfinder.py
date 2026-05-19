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

# Nettoyage pour pouvoir relancer proprement
cur.execute("DELETE FROM analysis_results WHERE tool_name = 'amrfinder';")

colonnes_utiles = [
    "Gene symbol",
    "Sequence name",
    "Scope",
    "Element type",
    "Element subtype",
    "Class",
    "Subclass",
    "Method",
    "% Coverage of reference sequence",
    "% Identity to reference sequence",
    "Name of closest sequence",
]

for sample_dir in ROOT_DIR.iterdir():
    if not sample_dir.is_dir():
        continue

    sample_id = sample_dir.name
    amr_file = sample_dir / "amrfinder" / "amrfinder.tsv"

    if not amr_file.exists():
        continue

    with open(amr_file, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")

        hit_num = 0
        for row in reader:
            hit_num += 1

            for col in colonnes_utiles:
                valeur = row.get(col)
                if valeur is None or valeur == "":
                    continue

                cur.execute("""
                    INSERT INTO analysis_results
                    (sample_id, tool_name, result_key, result_value, source_file)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    sample_id,
                    "amrfinder",
                    f"hit_{hit_num}:{col}",
                    valeur,
                    str(amr_file)
                ))

        print(f"[AMRFINDER] {sample_id} -> {hit_num} hit(s)")

conn.commit()
cur.close()
conn.close()

print("Parsing AMRFinder terminé")

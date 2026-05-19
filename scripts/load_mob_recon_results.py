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

cur.execute("TRUNCATE TABLE mob_recon_results;")

for sample_dir in ROOT_DIR.iterdir():
    if not sample_dir.is_dir():
        continue

    sample_id = sample_dir.name
    mob_file = sample_dir / "mob_recon" / "mobtyper_results.txt"

    if not mob_file.exists():
        continue

    n = 0

    with open(mob_file, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            def val(key):
                x = row.get(key)
                if x is None:
                    return None
                x = x.strip()
                return None if x == "" or x == "-" else x

            def to_int(key):
                x = val(key)
                return int(x) if x is not None else None

            def to_float(key):
                x = val(key)
                return float(x) if x is not None else None

            raw_plasmid = val("sample_id")
            plasmid_id = None
            if raw_plasmid and ":" in raw_plasmid:
                plasmid_id = raw_plasmid.split(":")[-1]

            host_range = val("predicted_host_range_overall_name")

            cur.execute("""
                INSERT INTO mob_recon_results (
                    sample_id,
                    plasmid_id,
                    num_contigs,
                    size,
                    gc,
                    rep_type,
                    relaxase_type,
                    mpf_type,
                    predicted_mobility,
                    mash_neighbor,
                    host_range,
                    source_file
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                sample_id,
                plasmid_id,
                to_int("num_contigs"),
                to_int("size"),
                to_float("gc"),
                val("rep_type(s)"),
                val("relaxase_type(s)"),
                val("mpf_type"),
                val("predicted_mobility"),
                val("mash_neighbor_identification"),
                host_range,
                str(mob_file)
            ))
            n += 1

    print(f"[MOB_RECON] {sample_id} -> {n} plasmide(s)")

conn.commit()
cur.close()
conn.close()

print("Chargement mob_recon_results terminé")

from pathlib import Path
from datetime import date, datetime

import pandas as pd
import psycopg2

DB_CONFIG = {
    "dbname": "bd_bhre",
    "user": "msarr",
    "host": "localhost",
    "port": 55432,
}

EXCEL_PATH = "/data/msarr/metadata.xlsx"


def to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.date


def clean_text(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text if text else None


def clean_scalar(value):
    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.date()

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return value


def main():
    path = Path(EXCEL_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {path}")

    df = pd.read_excel(path)

    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
    )

    df = df.drop(columns=["unnamed:_34"], errors="ignore")

    expected_cols = [
        "sample_id",
        "ordre_chronologique",
        "cluster_id",
        "flag_epitrack",
        "flag_uhe",
        "valid_genom",
        "glims",
        "ipp",
        "date_prelevement",
        "species",
        "type_prelevement",
        "bmr_bhre",
        "mlst_species",
        "identification",
        "transplanting_date",
        "isolation_media_1",
        "isolation_media_2",
        "extraction_date",
        "extraction_statut",
        "quantification",
        "seq_illumina_date",
        "illumina_statut",
        "seq_nanopore_date",
        "seq_nanopore_batch",
        "seq_nanopore_batch_bis",
        "seq_nanopore_date_bis",
        "seq_nanopore_batch_ter",
        "seq_nanopore_date_ter",
        "nanopore_statut",
        "station_ngs",
        "assemblage",
        "annotation",
        "rendu",
        "cluster_rendu",
    ]

    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes dans l'Excel: {missing}")

    df = df[expected_cols].copy()

    int_cols = ["ordre_chronologique"]
    for col in int_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    date_cols = [
        "date_prelevement",
        "transplanting_date",
        "extraction_date",
        "seq_illumina_date",
        "seq_nanopore_date",
        "seq_nanopore_date_bis",
        "seq_nanopore_date_ter",
    ]
    for col in date_cols:
        df[col] = to_date(df[col])

    text_cols = [c for c in df.columns if c not in int_cols + date_cols]
    for col in text_cols:
        df[col] = df[col].map(clean_text)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        cur.execute("TRUNCATE TABLE clinical_data RESTART IDENTITY;")

        insert_sql = """
            INSERT INTO clinical_data (
                sample_id,
                ordre_chronologique,
                cluster_id,
                flag_epitrack,
                flag_uhe,
                valid_genom,
                glims,
                ipp,
                date_prelevement,
                species,
                type_prelevement,
                bmr_bhre,
                mlst_species,
                identification,
                transplanting_date,
                isolation_media_1,
                isolation_media_2,
                extraction_date,
                extraction_statut,
                quantification,
                seq_illumina_date,
                illumina_statut,
                seq_nanopore_date,
                seq_nanopore_batch,
                seq_nanopore_batch_bis,
                seq_nanopore_date_bis,
                seq_nanopore_batch_ter,
                seq_nanopore_date_ter,
                nanopore_statut,
                station_ngs,
                assemblage,
                annotation,
                rendu,
                cluster_rendu
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            );
        """

        rows = []
        for _, row in df.iterrows():
            ordre_val = None if pd.isna(row["ordre_chronologique"]) else int(row["ordre_chronologique"])

            rows.append((
                clean_scalar(row["sample_id"]),
                ordre_val,
                clean_scalar(row["cluster_id"]),
                clean_scalar(row["flag_epitrack"]),
                clean_scalar(row["flag_uhe"]),
                clean_scalar(row["valid_genom"]),
                clean_scalar(row["glims"]),
                clean_scalar(row["ipp"]),
                clean_scalar(row["date_prelevement"]),
                clean_scalar(row["species"]),
                clean_scalar(row["type_prelevement"]),
                clean_scalar(row["bmr_bhre"]),
                clean_scalar(row["mlst_species"]),
                clean_scalar(row["identification"]),
                clean_scalar(row["transplanting_date"]),
                clean_scalar(row["isolation_media_1"]),
                clean_scalar(row["isolation_media_2"]),
                clean_scalar(row["extraction_date"]),
                clean_scalar(row["extraction_statut"]),
                clean_scalar(row["quantification"]),
                clean_scalar(row["seq_illumina_date"]),
                clean_scalar(row["illumina_statut"]),
                clean_scalar(row["seq_nanopore_date"]),
                clean_scalar(row["seq_nanopore_batch"]),
                clean_scalar(row["seq_nanopore_batch_bis"]),
                clean_scalar(row["seq_nanopore_date_bis"]),
                clean_scalar(row["seq_nanopore_batch_ter"]),
                clean_scalar(row["seq_nanopore_date_ter"]),
                clean_scalar(row["nanopore_statut"]),
                clean_scalar(row["station_ngs"]),
                clean_scalar(row["assemblage"]),
                clean_scalar(row["annotation"]),
                clean_scalar(row["rendu"]),
                clean_scalar(row["cluster_rendu"]),
            ))

        cur.executemany(insert_sql, rows)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_clinical_data_glims ON clinical_data(glims);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_clinical_data_sample_id ON clinical_data(sample_id);")

        conn.commit()
        print(f"Import terminé: {len(rows)} lignes insérées dans clinical_data.")

    except Exception:
        conn.rollback()
        raise

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

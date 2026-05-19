#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

FILE = Path("/data/msarr/metadata_filtre_enrichi.xlsx")

DB_CONFIG = {
    "dbname": "bd_bhre",
    "user": "msarr",
    "host": "localhost",
    "port": 55432,
}

def clean_text(x):
    if pd.isna(x):
        return None
    x = str(x).strip()
    if x == "" or x.lower() == "nan":
        return None
    return x


def clean_date(x):
    if pd.isna(x):
        return None
    dt = pd.to_datetime(x, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.date()


def main():
    if not FILE.exists():
        raise FileNotFoundError(f"Fichier introuvable : {FILE}")

    df = pd.read_excel(FILE, dtype=str)

    # Noms exacts du fichier -> noms SQL
    df = df.rename(columns={
        "Sample_Epi": "sample_epi",
        "ordre chronologique": "ordre_chronologique",
        "CLUSTER_ID": "cluster_id",
        "Flag_Epitrack": "flag_epitrack",
        "Flag_UHE": "flag_uhe",
        "VALID_GENOM": "valid_genom",
        "SAMPLE_ID": "sample_id",
        "IPP": "ipp",
        "DATE_PRELEVEMENT": "date_prelevement",
        "SPECIES": "species",
        "TYPE_PRELEVEMENT": "type_prelevement",
        "BMR-BHRE": "bmr_bhre",
        "MLST_SPECIES": "mlst_species",
        "IDENTIFICATION": "identification",
        "TRANSPLANTING_DATE ": "transplanting_date",
        "TRANSPLANTING_DATE": "transplanting_date",
        "ISOLATION_MEDIA_1": "isolation_media_1",
        "ISOLATION_MEDIA_2": "isolation_media_2",
        "EXTRACTION_DATE": "extraction_date",
        "EXTRACTION_STATUT": "extraction_statut",
        "QUANTIFICATION": "quantification",
        "SEQ_ILLUMINA_DATE": "seq_illumina_date",
        "ILLUMINA_STATUT": "illumina_statut",
        "SEQ_NANOPORE_DATE": "seq_nanopore_date",
        "SEQ_NANOPORE_BATCH": "seq_nanopore_batch",
        "SEQ_NANOPORE_BATCH_BIS": "seq_nanopore_batch_bis",
        "SEQ_NANOPORE_DATE_BIS": "seq_nanopore_date_bis",
        "SEQ_NANOPORE_BATCH_TER": "seq_nanopore_batch_ter",
        "SEQ_NANOPORE_DATE_TER": "seq_nanopore_date_ter",
        "NANOPORE_STATUT": "nanopore_statut",
        "STATION_NGS": "station_ngs",
        "ASSEMBLAGE": "assemblage",
        "ANNOTATION": "annotation",
        "RENDU": "rendu",
        "CLUSTER_RENDU": "cluster_rendu",
        "Unnamed: 34": "unnamed_34",
    })

    expected_cols = [
        "sample_epi",
        "ordre_chronologique",
        "cluster_id",
        "flag_epitrack",
        "flag_uhe",
        "valid_genom",
        "sample_id",
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
        "unnamed_34",
    ]

    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes dans le fichier Excel : {missing}")

    text_cols = [
        "sample_epi",
        "ordre_chronologique",
        "cluster_id",
        "flag_epitrack",
        "flag_uhe",
        "valid_genom",
        "sample_id",
        "ipp",
        "species",
        "type_prelevement",
        "bmr_bhre",
        "mlst_species",
        "identification",
        "isolation_media_1",
        "isolation_media_2",
        "extraction_statut",
        "quantification",
        "illumina_statut",
        "seq_nanopore_batch",
        "seq_nanopore_batch_bis",
        "seq_nanopore_batch_ter",
        "nanopore_statut",
        "station_ngs",
        "assemblage",
        "annotation",
        "rendu",
        "cluster_rendu",
        "unnamed_34",
    ]

    for col in text_cols:
        df[col] = df[col].apply(clean_text)

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
        df[col] = df[col].apply(clean_date)

    rows = df[expected_cols].to_dict(orient="records")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    insert_sql = """
        INSERT INTO clinical_data (
            sample_epi,
            ordre_chronologique,
            cluster_id,
            flag_epitrack,
            flag_uhe,
            valid_genom,
            sample_id,
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
            cluster_rendu,
            unnamed_34
        ) VALUES (
            %(sample_epi)s,
            %(ordre_chronologique)s,
            %(cluster_id)s,
            %(flag_epitrack)s,
            %(flag_uhe)s,
            %(valid_genom)s,
            %(sample_id)s,
            %(ipp)s,
            %(date_prelevement)s,
            %(species)s,
            %(type_prelevement)s,
            %(bmr_bhre)s,
            %(mlst_species)s,
            %(identification)s,
            %(transplanting_date)s,
            %(isolation_media_1)s,
            %(isolation_media_2)s,
            %(extraction_date)s,
            %(extraction_statut)s,
            %(quantification)s,
            %(seq_illumina_date)s,
            %(illumina_statut)s,
            %(seq_nanopore_date)s,
            %(seq_nanopore_batch)s,
            %(seq_nanopore_batch_bis)s,
            %(seq_nanopore_date_bis)s,
            %(seq_nanopore_batch_ter)s,
            %(seq_nanopore_date_ter)s,
            %(nanopore_statut)s,
            %(station_ngs)s,
            %(assemblage)s,
            %(annotation)s,
            %(rendu)s,
            %(cluster_rendu)s,
            %(unnamed_34)s
        )
    """

    execute_batch(cur, insert_sql, rows, page_size=1000)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM clinical_data;")
    n = cur.fetchone()[0]

    cur.close()
    conn.close()

    print(f"Import terminé : {n} lignes insérées dans clinical_data")


if __name__ == "__main__":
    main()

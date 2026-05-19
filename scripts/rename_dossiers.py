from pathlib import Path
import pandas as pd


def charger_mapping(fichier_tableau):
    ext = Path(fichier_tableau).suffix.lower()

    if ext == ".csv":
        df = pd.read_csv(fichier_tableau, dtype=str)
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(fichier_tableau, dtype=str)
    else:
        raise ValueError("Format non supporté.")

    df.columns = df.columns.str.strip()

    if "SAMPLE_ID" not in df.columns:
        raise ValueError("Colonne SAMPLE_ID absente")
    if "GLIMS" not in df.columns:
        raise ValueError("Colonne GLIMS absente")

    df["SAMPLE_ID"] = df["SAMPLE_ID"].astype(str).str.strip()
    df["GLIMS"] = df["GLIMS"].astype(str).str.strip()

    df = df[
        (df["SAMPLE_ID"] != "") &
        (df["GLIMS"] != "") &
        (df["SAMPLE_ID"].str.lower() != "nan") &
        (df["GLIMS"].str.lower() != "nan")
    ]

    return dict(zip(df["SAMPLE_ID"], df["GLIMS"]))


def extraire_base_suffixe(nom):
    """
    Exemples :
      Epi-1      -> ("Epi-1", "")
      Epi-1-A    -> ("Epi-1", "-A")
      Epi-1-B    -> ("Epi-1", "-B")
    """
    morceaux = nom.split("-")

    if len(morceaux) <= 2:
        return nom, ""

    base = "-".join(morceaux[:2])   # Epi-1
    suffixe = "-" + "-".join(morceaux[2:])  # -A ou -B

    return base, suffixe


def renommer_fichiers_dans_dossier(dossier, ancien_nom, nouveau_nom, dry_run=True):
    for item in dossier.iterdir():
        if not item.is_file():
            continue

        ancien_fichier = item.name

        if not ancien_fichier.startswith(ancien_nom):
            print(f"   [SKIP] {ancien_fichier}")
            continue

        nouveau_fichier = nouveau_nom + ancien_fichier[len(ancien_nom):]
        nouveau_chemin = dossier / nouveau_fichier

        if nouveau_chemin.exists():
            print(f"   [CONFLIT] {nouveau_fichier} existe déjà")
            continue

        print(f"   [FICHIER] {ancien_fichier} -> {nouveau_fichier}")

        if not dry_run:
            item.rename(nouveau_chemin)


def renommer_et_deplacer(dossier_parent, fichier_tableau, dossier_destination, dry_run=True):
    dossier_parent = Path(dossier_parent)
    dossier_destination = Path(dossier_destination)

    mapping = charger_mapping(fichier_tableau)

    if not dry_run:
        dossier_destination.mkdir(parents=True, exist_ok=True)

    for dossier in dossier_parent.iterdir():
        if not dossier.is_dir():
            continue

        ancien_nom = dossier.name
        base, suffixe = extraire_base_suffixe(ancien_nom)

        if base not in mapping:
            print(f"[SKIP] {ancien_nom} (base {base} non trouvée)")
            continue

        glims = mapping[base]

        if not glims or glims.lower() == "nan":
            print(f"[SKIP] {ancien_nom} GLIMS vide")
            continue

        nouveau_nom = glims + suffixe
        nouveau_dossier = dossier_destination / nouveau_nom

        print(f"\n[DOSSIER] {ancien_nom} -> {nouveau_nom}")

        #  renommer fichiers
        renommer_fichiers_dans_dossier(
            dossier, ancien_nom, nouveau_nom, dry_run
        )

        #  déplacer dossier
        if nouveau_dossier.exists():
            print(f"[CONFLIT DOSSIER] {nouveau_nom} existe déjà")
            continue

        print(f"[MOVE] {dossier} -> {nouveau_dossier}")

        if not dry_run:
            dossier.rename(nouveau_dossier)

    if dry_run:
        print("\n Mode test désactivé")


if __name__ == "__main__":
    dossier_parent = "/data/msarr/BD_genomes"
    fichier_tableau = "/data/msarr/Metadata_eq_rasigade.xlsx"
    dossier_destination = "/data/msarr/BD_BHRe"

    dry_run = False  # tester d'abord avec True à la place 

    renommer_et_deplacer(
        dossier_parent,
        fichier_tableau,
        dossier_destination,
        dry_run
    )

from pathlib import Path

import pandas as pd


"""
Rename and move genome sample folders using a SAMPLE_ID-to-GLIMS mapping table.

This script reads a mapping table containing at least two columns:

    SAMPLE_ID | GLIMS

It then scans a parent directory containing genome sample folders, converts
folder names based on the mapping, renames files inside each folder when their
names start with the old folder name, and finally moves the renamed folders to
a destination directory.

The script supports sample names with suffixes such as:

    Epi-1      -> base: Epi-1, suffix: ""
    Epi-1-A    -> base: Epi-1, suffix: "-A"
    Epi-1-B    -> base: Epi-1, suffix: "-B"

Example
-------
If the mapping table contains:

    SAMPLE_ID = Epi-1
    GLIMS     = 023064521501

Then:

    Epi-1-A -> 023064521501-A

Main workflow
-------------
1. Load the SAMPLE_ID-to-GLIMS mapping from CSV or Excel.
2. Scan all folders in the source directory.
3. Extract the base sample name and optional suffix.
4. Build the new folder name using the GLIMS identifier.
5. Rename files inside the folder if they start with the old folder name.
6. Move the folder to the destination directory.

Author
------
Mareme SARR
Bioinformatics Engineer
Hospices Civils de Lyon
"""


# ============================================================================
# Mapping utilities
# ============================================================================

def load_mapping(mapping_file):
    """
    Load the SAMPLE_ID-to-GLIMS mapping from a CSV or Excel file.

    The input table must contain the columns `SAMPLE_ID` and `GLIMS`.
    Empty values and textual missing values such as "nan" are removed.

    Parameters
    ----------
    mapping_file : str | pathlib.Path
        Path to the CSV, XLSX, or XLS mapping file.

    Returns
    -------
    dict[str, str]
        Dictionary mapping SAMPLE_ID values to GLIMS identifiers.

    Raises
    ------
    ValueError
        If the file format is unsupported or required columns are missing.
    """
    mapping_file = Path(mapping_file)
    extension = mapping_file.suffix.lower()

    if extension == ".csv":
        df = pd.read_csv(mapping_file, dtype=str)
    elif extension in [".xlsx", ".xls"]:
        df = pd.read_excel(mapping_file, dtype=str)
    else:
        raise ValueError("Unsupported file format. Use CSV, XLSX, or XLS.")

    df.columns = df.columns.str.strip()

    if "SAMPLE_ID" not in df.columns:
        raise ValueError("Missing required column: SAMPLE_ID")

    if "GLIMS" not in df.columns:
        raise ValueError("Missing required column: GLIMS")

    df["SAMPLE_ID"] = df["SAMPLE_ID"].astype(str).str.strip()
    df["GLIMS"] = df["GLIMS"].astype(str).str.strip()

    df = df[
        (df["SAMPLE_ID"] != "")
        & (df["GLIMS"] != "")
        & (df["SAMPLE_ID"].str.lower() != "nan")
        & (df["GLIMS"].str.lower() != "nan")
    ]

    return dict(zip(df["SAMPLE_ID"], df["GLIMS"]))


# ============================================================================
# Naming utilities
# ============================================================================

def extract_base_suffix(name):
    """
    Split a sample folder name into base sample name and suffix.

    The expected naming pattern is based on hyphen-separated identifiers.
    The first two parts define the base sample name, and all remaining parts
    are treated as the suffix.

    Examples
    --------
    Epi-1
        -> ("Epi-1", "")

    Epi-1-A
        -> ("Epi-1", "-A")

    Epi-1-B
        -> ("Epi-1", "-B")

    Parameters
    ----------
    name : str
        Original folder name.

    Returns
    -------
    tuple[str, str]
        Base sample name and suffix.
    """
    parts = name.split("-")

    if len(parts) <= 2:
        return name, ""

    base = "-".join(parts[:2])
    suffix = "-" + "-".join(parts[2:])

    return base, suffix


# ============================================================================
# File and folder operations
# ============================================================================

def rename_files_in_folder(folder, old_name, new_name, dry_run=True):
    """
    Rename files inside a folder when their names start with the old sample name.

    Only regular files are considered. Subdirectories are ignored.

    Parameters
    ----------
    folder : str | pathlib.Path
        Folder containing files to rename.

    old_name : str
        Prefix to replace in file names.

    new_name : str
        New prefix to use in file names.

    dry_run : bool, optional
        If True, only print planned operations without modifying files.
        If False, files are actually renamed.

    Returns
    -------
    None
    """
    folder = Path(folder)

    for item in folder.iterdir():
        if not item.is_file():
            continue

        old_file_name = item.name

        if not old_file_name.startswith(old_name):
            print(f"   [SKIP] {old_file_name}")
            continue

        new_file_name = new_name + old_file_name[len(old_name):]
        new_path = folder / new_file_name

        if new_path.exists():
            print(f"   [CONFLICT] {new_file_name} already exists")
            continue

        print(f"   [FILE] {old_file_name} -> {new_file_name}")

        if not dry_run:
            item.rename(new_path)


def rename_and_move_folders(
    source_parent,
    mapping_file,
    destination_parent,
    dry_run=True
):
    """
    Rename genome sample folders using a mapping table and move them elsewhere.

    For each folder in `source_parent`, the function extracts a base sample
    identifier, looks it up in the SAMPLE_ID-to-GLIMS mapping, builds the new
    folder name, renames matching files inside the folder, and moves the folder
    to `destination_parent`.

    Parameters
    ----------
    source_parent : str | pathlib.Path
        Directory containing the original sample folders.

    mapping_file : str | pathlib.Path
        CSV or Excel file containing SAMPLE_ID and GLIMS columns.

    destination_parent : str | pathlib.Path
        Directory where renamed folders will be moved.

    dry_run : bool, optional
        If True, print planned operations without modifying the filesystem.
        If False, perform the file renaming and folder moving.

    Returns
    -------
    None

    Raises
    ------
    FileNotFoundError
        If the source directory does not exist.

    ValueError
        If the mapping file is invalid or missing required columns.
    """
    source_parent = Path(source_parent)
    destination_parent = Path(destination_parent)

    if not source_parent.exists():
        raise FileNotFoundError(f"Source directory not found: {source_parent}")

    mapping = load_mapping(mapping_file)

    if not dry_run:
        destination_parent.mkdir(parents=True, exist_ok=True)

    for folder in source_parent.iterdir():
        if not folder.is_dir():
            continue

        old_name = folder.name
        base, suffix = extract_base_suffix(old_name)

        if base not in mapping:
            print(f"[SKIP] {old_name} - base {base} not found in mapping")
            continue

        glims = mapping[base]

        if not glims or glims.lower() == "nan":
            print(f"[SKIP] {old_name} - empty GLIMS value")
            continue

        new_name = glims + suffix
        new_folder = destination_parent / new_name

        print(f"\n[FOLDER] {old_name} -> {new_name}")

        rename_files_in_folder(
            folder=folder,
            old_name=old_name,
            new_name=new_name,
            dry_run=dry_run
        )

        if new_folder.exists():
            print(f"[FOLDER CONFLICT] {new_name} already exists")
            continue

        print(f"[MOVE] {folder} -> {new_folder}")

        if not dry_run:
            folder.rename(new_folder)

    if dry_run:
        print("\nDry-run mode enabled: no files or folders were modified.")


# ============================================================================
# Script entry point
# ============================================================================

if __name__ == "__main__":
    source_parent = "/data/msarr/BD_genomes"
    mapping_file = "/data/msarr/Metadata_eq_rasigade.xlsx"
    destination_parent = "/data/msarr/BD_BHRe"

    # Set to True first to preview all planned changes safely.
    # Set to False only after verifying the output.
    dry_run = False

    rename_and_move_folders(
        source_parent=source_parent,
        mapping_file=mapping_file,
        destination_parent=destination_parent,
        dry_run=dry_run
    )
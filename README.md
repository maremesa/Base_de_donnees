# 🧬 BHRe Genomic Database and Interactive Dashboard

## Overview

The BHRe Genomic Database project provides a complete infrastructure for storing,
processing, and exploring genomic and epidemiological data generated during the
surveillance of Highly Resistant Emerging Bacteria (BHRe).

The platform integrates:

- PostgreSQL database storage
- Clinical and epidemiological metadata
- Whole-genome sequencing results
- MLST typing
- AMRFinderPlus resistance profiling
- MOB-recon plasmid characterization
- QUAST assembly quality metrics
- Prokka genome annotation
- Interactive Streamlit dashboard

---

# Objectives

- Centralize genomic and clinical information.
- Support outbreak investigations.
- Track antimicrobial resistance determinants.
- Characterize plasmid dissemination.
- Facilitate genomic epidemiology analyses.
- Provide a user-friendly interface for microbiologists and bioinformaticians.

---

# System Architecture

Clinical Metadata
        |
        v
PostgreSQL Database
        |
        +-- MLST Results
        +-- AMRFinderPlus Results
        +-- MOB-recon Results
        +-- QUAST Metrics
        +-- Prokka Annotations
        |
        v
Streamlit Dashboard

---

# Database Tables

## samples

Stores sample-level information.

## clinical_data

Stores epidemiological and laboratory metadata.

## mlst_results

MLST typing results.

## amrfinder_hits

Antimicrobial resistance genes identified by AMRFinderPlus.

## mob_recon_results

Plasmid characterization results.

## quast_metrics

Assembly quality metrics.

## prokka_annotations

Genome annotation results.

## files

Indexed files associated with each sample.

## analysis_results

Generic key-value storage for parsed bioinformatics outputs.

---

# Bioinformatics Tools

## MLST

Provides:

- Species assignment
- Sequence Type (ST)
- Allele profiles

Expected file:

    sample/mlst/mlst.tsv

## AMRFinderPlus

Provides:

- Resistance genes
- Resistance classes
- Coverage
- Identity
- Closest reference sequence

Expected file:

    sample/amrfinder/amrfinder.tsv

## MOB-recon

Provides:

- Plasmid size
- Replicon type
- Relaxase type
- Mobility prediction
- Host range

Expected file:

    sample/mob_recon/mobtyper_results.txt

## QUAST

Provides:

- N50
- GC content
- Assembly size
- Number of contigs

Expected file:

    sample/quast/report.tsv

## Prokka

Provides:

- Gene names
- Product descriptions
- EC numbers
- COG annotations

Expected file:

    sample/prokka/*.tsv

---

# Directory Structure

```text
BD_BHRe/
│
├── 025138498903-02/
│   ├── amrfinder/
│   ├── mlst/
│   ├── mob_recon/
│   ├── prokka/
│   └── quast/
│
├── 025093175101-02/
│
└── ...
```

---

# Installation

## Clone Repository

```bash
git clone https://github.com/<username>/BHRe.git
cd BHRe
```

## Create Environment

```bash
python -m venv venv
source venv/bin/activate
```

## Install Dependencies

```bash
pip install pandas
pip install psycopg2-binary
pip install streamlit
pip install openpyxl
pip install pymupdf
```

---

# PostgreSQL Configuration

Example:

```python
DB_CONFIG = {
    "dbname": "bd_bhre",
    "user": "username",
    "host": "localhost",
    "port": 5432
}
```

---

# Import Workflow

Run imports in the following order:

```bash
python import_clinical_data.py
python import_mlst.py
python import_amrfinder.py
python import_mob_recon.py
python import_quast.py
python import_prokka.py
```

---

# Dashboard

Launch:

```bash
streamlit run dashboard_bhre.py
```

Default address:

http://10.7.81.30:8501

---

# Dashboard Features

## Overview

- Global statistics
- Species distribution
- Resistance gene frequencies
- Plasmid mobility distribution

## Sample Sheet

Displays:

- Clinical metadata
- MLST results
- Resistance genes
- Plasmids
- QUAST metrics
- Annotations
- Associated files

## Clinical Explorer

Filter by:

- Sample ID
- GLIMS
- Species
- Cluster
- Sampling type

## File Explorer

Preview:

- Text files
- FASTA files
- HTML reports
- PDF reports

---

# Authors

## Mareme SARR

Bioinformatics Engineer  
Hospices Civils de Lyon (HCL)
mareme.sarr@chu-lyon.fr


---

# Citation

If you use this project, please cite:

SARR M.
BHRe Genomic Database and Dashboard.
Hospices Civils de Lyon.

---

# License

This repository is intended for research, surveillance, and clinical microbiology activities.

Some data may contain sensitive clinical information and must not be redistributed without authorization.

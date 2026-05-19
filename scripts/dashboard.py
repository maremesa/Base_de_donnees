from pathlib import Path
import base64

import pandas as pd
import psycopg2
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Dashboard Genomique BHRe",
    page_icon="🧬",
    layout="wide",
)

DB_CONFIG = {
    "dbname": "bd_bhre",
    "user": "msarr",
    "host": "localhost",
    "port": 55432,
}

TEXT_EXTENSIONS = {
    ".txt", ".tsv", ".csv", ".log", ".fasta", ".fa", ".fna", ".ffn", ".faa",
    ".gff", ".gbk", ".fsa", ".tbl"
}
HTML_EXTENSIONS = {".html", ".htm"}
PDF_EXTENSIONS = {".pdf"}

MAX_FILE_PREVIEW_CHARS = 200000

HCL_LOGO_CANDIDATES = [
    Path("hcl_logo.png"),
    Path("HCL_logo.png"),
    Path("/data/msarr/hcl_logo.png"),
    Path("/data/msarr/HCL_logo.png"),
]

TAB_NAMES = [
    "Vue d’ensemble",
    "Fiche sample",
    "MLST",
    "AMR",
    "Plasmides",
    "QUAST",
    "Prokka",
    "Clinique",
    "Fichiers",
]

CLINICAL_ORDER_SQL = """
    CASE
        WHEN ordre_chronologique ~ '^[0-9]+$' THEN ordre_chronologique::int
        ELSE NULL
    END
"""


@st.cache_resource
def get_conn():
    return psycopg2.connect(**DB_CONFIG)


@st.cache_data(ttl=300)
def run_query(query: str, params=None) -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql(query, conn, params=params)


@st.cache_data(ttl=300)
def read_text_file(path_str: str, max_chars: int = MAX_FILE_PREVIEW_CHARS):
    path = Path(path_str)

    if not path.exists():
        return {"ok": False, "error": f"Fichier introuvable: {path_str}"}
    if not path.is_file():
        return {"ok": False, "error": f"Ce chemin n'est pas un fichier: {path_str}"}

    suffixes = "".join(path.suffixes).lower()
    if suffixes == ".fastq.gz":
        return {"ok": False, "error": "Prévisualisation non activée pour les fichiers compressés .fastq.gz"}

    if path.suffix.lower() not in TEXT_EXTENSIONS and suffixes not in {".fasta", ".fa", ".fna", ".ffn", ".faa"}:
        return {"ok": False, "error": f"Extension non prévisualisable en texte: {path.suffix}"}

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_chars + 1)

        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars]

        return {"ok": True, "content": content, "truncated": truncated}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@st.cache_data(ttl=300)
def read_html_file(path_str: str):
    path = Path(path_str)

    if not path.exists():
        return {"ok": False, "error": f"Fichier introuvable: {path_str}"}
    if not path.is_file():
        return {"ok": False, "error": f"Ce chemin n'est pas un fichier: {path_str}"}

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {"ok": True, "content": content}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@st.cache_data(ttl=300)
def get_logo_base64():
    for path in HCL_LOGO_CANDIDATES:
        if path.exists() and path.is_file():
            try:
                encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
                return {"ok": True, "content": encoded, "mime": "image/png"}
            except Exception as e:
                return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "Logo non trouvé"}


def fmt_int(x):
    try:
        return f"{int(x):,}".replace(",", " ")
    except Exception:
        return str(x)


def normalize_sample_ids(values):
    if not values:
        return []
    out = []
    seen = set()
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def clear_all_filters():
    st.session_state.reset_filters = True
    st.rerun()


def select_sample(sample_id: str, target_tab: str = "Fiche sample"):
    sample_id = str(sample_id).strip()
    st.session_state.selected_sample = sample_id
    st.session_state.active_tab = target_tab
    st.session_state.filtered_sample_ids = [sample_id]
    st.session_state.filter_origin = f"sample_id = {sample_id}"
    st.session_state.previous_selected_sample = sample_id
    st.rerun()


def apply_common_sample_filter(query, params, filtered_sample_ids, sample_column="sample_id"):
    if filtered_sample_ids:
        query += f" AND {sample_column} = ANY(%s)"
        params.append(filtered_sample_ids)
    return query, params


@st.cache_data(ttl=300)
def get_filtered_sample_ids(
    sample_search,
    sample_epi_filter,
    species_filter,
    gene_filter,
    prokka_gene_filter,
    mobility_filter,
    cluster_filter,
    type_prelevement_filter,
):
    clauses = []
    params = []
    labels = []

    if sample_search:
        clauses.append("base.sample_id ILIKE %s")
        params.append(f"%{sample_search}%")
        labels.append(f"sample_id ~ {sample_search}")

    if sample_epi_filter:
        clauses.append("""
            EXISTS (
                SELECT 1
                FROM clinical_data c
                WHERE c.sample_id = base.sample_id
                  AND TRIM(LOWER(c.sample_epi)) = TRIM(LOWER(%s))
            )
        """)
        params.append(sample_epi_filter)
        labels.append(f"sample_epi = {sample_epi_filter}")

    if species_filter:
        clauses.append("""
            EXISTS (
                SELECT 1
                FROM clinical_data c
                WHERE c.sample_id = base.sample_id
                  AND c.species ILIKE %s
            )
        """)
        params.append(f"%{species_filter}%")
        labels.append(f"espèce clinique ~ {species_filter}")

    if gene_filter:
        clauses.append("""
            EXISTS (
                SELECT 1
                FROM amrfinder_hits a
                WHERE a.sample_id = base.sample_id
                  AND a.gene_symbol IS NOT NULL
                  AND a.gene_symbol ILIKE %s
            )
        """)
        params.append(f"%{gene_filter}%")
        labels.append(f"AMR ~ {gene_filter}")

    if prokka_gene_filter:
        clauses.append("""
            EXISTS (
                SELECT 1
                FROM prokka_annotations p
                WHERE p.sample_id = base.sample_id
                  AND p.gene ILIKE %s
            )
        """)
        params.append(f"%{prokka_gene_filter}%")
        labels.append(f"Prokka ~ {prokka_gene_filter}")

    if mobility_filter != "Toutes":
        clauses.append("""
            EXISTS (
                SELECT 1
                FROM mob_recon_results mr
                WHERE mr.sample_id = base.sample_id
                  AND mr.predicted_mobility = %s
            )
        """)
        params.append(mobility_filter)
        labels.append(f"mobilité = {mobility_filter}")

    if cluster_filter:
        clauses.append("""
            EXISTS (
                SELECT 1
                FROM clinical_data c
                WHERE c.sample_id = base.sample_id
                  AND TRIM(LOWER(c.cluster_id)) = TRIM(LOWER(%s))
            )
        """)
        params.append(cluster_filter)
        labels.append(f"cluster = {cluster_filter}")

    if type_prelevement_filter:
        clauses.append("""
            EXISTS (
                SELECT 1
                FROM clinical_data c
                WHERE c.sample_id = base.sample_id
                  AND TRIM(LOWER(c.type_prelevement)) = TRIM(LOWER(%s))
            )
        """)
        params.append(type_prelevement_filter)
        labels.append(f"type_prelevement = {type_prelevement_filter}")

    query = """
        WITH base AS (
            SELECT sample_id FROM samples
            UNION
            SELECT sample_id FROM mlst_results
            UNION
            SELECT sample_id FROM amrfinder_hits
            UNION
            SELECT sample_id FROM mob_recon_results
            UNION
            SELECT sample_id FROM prokka_annotations
            UNION
            SELECT sample_id FROM quast_metrics
            UNION
            SELECT sample_id FROM files
            UNION
            SELECT sample_id FROM clinical_data
        )
        SELECT base.sample_id
        FROM base
        WHERE base.sample_id IS NOT NULL
          AND TRIM(base.sample_id) <> ''
    """

    if clauses:
        query += " AND " + " AND ".join(clauses)

    query += " ORDER BY base.sample_id"

    df = run_query(query, params)
    return normalize_sample_ids(df["sample_id"].tolist() if not df.empty else []), " ; ".join(labels)


def detect_auto_tab(
    sample_search,
    sample_epi_filter,
    species_filter,
    gene_filter,
    prokka_gene_filter,
    mobility_filter,
    cluster_filter,
    type_prelevement_filter,
):
    previous_selected_sample = st.session_state.get("previous_selected_sample", "")
    previous_sample_epi_filter = st.session_state.get("previous_sample_epi_filter", "")
    previous_species_filter = st.session_state.get("previous_species_filter", "")
    previous_gene_filter = st.session_state.get("previous_gene_filter", "")
    previous_prokka_gene_filter = st.session_state.get("previous_prokka_gene_filter", "")
    previous_mobility_filter = st.session_state.get("previous_mobility_filter", "Toutes")
    previous_cluster_filter = st.session_state.get("previous_cluster_filter", "")
    previous_type_prelevement_filter = st.session_state.get("previous_type_prelevement_filter", "")

    sample_changed = sample_search != previous_selected_sample
    sample_epi_changed = sample_epi_filter != previous_sample_epi_filter
    species_changed = species_filter != previous_species_filter
    gene_changed = gene_filter != previous_gene_filter
    prokka_changed = prokka_gene_filter != previous_prokka_gene_filter
    mobility_changed = mobility_filter != previous_mobility_filter
    cluster_changed = cluster_filter != previous_cluster_filter
    type_prelevement_changed = type_prelevement_filter != previous_type_prelevement_filter

    auto_tab = None

    if sample_changed and sample_search:
        auto_tab = "Fiche sample"
    elif sample_epi_changed and sample_epi_filter:
        auto_tab = "Clinique"
    elif species_changed and species_filter:
        auto_tab = "Clinique"
    elif gene_changed and gene_filter:
        auto_tab = "AMR"
    elif prokka_changed and prokka_gene_filter:
        auto_tab = "Prokka"
    elif mobility_changed and mobility_filter != "Toutes":
        auto_tab = "Plasmides"
    elif cluster_changed and cluster_filter:
        auto_tab = "Clinique"
    elif type_prelevement_changed and type_prelevement_filter:
        auto_tab = "Clinique"

    st.session_state.previous_selected_sample = sample_search
    st.session_state.previous_sample_epi_filter = sample_epi_filter
    st.session_state.previous_species_filter = species_filter
    st.session_state.previous_gene_filter = gene_filter
    st.session_state.previous_prokka_gene_filter = prokka_gene_filter
    st.session_state.previous_mobility_filter = mobility_filter
    st.session_state.previous_cluster_filter = cluster_filter
    st.session_state.previous_type_prelevement_filter = type_prelevement_filter

    return auto_tab


def show_sample_sheet(sample_id: str):
    st.markdown(f"## 🧪 Fiche sample — `{sample_id}`")

    df_sample = run_query("""
        SELECT sample_id, sample_path, glims_base, sample_suffix, created_at
        FROM samples
        WHERE sample_id = %s
        LIMIT 1
    """, [sample_id])

    df_sample_mlst = run_query("""
        SELECT species, st, sequence_file, alleles
        FROM mlst_results
        WHERE sample_id = %s
    """, [sample_id])

    df_sample_amr = run_query("""
        SELECT gene_symbol, class, subclass, method, identity, coverage, closest_sequence
        FROM amrfinder_hits
        WHERE sample_id = %s
          AND gene_symbol IS NOT NULL
        ORDER BY gene_symbol
    """, [sample_id])

    df_sample_plasmids = run_query("""
        SELECT plasmid_id, predicted_mobility, rep_type, relaxase_type, mpf_type, size, gc, host_range
        FROM mob_recon_results
        WHERE sample_id = %s
        ORDER BY plasmid_id
    """, [sample_id])

    df_sample_quast = run_query("""
        SELECT metric_name, metric_value
        FROM quast_metrics
        WHERE sample_id = %s
        ORDER BY metric_name
    """, [sample_id])

    df_sample_files = run_query("""
        SELECT file_id, subpath, filename, extension, size_bytes, relative_path, absolute_path
        FROM files
        WHERE sample_id = %s
        ORDER BY subpath, filename
        LIMIT 500
    """, [sample_id])

    df_sample_clinical = run_query(f"""
        SELECT
            sample_epi,
            sample_id,
            ipp,
            date_prelevement,
            species,
            type_prelevement,
            bmr_bhre,
            cluster_id,
            ordre_chronologique,
            flag_epitrack,
            flag_uhe,
            valid_genom,
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
        FROM clinical_data
        WHERE sample_id = %s
        ORDER BY {CLINICAL_ORDER_SQL} NULLS LAST, date_prelevement NULLS LAST
    """, [sample_id])

    if df_sample.empty:
        st.warning("Aucun sample trouvé dans la table samples.")
    else:
        st.dataframe(df_sample, use_container_width=True, hide_index=True)

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Lignes MLST", len(df_sample_mlst))
    k2.metric("Gènes AMR", len(df_sample_amr))
    k3.metric("Plasmides", len(df_sample_plasmids))
    k4.metric("Fichiers", len(df_sample_files))
    k5.metric("Clinique", len(df_sample_clinical))

    left, right = st.columns(2)

    with left:
        st.markdown("### MLST")
        st.dataframe(df_sample_mlst, use_container_width=True, hide_index=True)

        st.markdown("### Plasmides")
        st.dataframe(df_sample_plasmids, use_container_width=True, hide_index=True)

        st.markdown("### Données cliniques")
        st.dataframe(df_sample_clinical, use_container_width=True, hide_index=True)

    with right:
        st.markdown("### QUAST")
        st.dataframe(df_sample_quast, use_container_width=True, hide_index=True)

        st.markdown("### AMR")
        st.dataframe(df_sample_amr, use_container_width=True, hide_index=True)

    st.markdown("### Fichiers")
    if df_sample_files.empty:
        st.info("Aucun fichier.")
    else:
        st.dataframe(
            df_sample_files[["subpath", "filename", "extension", "size_bytes", "relative_path"]],
            use_container_width=True,
            hide_index=True
        )


st.markdown("""
<style>
:root {
    --blue-1: #0f4c81;
    --blue-2: #2f80c1;
    --border: #d9e7f4;
    --text: #12263a;
    --muted: #5f6b7a;
}

html, body, [class*="css"] {
    color: var(--text);
}

.stApp {
    background:
        radial-gradient(circle at top left, #e9f6ff 0%, #f7fbff 38%, #fff7f8 100%);
}

.block-container {
    padding-top: 1rem;
    padding-bottom: 5rem;
    max-width: 1500px;
}

.hero-box {
    background: linear-gradient(135deg, rgba(15,76,129,0.96), rgba(47,128,193,0.92));
    color: white;
    border-radius: 22px;
    padding: 1.4rem 1.4rem 1.2rem 1.4rem;
    border: 1px solid rgba(255,255,255,0.14);
    box-shadow: 0 10px 30px rgba(15,76,129,0.16);
    margin-bottom: 1rem;
}

.hero-title {
    font-size: 2rem;
    font-weight: 800;
    line-height: 1.1;
    margin-bottom: 0.3rem;
}

.hero-subtitle {
    font-size: 1rem;
    opacity: 0.92;
}

.info-box {
    background: rgba(255,255,255,0.86);
    border: 1px solid var(--border);
    border-left: 6px solid var(--blue-2);
    border-radius: 18px;
    padding: 1rem 1.2rem;
    margin-bottom: 1rem;
    box-shadow: 0 8px 24px rgba(17,38,58,0.05);
}

.section-card {
    background: rgba(255,255,255,0.78);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 1rem;
    box-shadow: 0 8px 24px rgba(17,38,58,0.05);
}

.footer-box {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(255,255,255,0.96);
    border-top: 1px solid var(--border);
    padding: 0.55rem 1rem;
    text-align: center;
    color: var(--muted);
    font-size: 0.88rem;
    z-index: 999;
    backdrop-filter: blur(6px);
}

h1, h2, h3 {
    color: var(--text);
}

[data-testid="stMetric"] {
    background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 14px;
    box-shadow: 0 6px 18px rgba(17,38,58,0.04);
}

[data-testid="stMetricValue"] {
    font-size: 1.55rem;
}

pre {
    white-space: pre-wrap !important;
    word-break: break-word !important;
}

.logo-caption {
    color: rgba(255,255,255,0.85);
    font-size: 0.85rem;
    margin-top: 0.2rem;
}

.contact-link {
    color: var(--blue-1);
    font-weight: 600;
    text-decoration: none;
}

.contact-link:hover {
    text-decoration: underline;
}
</style>
""", unsafe_allow_html=True)

DEFAULTS = {
    "selected_sample": "",
    "active_tab": "Vue d’ensemble",
    "sample_epi_filter": "",
    "species_filter": "",
    "gene_filter": "",
    "prokka_gene_filter": "",
    "mobility_filter": "Toutes",
    "cluster_filter": "",
    "type_prelevement_filter": "",
    "filtered_sample_ids": [],
    "filter_origin": "",
    "previous_selected_sample": "",
    "previous_sample_epi_filter": "",
    "previous_species_filter": "",
    "previous_gene_filter": "",
    "previous_prokka_gene_filter": "",
    "previous_mobility_filter": "Toutes",
    "previous_cluster_filter": "",
    "previous_type_prelevement_filter": "",
    "reset_filters": False,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

if st.session_state.reset_filters:
    st.session_state.selected_sample = ""
    st.session_state.sample_epi_filter = ""
    st.session_state.species_filter = ""
    st.session_state.gene_filter = ""
    st.session_state.prokka_gene_filter = ""
    st.session_state.mobility_filter = "Toutes"
    st.session_state.cluster_filter = ""
    st.session_state.type_prelevement_filter = ""
    st.session_state.filtered_sample_ids = []
    st.session_state.filter_origin = ""
    st.session_state.previous_selected_sample = ""
    st.session_state.previous_sample_epi_filter = ""
    st.session_state.previous_species_filter = ""
    st.session_state.previous_gene_filter = ""
    st.session_state.previous_prokka_gene_filter = ""
    st.session_state.previous_mobility_filter = "Toutes"
    st.session_state.previous_cluster_filter = ""
    st.session_state.previous_type_prelevement_filter = ""
    st.session_state.reset_filters = False

logo = get_logo_base64()

left_hero, right_hero = st.columns([4.5, 1.3])

with left_hero:
    st.markdown("""
    <div class="hero-box">
        <div class="hero-title">🧬 Dashboard Genomique BHRe</div>
        <div class="hero-subtitle">
            Exploration des cohortes, résistances, plasmides, qualité d’assemblage,
            annotations, clinique et fichiers bioinformatiques.
        </div>
    </div>
    """, unsafe_allow_html=True)

with right_hero:
    if logo.get("ok"):
        st.markdown(
            f"""
            <div class="hero-box" style="text-align:center; padding: 1rem;">
                <img src="data:{logo['mime']};base64,{logo['content']}" style="max-width:100%; max-height:100px; object-fit:contain;">
                <div class="logo-caption">HCL Lyon</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown("""
        <div class="hero-box" style="text-align:center;">
            <div style="font-size:2rem;">🏥</div>
            <div class="logo-caption">HCL Lyon</div>
        </div>
        """, unsafe_allow_html=True)

st.sidebar.header("Filtres")

sample_search_input = st.sidebar.text_input(
    "Sample ID",
    value=st.session_state.selected_sample,
    placeholder="ex: 023064521501-02"
)

sample_epi_filter = st.sidebar.text_input(
    "Sample_Epi",
    key="sample_epi_filter",
    placeholder="ex: Epi-1"
)

species_filter = st.sidebar.text_input(
    "Espèce",
    key="species_filter",
    placeholder="ex: cfreundii"
)

gene_filter = st.sidebar.text_input(
    "Gène AMR",
    key="gene_filter",
    placeholder="ex: blaCMY"
)

prokka_gene_filter = st.sidebar.text_input(
    "Gène Prokka",
    key="prokka_gene_filter",
    placeholder="ex: gyrB"
)

mobility_filter = st.sidebar.selectbox(
    "Mobilité plasmidique",
    ["Toutes", "conjugative", "mobilizable", "non-mobilizable"],
    key="mobility_filter"
)

cluster_filter = st.sidebar.text_input(
    "Cluster clinique",
    key="cluster_filter",
    placeholder="ex: 2"
)

type_prelevement_filter = st.sidebar.text_input(
    "Type prélèvement",
    key="type_prelevement_filter",
    placeholder="ex: BMR-BHR"
)

limit_rows = st.sidebar.slider("Nombre de lignes", 10, 500, 50, 10)

sample_search = sample_search_input.strip()
sample_epi_filter_clean = sample_epi_filter.strip()
species_filter_clean = species_filter.strip()
gene_filter_clean = gene_filter.strip()
prokka_gene_filter_clean = prokka_gene_filter.strip()
cluster_filter_clean = cluster_filter.strip()
type_prelevement_filter_clean = type_prelevement_filter.strip()

st.session_state.selected_sample = sample_search

filtered_sample_ids, filter_origin = get_filtered_sample_ids(
    sample_search=sample_search,
    sample_epi_filter=sample_epi_filter_clean,
    species_filter=species_filter_clean,
    gene_filter=gene_filter_clean,
    prokka_gene_filter=prokka_gene_filter_clean,
    mobility_filter=mobility_filter,
    cluster_filter=cluster_filter_clean,
    type_prelevement_filter=type_prelevement_filter_clean,
)

st.session_state.filtered_sample_ids = filtered_sample_ids
st.session_state.filter_origin = filter_origin

auto_tab = detect_auto_tab(
    sample_search=sample_search,
    sample_epi_filter=sample_epi_filter_clean,
    species_filter=species_filter_clean,
    gene_filter=gene_filter_clean,
    prokka_gene_filter=prokka_gene_filter_clean,
    mobility_filter=mobility_filter,
    cluster_filter=cluster_filter_clean,
    type_prelevement_filter=type_prelevement_filter_clean,
)

if auto_tab is not None and auto_tab != st.session_state.active_tab:
    st.session_state.active_tab = auto_tab
    st.rerun()

a1, a2, a3 = st.columns([1, 1, 5])

with a1:
    if st.button("🏠 Retour vue d’ensemble"):
        st.session_state.active_tab = "Vue d’ensemble"
        st.rerun()

with a2:
    if st.button("🧹 Effacer tous les filtres"):
        clear_all_filters()

if st.session_state.filtered_sample_ids:
    if len(st.session_state.filtered_sample_ids) == 1:
        st.info(
            f"Filtre actif : `{st.session_state.filtered_sample_ids[0]}`"
            + (f" — {st.session_state.filter_origin}" if st.session_state.filter_origin else "")
        )
    else:
        st.info(
            f"Filtre actif : {len(st.session_state.filtered_sample_ids)} souches"
            + (f" — {st.session_state.filter_origin}" if st.session_state.filter_origin else "")
        )
elif any([
    sample_search,
    sample_epi_filter_clean,
    species_filter_clean,
    gene_filter_clean,
    prokka_gene_filter_clean,
    mobility_filter != "Toutes",
    cluster_filter_clean,
    type_prelevement_filter_clean,
]):
    st.warning("Aucune souche ne correspond aux filtres actuels.")

kpi_samples = run_query("SELECT COUNT(*) AS n FROM samples")
kpi_files = run_query("SELECT COUNT(*) AS n FROM files")
kpi_mlst = run_query("SELECT COUNT(*) AS n FROM mlst_results")
kpi_amr = run_query("SELECT COUNT(*) AS n FROM amrfinder_hits")
kpi_plasmids = run_query("SELECT COUNT(*) AS n FROM mob_recon_results")
kpi_prokka = run_query("SELECT COUNT(*) AS n FROM prokka_annotations")
kpi_quast = run_query("SELECT COUNT(*) AS n FROM quast_metrics")
kpi_clinical = run_query("SELECT COUNT(*) AS n FROM clinical_data")

c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
c1.metric("Samples", fmt_int(kpi_samples.iloc[0, 0]))
c2.metric("Fichiers", fmt_int(kpi_files.iloc[0, 0]))
c3.metric("MLST", fmt_int(kpi_mlst.iloc[0, 0]))
c4.metric("AMR hits", fmt_int(kpi_amr.iloc[0, 0]))
c5.metric("Plasmides", fmt_int(kpi_plasmids.iloc[0, 0]))
c6.metric("Prokka", fmt_int(kpi_prokka.iloc[0, 0]))
c7.metric("QUAST", fmt_int(kpi_quast.iloc[0, 0]))
c8.metric("Clinique", fmt_int(kpi_clinical.iloc[0, 0]))

st.divider()

current_tab = st.radio(
    "Navigation",
    TAB_NAMES,
    horizontal=True,
    index=TAB_NAMES.index(st.session_state.active_tab),
    label_visibility="collapsed"
)

if current_tab != st.session_state.active_tab:
    st.session_state.active_tab = current_tab
    st.rerun()

current_tab = st.session_state.active_tab

if current_tab == "Vue d’ensemble":
    st.markdown("""
    <div class="info-box">
        <div style="font-size:1.05rem; font-weight:700; color:#0f4c81; margin-bottom:0.4rem;">
            À propos de cette base
        </div>
        <div>
            Cette base de données permet l’exploration des échantillons, des résultats de typage,
            des résistances, des plasmides, de la qualité d’assemblage, des annotations,
            des données cliniques et des fichiers associés.
        </div>
    </div>
    """, unsafe_allow_html=True)

    left, right = st.columns(2)

    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Top espèces")
        query = """
            SELECT species, COUNT(*) AS count
            FROM clinical_data
            WHERE species IS NOT NULL
              AND species <> ''
        """
        params = []
        query, params = apply_common_sample_filter(query, params, st.session_state.filtered_sample_ids, "sample_id")
        query += " GROUP BY species ORDER BY count DESC LIMIT 15"
        df_species = run_query(query, params)
        if df_species.empty:
            st.info("Aucune donnée.")
        else:
            st.bar_chart(df_species.set_index("species"))
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Mobilité plasmidique")
        query = """
            SELECT predicted_mobility, COUNT(*) AS count
            FROM mob_recon_results
            WHERE 1=1
        """
        params = []
        query, params = apply_common_sample_filter(query, params, st.session_state.filtered_sample_ids, "sample_id")
        query += " GROUP BY predicted_mobility ORDER BY count DESC"
        df_mob = run_query(query, params)
        if df_mob.empty:
            st.info("Aucune donnée.")
        else:
            st.bar_chart(df_mob.set_index("predicted_mobility"))
        st.markdown('</div>', unsafe_allow_html=True)

    left2, right2 = st.columns(2)

    with left2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Top gènes AMR")
        query = """
            SELECT gene_symbol, COUNT(*) AS count
            FROM amrfinder_hits
            WHERE gene_symbol IS NOT NULL
        """
        params = []
        query, params = apply_common_sample_filter(query, params, st.session_state.filtered_sample_ids, "sample_id")
        query += " GROUP BY gene_symbol ORDER BY count DESC LIMIT 20"
        df_top_genes = run_query(query, params)
        st.dataframe(df_top_genes, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with right2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Top clusters cliniques")
        query = """
            SELECT cluster_id, COUNT(*) AS count
            FROM clinical_data
            WHERE cluster_id IS NOT NULL
              AND cluster_id <> ''
        """
        params = []
        query, params = apply_common_sample_filter(query, params, st.session_state.filtered_sample_ids, "sample_id")
        query += " GROUP BY cluster_id ORDER BY count DESC LIMIT 20"
        df_clusters = run_query(query, params)
        st.dataframe(df_clusters, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

elif current_tab == "Fiche sample":
    if sample_search:
        show_sample_sheet(sample_search)
    elif len(st.session_state.filtered_sample_ids) == 1:
        show_sample_sheet(st.session_state.filtered_sample_ids[0])
    else:
        st.info("Saisis un Sample ID ou filtre jusqu’à obtenir une seule souche.")

elif current_tab == "MLST":
    st.subheader("Résultats MLST")

    query = """
        SELECT mlst_results.sample_id, mlst_results.species, mlst_results.st, mlst_results.sequence_file, mlst_results.alleles
        FROM mlst_results
        WHERE 1=1
    """
    params = []
    query, params = apply_common_sample_filter(
        query, params, st.session_state.filtered_sample_ids, "mlst_results.sample_id"
    )

    if species_filter_clean:
        query += """
            AND EXISTS (
                SELECT 1
                FROM clinical_data c
                WHERE c.sample_id = mlst_results.sample_id
                  AND c.species ILIKE %s
            )
        """
        params.append(f"%{species_filter_clean}%")

    if sample_epi_filter_clean:
        query += """
            AND EXISTS (
                SELECT 1
                FROM clinical_data c
                WHERE c.sample_id = mlst_results.sample_id
                  AND TRIM(LOWER(c.sample_epi)) = TRIM(LOWER(%s))
            )
        """
        params.append(sample_epi_filter_clean)

    if sample_search:
        query += " AND mlst_results.sample_id ILIKE %s"
        params.append(f"%{sample_search}%")

    query += " ORDER BY mlst_results.sample_id LIMIT %s"
    params.append(limit_rows)

    df_mlst = run_query(query, params)
    st.dataframe(df_mlst, use_container_width=True, hide_index=True)

elif current_tab == "AMR":
    st.subheader("Résultats AMR")

    query = """
        SELECT sample_id, gene_symbol, class, subclass, method, identity, coverage, closest_sequence
        FROM amrfinder_hits
        WHERE gene_symbol IS NOT NULL
    """
    params = []
    query, params = apply_common_sample_filter(query, params, st.session_state.filtered_sample_ids, "sample_id")

    if gene_filter_clean:
        query += " AND gene_symbol ILIKE %s"
        params.append(f"%{gene_filter_clean}%")

    if sample_search:
        query += " AND sample_id ILIKE %s"
        params.append(f"%{sample_search}%")

    query += " ORDER BY sample_id, gene_symbol LIMIT %s"
    params.append(limit_rows)

    df_amr = run_query(query, params)
    st.dataframe(df_amr, use_container_width=True, hide_index=True)

elif current_tab == "Plasmides":
    st.subheader("Résultats plasmidiques")

    query = """
        SELECT sample_id, plasmid_id, predicted_mobility, rep_type, relaxase_type, mpf_type, size, gc, host_range
        FROM mob_recon_results
        WHERE 1=1
    """
    params = []
    query, params = apply_common_sample_filter(query, params, st.session_state.filtered_sample_ids, "sample_id")

    if mobility_filter != "Toutes":
        query += " AND predicted_mobility = %s"
        params.append(mobility_filter)

    if sample_search:
        query += " AND sample_id ILIKE %s"
        params.append(f"%{sample_search}%")

    query += " ORDER BY sample_id, plasmid_id LIMIT %s"
    params.append(limit_rows)

    df_plasmids = run_query(query, params)
    st.dataframe(df_plasmids, use_container_width=True, hide_index=True)

elif current_tab == "QUAST":
    st.subheader("Métriques QUAST")

    left, right = st.columns([1.15, 0.85])

    with left:
        query = """
            SELECT sample_id, metric_name, metric_value
            FROM quast_metrics
            WHERE 1=1
        """
        params = []
        query, params = apply_common_sample_filter(query, params, st.session_state.filtered_sample_ids, "sample_id")

        if sample_search:
            query += " AND sample_id ILIKE %s"
            params.append(f"%{sample_search}%")

        query += " ORDER BY sample_id, metric_name LIMIT %s"
        params.append(limit_rows)

        df_quast = run_query(query, params)
        st.dataframe(df_quast, use_container_width=True, hide_index=True)

    with right:
        st.markdown("#### Top N50")
        query = """
            SELECT sample_id, metric_value::numeric AS n50
            FROM quast_metrics
            WHERE metric_name = 'N50'
        """
        params = []
        query, params = apply_common_sample_filter(query, params, st.session_state.filtered_sample_ids, "sample_id")

        if sample_search:
            query += " AND sample_id ILIKE %s"
            params.append(f"%{sample_search}%")

        query += " ORDER BY metric_value::numeric DESC LIMIT 20"

        df_n50 = run_query(query, params)
        st.dataframe(df_n50, use_container_width=True, hide_index=True)

elif current_tab == "Prokka":
    st.subheader("Annotations Prokka")

    query = """
        SELECT sample_id, locus_tag, ftype, gene, product, length_bp
        FROM prokka_annotations
        WHERE 1=1
    """
    params = []
    query, params = apply_common_sample_filter(query, params, st.session_state.filtered_sample_ids, "sample_id")

    if prokka_gene_filter_clean:
        query += " AND gene ILIKE %s"
        params.append(f"%{prokka_gene_filter_clean}%")

    if sample_search:
        query += " AND sample_id ILIKE %s"
        params.append(f"%{sample_search}%")

    query += " ORDER BY sample_id, locus_tag LIMIT %s"
    params.append(limit_rows)

    df_prokka = run_query(query, params)
    st.dataframe(df_prokka, use_container_width=True, hide_index=True)

elif current_tab == "Clinique":
    st.subheader("Données cliniques")

    query = f"""
        SELECT
            sample_epi,
            sample_id,
            ipp,
            date_prelevement,
            species,
            type_prelevement,
            bmr_bhre,
            cluster_id,
            ordre_chronologique,
            flag_epitrack,
            flag_uhe,
            valid_genom,
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
        FROM clinical_data
        WHERE 1=1
    """
    params = []
    query, params = apply_common_sample_filter(query, params, st.session_state.filtered_sample_ids, "sample_id")

    if sample_epi_filter_clean:
        query += " AND TRIM(LOWER(sample_epi)) = TRIM(LOWER(%s))"
        params.append(sample_epi_filter_clean)

    if species_filter_clean:
        query += " AND species ILIKE %s"
        params.append(f"%{species_filter_clean}%")

    if cluster_filter_clean:
        query += " AND TRIM(LOWER(cluster_id)) = TRIM(LOWER(%s))"
        params.append(cluster_filter_clean)

    if type_prelevement_filter_clean:
        query += " AND TRIM(LOWER(type_prelevement)) = TRIM(LOWER(%s))"
        params.append(type_prelevement_filter_clean)

    if sample_search:
        query += " AND sample_id ILIKE %s"
        params.append(f"%{sample_search}%")

    query += f"""
        ORDER BY
            cluster_id NULLS LAST,
            type_prelevement NULLS LAST,
            sample_id,
            {CLINICAL_ORDER_SQL} NULLS LAST,
            date_prelevement NULLS LAST
        LIMIT %s
    """
    params.append(limit_rows)

    df_clinical = run_query(query, params)

    if df_clinical.empty:
        st.warning("Aucune donnée clinique trouvée avec les filtres actuels.")
    else:
        st.dataframe(df_clinical, use_container_width=True, hide_index=True)

        st.markdown("### Répartition des clusters")
        df_clusters = (
            df_clinical["cluster_id"]
            .fillna("Non renseigné")
            .replace("", "Non renseigné")
            .value_counts()
            .reset_index()
        )
        df_clusters.columns = ["cluster_id", "count"]
        st.bar_chart(df_clusters.set_index("cluster_id"))

elif current_tab == "Fichiers":
    st.subheader("Explorateur de fichiers")

    query = """
        SELECT file_id, sample_id, subfolder, subpath, filename, extension, size_bytes, relative_path, absolute_path
        FROM files
        WHERE 1=1
    """
    params = []
    query, params = apply_common_sample_filter(query, params, st.session_state.filtered_sample_ids, "sample_id")

    if sample_search:
        query += " AND sample_id ILIKE %s"
        params.append(f"%{sample_search}%")

    query += " ORDER BY sample_id, subpath, filename LIMIT %s"
    params.append(limit_rows)

    df_files = run_query(query, params)

    left, right = st.columns([1.1, 1])

    with left:
        st.markdown("#### Liste des fichiers")
        if df_files.empty:
            st.info("Aucun fichier.")
            selected_file_label = ""
            file_map = {}
        else:
            st.dataframe(
                df_files[["sample_id", "subpath", "filename", "extension", "size_bytes", "relative_path"]],
                use_container_width=True,
                hide_index=True
            )

            file_options = []
            file_map = {}

            for _, row in df_files.iterrows():
                label = f"{row['sample_id']} | {row['subpath']} | {row['filename']}"
                file_options.append(label)
                file_map[label] = row

            selected_file_label = st.selectbox(
                "Choisir un fichier à afficher",
                options=[""] + file_options,
                index=0
            )

    with right:
        st.markdown("#### Prévisualisation")

        if not df_files.empty and selected_file_label:
            row = file_map[selected_file_label]
            abs_path = row["absolute_path"]
            filename = row["filename"]
            file_sample_id = row["sample_id"]
            extension = (row["extension"] or "").lower() if pd.notna(row["extension"]) else ""
            suffixes = "".join(Path(abs_path).suffixes).lower()

            if st.button("🧬 Ouvrir la fiche sample", key=f"open_sample_{row['file_id']}"):
                select_sample(file_sample_id, "Fiche sample")

            st.caption(f"Sample lié : `{file_sample_id}`")
            st.write(f"**Fichier** : `{filename}`")
            st.write(f"**Chemin relatif** : `{row['relative_path']}`")
            st.write(f"**Chemin absolu** : `{abs_path}`")
            st.write(f"**Taille** : `{fmt_int(row['size_bytes'])}` octets")

            if extension in TEXT_EXTENSIONS or suffixes in {".fasta", ".fa", ".fna", ".ffn", ".faa"}:
                preview = read_text_file(abs_path)
                if preview["ok"]:
                    if preview.get("truncated"):
                        st.warning("Fichier tronqué pour prévisualisation.")
                    st.code(preview["content"], language="text")
                else:
                    st.info(preview["error"])

            elif extension in HTML_EXTENSIONS:
                preview = read_html_file(abs_path)
                if preview["ok"]:
                    components.html(preview["content"], height=800, scrolling=True)
                else:
                    st.info(preview["error"])

            elif extension in PDF_EXTENSIONS:
                st.markdown("### 📄 PDF")
                try:
                    with open(abs_path, "rb") as f:
                        st.download_button(
                            "📥 Télécharger",
                            data=f,
                            file_name=filename,
                            mime="application/pdf"
                        )
                except Exception as e:
                    st.error(f"Erreur téléchargement: {e}")

                st.markdown("#### Aperçu")
                try:
                    import fitz

                    doc = fitz.open(abs_path)
                    page = doc[0]
                    pix = page.get_pixmap()
                    img_bytes = pix.tobytes("png")
                    st.image(img_bytes, caption="Première page du PDF")
                except Exception:
                    st.info("Aperçu non disponible. Installe PyMuPDF pour afficher la première page.")
            else:
                st.info(f"Prévisualisation non disponible pour l’extension `{extension or 'inconnue'}`.")
        else:
            st.info("Sélectionne un fichier dans la liste pour afficher son contenu.")

st.markdown("""
<div class="footer-box">
    Base BHRe — créée par <strong>Mareme SARR</strong>, ingénieure bioinformatique aux HCL —
    Contact : <a class="contact-link" href="mailto:mareme.sarr@chu-lyon.fr">mareme.sarr@chu-lyon.fr</a> —
    Jean-Philippe Rasigade :
    <a class="contact-link" href="mailto:jean-philippe.rasigade@chu-lyon.fr">jean-philippe.rasigade@chu-lyon.fr</a>
</div>
""", unsafe_allow_html=True)

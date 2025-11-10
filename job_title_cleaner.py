import pandas as pd
import numpy as np
import json
import re
import streamlit as st
from sentence_transformers import SentenceTransformer, util

# --- Fast, lightweight model ---
model = SentenceTransformer('all-MiniLM-L6-v2')  # 6x faster than all-mpnet-base-v2
SIMILARITY_THRESHOLD = 0.75

# --- Load mapping ---
def load_mapping(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# --- Text utilities ---
def capitalize_title(title):
    words = str(title).split()
    corrected = []
    for w in words:
        if w.isupper():
            corrected.append(w)
        else:
            parts = re.split(r'(-)', w)
            corrected_parts = [p.capitalize() if p != '-' else p for p in parts]
            corrected.append(''.join(corrected_parts))
    return ' '.join(corrected)

def normalize_title(title):
    return str(title).lower().strip()

def map_title(raw_title, mapping, known_titles_embed, known_keys):
    normalized = normalize_title(raw_title)
    if normalized in mapping:
        return mapping[normalized], False

    raw_emb = model.encode(normalized, normalize_embeddings=True)
    similarities = util.cos_sim(raw_emb, known_titles_embed)[0].cpu().numpy()
    best_idx = int(np.argmax(similarities))
    best_score = similarities[best_idx]

    if best_score >= SIMILARITY_THRESHOLD:
        return mapping[known_keys[best_idx]], False
    else:
        return 'Unknown - Needs Review', True

# --- Main cleaning function ---
def process_excel(input_path, output_path, mapping_path, dept_json_output,
                  target_column, sheet_name=None, return_df=False, return_changes=False):

    # --- Load data ---
    if input_path.endswith('.xlsx'):
        if sheet_name:
            df = pd.read_excel(input_path, sheet_name=sheet_name)
        else:
            df = pd.read_excel(input_path)
    else:
        df = pd.read_csv(input_path)

    if target_column not in df.columns:
        raise ValueError(f"Column '{target_column}' not found in file.")

    # --- Load canonical mapping ---
    mapping = load_mapping(mapping_path)
    known_keys = list(mapping.keys())
    known_embeddings = model.encode(known_keys, normalize_embeddings=True)

    standardized, unknowns = [], set()

    # --- Progress bar setup ---
    st.markdown("""
        <style>
        /* Default progress bar style */
        div[data-testid="stProgress"] div[role="progressbar"] {
            background-color: #0078ff;
            height: 1rem;
            border-radius: 10px;
        }
        /* Change to green when full */
        div[data-testid="stProgress"][aria-valuenow="100"] div[role="progressbar"] {
            background-color: #2ecc71 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    total_rows = len(df)
    progress_bar = st.progress(0)
    status_text = st.empty()

    # --- Row-wise cleaning with periodic progress updates ---
    for i, raw in enumerate(df[target_column]):
        mapped, is_unknown = map_title(str(raw), mapping, known_embeddings, known_keys)
        standardized.append(capitalize_title(mapped))
        if is_unknown:
            unknowns.add(normalize_title(raw))

        # Update progress every 100 rows
        if (i + 1) % 100 == 0 or (i + 1) == total_rows:
            percent = int(((i + 1) / total_rows) * 100)
            progress_bar.progress(percent)
            status_text.text(f"Processing row {i + 1:,} of {total_rows:,}...")

    # --- Final completion state ---
    progress_bar.progress(100)
    status_text.markdown("<span style='color:#2ecc71;font-weight:600;'>Processing complete ✅</span>", unsafe_allow_html=True)

    # --- Save cleaned output ---
    normalized_col = f"Normalized {target_column}"
    df[normalized_col] = standardized
    df.to_excel(output_path, index=False)

    # --- Identify top 5 changed rows for preview (sampled for speed) ---
    invalid_values = ["-", "nan", "none", "null", "na", ""]
    filtered_df = df[
        (~df[target_column].astype(str).str.lower().isin(invalid_values))
        & (~df[normalized_col].astype(str).str.lower().isin(invalid_values))
    ]

    # Sample subset for similarity comparison (faster)
    sample_df = filtered_df.sample(min(len(filtered_df), 500), random_state=42)
    raw_list = sample_df[target_column].astype(str).tolist()
    norm_list = sample_df[normalized_col].astype(str).tolist()

    raw_embeds = model.encode(raw_list, normalize_embeddings=True)
    norm_embeds = model.encode(norm_list, normalize_embeddings=True)
    similarity_scores = util.cos_sim(raw_embeds, norm_embeds).diagonal().cpu().numpy()
    sample_df["Change Score"] = 1 - similarity_scores

    # Select top 5 most changed (exclude score in final)
    major_changes = (
        sample_df[[target_column, normalized_col, "Change Score"]]
        .sort_values("Change Score", ascending=False)
        .head(5)
        .drop(columns=["Change Score"])
        .reset_index(drop=True)
    )

    # --- Optional Department grouping ---
    if 'Department*' in df.columns:
        grouped = (
            df[df[normalized_col] != 'Unknown - Needs Review']
            .groupby('Department*')[normalized_col]
            .unique()
            .apply(sorted)
            .to_dict()
        )
        with open(dept_json_output, 'w', encoding='utf-8') as f:
            json.dump(grouped, f, indent=4)

    # --- Return results ---
    if return_df:
        if return_changes:
            return df, major_changes
        return df

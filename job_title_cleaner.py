import pandas as pd
import numpy as np
import json
import re
import streamlit as st
from sentence_transformers import SentenceTransformer, util

# --- Model & threshold ---
model = SentenceTransformer('all-mpnet-base-v2')  # high-accuracy model
SIMILARITY_THRESHOLD = 0.75
AUTO_LEARN_THRESHOLD = 0.88   # high confidence threshold for auto-add to JSON

# --- Load & Save Mapping ---
def load_mapping(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_mapping(mapping, json_path):
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=4, ensure_ascii=False)

# --- Text Formatting ---
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

# --- Mapping Logic (with auto-learn) ---
def map_title(raw_title, mapping, known_titles_embed, known_keys, mapping_path):
    normalized = normalize_title(raw_title)

    # 1. Direct match
    if normalized in mapping:
        return mapping[normalized], False

    # 2. Semantic similarity match
    raw_emb = model.encode(normalized, normalize_embeddings=True)
    similarities = util.cos_sim(raw_emb, known_titles_embed)[0].cpu().numpy()

    best_idx = int(np.argmax(similarities))
    best_score = similarities[best_idx]
    best_key = known_keys[best_idx]
    best_canonical = mapping[best_key]

    # 3. High-confidence match → auto-learn variant
    if best_score >= AUTO_LEARN_THRESHOLD:
        mapping[normalized] = best_canonical  # add the spelling variant
        save_mapping(mapping, mapping_path)    # update JSON permanently
        return best_canonical, False

    # 4. Normal threshold → accept but don't learn
    if best_score >= SIMILARITY_THRESHOLD:
        return best_canonical, False

    # 5. Unknown
    return 'Unknown - Needs Review', True

# --- Main Processing ---
def process_excel(input_path, output_path, mapping_path, dept_json_output,
                  target_column, sheet_name=None,
                  return_df=False, return_changes=False):

    # --- Load file ---
    if input_path.endswith('.xlsx'):
        df = pd.read_excel(input_path, sheet_name=sheet_name) if sheet_name else pd.read_excel(input_path)
    else:
        df = pd.read_csv(input_path)

    if target_column not in df.columns:
        raise ValueError(f"Column '{target_column}' not found in file.")

    # --- Load mapping ---
    mapping = load_mapping(mapping_path)
    known_keys = list(mapping.keys())
    known_embeddings = model.encode(known_keys, normalize_embeddings=True)

    standardized = []
    unknowns = set()

    # --- Streamlit Progress UI ---
    total_rows = len(df)
    progress_bar = st.progress(0)
    status_text = st.empty()

    # --- Process Rows ---
    for i, raw in enumerate(df[target_column]):
        mapped, is_unknown = map_title(
            str(raw),
            mapping,
            known_embeddings,
            known_keys,
            mapping_path
        )

        standardized.append(capitalize_title(mapped))
        if is_unknown:
            unknowns.add(normalize_title(raw))

        # Update progress
        if (i + 1) % 100 == 0 or i + 1 == total_rows:
            percent = int(((i + 1) / total_rows) * 100)
            progress_bar.progress(percent)
            status_text.text(f"Processing row {i + 1} of {total_rows}...")

    progress_bar.progress(100)
    status_text.text("Processing complete!")

    # --- Add normalized column ---
    normalized_col = f"Normalized {target_column}"
    df[normalized_col] = standardized
    df.to_excel(output_path, index=False)

    # --- Identify big changes ---
    invalid_values = ["-", "nan", "none", "null", "na", ""]
    filtered_df = df[
        (~df[target_column].astype(str).str.lower().isin(invalid_values)) &
        (~df[normalized_col].astype(str).str.lower().isin(invalid_values))
    ]

    sample_df = filtered_df.sample(min(len(filtered_df), 400), random_state=42)
    raw_list = sample_df[target_column].astype(str).tolist()
    norm_list = sample_df[normalized_col].astype(str).tolist()

    raw_embeds = model.encode(raw_list, normalize_embeddings=True)
    norm_embeds = model.encode(norm_list, normalize_embeddings=True)
    similarity_scores = util.cos_sim(raw_embeds, norm_embeds).diagonal().cpu().numpy()

    sample_df["Change Score"] = 1 - similarity_scores
    major_changes = (
        sample_df[[target_column, normalized_col, "Change Score"]]
        .sort_values("Change Score", ascending=False)
        .head(5)
        .drop(columns=["Change Score"])
        .reset_index(drop=True)
    )
    major_changes.index = major_changes.index + 1

    # --- Return results ---
    if return_df:
        return (df, major_changes) if return_changes else df

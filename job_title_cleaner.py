import pandas as pd
import numpy as np
import json
import re
import streamlit as st
from sentence_transformers import SentenceTransformer, util
from rapidfuzz import process

# =========================================================
# FAST RULE-BASED CORRECTIONS (No ML spell corrector)
# =========================================================

COMMON_CORRECTIONS = {
    r"\bengg\b": "engineer",
    r"\basst\b": "assistant",
    r"\bhk\b": "housekeeping",
    r"\bsupv\b": "supervisor",
    r"\bsuprv\b": "supervisor",
    r"\bexec\b": "executive",
    r"carpendar|carpendry|carpentry": "carpenter",
    r"techinician|technicion": "technician",
    r"superviser": "supervisor",
}

def rule_correct(text):
    t = text.lower().strip()
    for wrong, right in COMMON_CORRECTIONS.items():
        t = re.sub(wrong, right, t)
    return t


# =========================================================
# FUZZY MATCHING
# =========================================================
def fuzzy_correct(text, known_keys):
    match = process.extractOne(text, known_keys)
    if match and match[1] >= 85:
        return match[0]
    return text


# =========================================================
# SEMANTIC MODEL (GTE for speed)
# =========================================================
model = SentenceTransformer("thenlper/gte-large")

SIMILARITY_THRESHOLD = 0.75
AUTO_LEARN_THRESHOLD = 0.88


# =========================================================
# LOAD/SAVE MAPPING
# =========================================================
def load_mapping(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_mapping(mapping, json_path):
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=4, ensure_ascii=False)


# =========================================================
# TEXT FORMATTER
# =========================================================
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


def normalize_title(t):
    return str(t).lower().strip()


# =========================================================
# PREPROCESS INPUT TEXT
# =========================================================
def preprocess_title(raw, known_keys):
    t = str(raw).lower().strip()

    # 1. Rule-based
    t = rule_correct(t)

    # 2. Fuzzy
    t = fuzzy_correct(t, known_keys)

    return t


# =========================================================
# MAIN LOGIC FOR ONE TITLE
# =========================================================
def map_title(raw_title, mapping, known_embeddings, known_keys, mapping_path):
    cleaned = preprocess_title(raw_title, known_keys)
    normalized = normalize_title(cleaned)

    # Direct match
    if normalized in mapping:
        return mapping[normalized], False

    # Semantic match
    raw_emb = model.encode(normalized, normalize_embeddings=True)
    sims = util.cos_sim(raw_emb, known_embeddings)[0].cpu().numpy()

    best_idx = int(np.argmax(sims))
    best_score = sims[best_idx]
    best_key = known_keys[best_idx]
    best_canonical = mapping[best_key]

    if best_score >= AUTO_LEARN_THRESHOLD:
        mapping[normalized] = best_canonical
        save_mapping(mapping, mapping_path)
        return best_canonical, False

    if best_score >= SIMILARITY_THRESHOLD:
        return best_canonical, False

    return "Unknown - Needs Review", True


# =========================================================
# MAIN PROCESS FUNCTION USED BY STREAMLIT APP
# =========================================================
def process_excel(input_path, output_path, mapping_path, dept_json_output,
                  target_column, sheet_name=None,
                  return_df=False, return_changes=False):

    # Read input file
    if input_path.endswith('.xlsx'):
        df = pd.read_excel(input_path, sheet_name=sheet_name) if sheet_name else pd.read_excel(input_path)
    else:
        df = pd.read_csv(input_path)

    if target_column not in df.columns:
        raise ValueError(f"Column '{target_column}' not found.")

    # Load mapping
    mapping = load_mapping(mapping_path)
    known_keys = list(mapping.keys())
    known_embeddings = model.encode(known_keys, normalize_embeddings=True)

    standardized = []
    unknowns = set()

    total = len(df)
    bar = st.progress(0)
    status = st.empty()

    for i, raw in enumerate(df[target_column]):
        mapped, is_unknown = map_title(
            str(raw), mapping, known_embeddings, known_keys, mapping_path
        )
        final_title = capitalize_title(mapped)
        standardized.append(final_title)

        if is_unknown:
            unknowns.add(normalize_title(raw))

        # Progress update
        if (i + 1) % 50 == 0 or i + 1 == total:
            pct = int(((i + 1) / total) * 100)
            bar.progress(pct)
            status.text(f"Processing {i+1}/{total}...")

    bar.progress(100)
    status.text("Processing complete!")

    # Add new column
    col_normalized = f"Normalized {target_column}"
    df[col_normalized] = standardized

    df.to_excel(output_path, index=False)

    # Prepare change-tracking dataframe
    changes_df = pd.DataFrame({
        "Original": df[target_column],
        "Normalized": df[col_normalized]
    })

    # Return correctly (fixes the unpacking error)
    if return_df and return_changes:
        return df, changes_df

    if return_df:
        return df

    return None

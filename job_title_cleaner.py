import pandas as pd
import numpy as np
import json
import re
import streamlit as st
from sentence_transformers import SentenceTransformer, util
from rapidfuzz import process

# =========================================================
# RULE-BASED CORRECTIONS
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
# SEMANTIC MODEL
# =========================================================
model = SentenceTransformer("thenlper/gte-large")

SIMILARITY_THRESHOLD = 0.75
AUTO_LEARN_THRESHOLD = 0.88


# =========================================================
# LOAD / SAVE MAPPING
# =========================================================
def load_mapping(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_mapping(mapping, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=4, ensure_ascii=False)


# =========================================================
# CLEANING HELPERS
# =========================================================
def normalize_title(t):
    return str(t).lower().strip()

def capitalize_title(title):
    words = str(title).split()
    fixed = []
    for w in words:
        if w.isupper():
            fixed.append(w)
        else:
            parts = re.split(r"(-)", w)
            parts = [p.capitalize() if p != "-" else p for p in parts]
            fixed.append("".join(parts))
    return " ".join(fixed)


# =========================================================
# PREPROCESSING PIPELINE
# =========================================================
def preprocess_title(raw, known_keys):
    t = str(raw).lower().strip()
    t = rule_correct(t)
    t = fuzzy_correct(t, known_keys)
    return t


# =========================================================
# SEMANTIC MATCHING
# =========================================================
def map_title(raw, mapping, known_embeddings, known_keys, mapping_path):

    cleaned = preprocess_title(raw, known_keys)
    normalized = normalize_title(cleaned)

    # Direct mapping
    if normalized in mapping:
        return mapping[normalized], False

    # Semantic matching
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
# MAIN PROCESSOR FOR STREAMLIT
# =========================================================
def process_excel(input_path, output_path, mapping_path, dept_json_output,
                  target_column, sheet_name=None,
                  return_df=False, return_changes=False):

    # Load file
    if input_path.endswith(".xlsx"):
        df = pd.read_excel(input_path, sheet_name=sheet_name) if sheet_name else pd.read_excel(input_path)
    else:
        df = pd.read_csv(input_path)

    if target_column not in df.columns:
        raise ValueError(f"Column '{target_column}' not found")

    mapping = load_mapping(mapping_path)
    known_keys = list(mapping.keys())
    known_embeddings = model.encode(known_keys, normalize_embeddings=True)

    standardized = []
    total = len(df)

    progress = st.progress(0)
    text = st.empty()

    for i, raw in enumerate(df[target_column]):

        # -----------------------------------------
        # 1️⃣ HANDLE NULL / EMPTY / PLACEHOLDER VALUES
        # -----------------------------------------
        if raw is None or str(raw).strip() in ["", "-", "_", "nan", "none", "NULL", "N/A", "na", "NaN"]:
            standardized.append("")   # leave empty
            continue

        # -----------------------------------------
        # 2️⃣ PROCESS VALID TITLES
        # -----------------------------------------
        mapped, is_unknown = map_title(
            str(raw), mapping, known_embeddings, known_keys, mapping_path
        )

        standardized.append(capitalize_title(mapped))

        # UI progress
        if (i + 1) % 50 == 0 or i + 1 == total:
            pct = int(((i + 1) / total) * 100)
            progress.progress(pct)
            text.text(f"Processing {i+1}/{total}...")

    progress.progress(100)
    text.text("Processing complete!")

    # Create output column
    new_col = f"Normalized {target_column}"
    df[new_col] = standardized

    df.to_excel(output_path, index=False)

    # Changes DataFrame
    changes_df = pd.DataFrame({
        "Original": df[target_column],
        "Normalized": df[new_col]
    })

    # Correct return behavior for Streamlit
    if return_df and return_changes:
        return df, changes_df
    if return_df:
        return df

    return None

import pandas as pd
import numpy as np
import json
import re
import streamlit as st
from sentence_transformers import SentenceTransformer, util
from rapidfuzz import process
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# =========================================================
#  SPELL CORRECTION MODELS
# =========================================================

# ML Spell Corrector (HuggingFace)
tokenizer_sc = AutoTokenizer.from_pretrained("oliverguhr/spelling-correction-english-base")
model_sc = AutoModelForSeq2SeqLM.from_pretrained("oliverguhr/spelling-correction-english-base")

def ml_spell_correct(text):
    try:
        input_ids = tokenizer_sc.encode(text, return_tensors="pt")
        output = model_sc.generate(input_ids, max_length=60)
        corrected = tokenizer_sc.decode(output[0], skip_special_tokens=True)
        return corrected
    except Exception:
        return text

# Rule-based corrections
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

# Fuzzy correction (RapidFuzz)
def fuzzy_correct(text, known_keys):
    match = process.extractOne(text, known_keys)
    if match and match[1] >= 85:
        return match[0]  # high confidence
    return text

# =========================================================
# SEMANTIC MODEL (GTE)
# =========================================================
# Switched from 'all-mpnet-base-v2' to GTE:
model = SentenceTransformer("thenlper/gte-large")

SIMILARITY_THRESHOLD = 0.75
AUTO_LEARN_THRESHOLD = 0.88   # high confidence threshold for auto-add to JSON

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
# TEXT FORMATTING
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

def normalize_title(title):
    return str(title).lower().strip()

# =========================================================
# PREPROCESS + SEMANTIC MAPPING
# =========================================================
def preprocess_title(raw, known_keys):
    t = str(raw).lower().strip()

    # 1️⃣ Rule-based corrections
    t = rule_correct(t)

    # 2️⃣ ML spell correction
    t = ml_spell_correct(t)

    # 3️⃣ Fuzzy correction vs known keys
    t = fuzzy_correct(t, known_keys)

    return t

def map_title(raw_title, mapping, known_titles_embed, known_keys, mapping_path):
    # --- Preprocess with rules + ML + fuzzy ---
    cleaned = preprocess_title(raw_title, known_keys)
    normalized = normalize_title(cleaned)

    # 1. Direct match
    if normalized in mapping:
        return mapping[normalized], False

    # 2. Semantic similarity match with GTE
    raw_emb = model.encode(normalized, normalize_embeddings=True)
    similarities = util.cos_sim(raw_emb, known_titles_embed)[0].cpu().numpy()

    best_idx = int(np.argmax(similarities))
    best_score = similarities[best_idx]
    best_key = known_keys[best_idx]
    best_canonical = mapping[best_key]

    # 3. High-confidence match → auto-add to JSON
    if best_score >= AUTO_LEARN_THRESHOLD:
        mapping[normalized] = best_canonical
        save_mapping(mapping, mapping_path)
        return best_canonical, False

    # 4. Acceptable match only (no auto-learn)
    if best_score >= SIMILARITY_THRESHOLD:
        return best_canonical, False

    # 5. Unknown case
    return "Unknown - Needs Review", True

# =========================================================
# MAIN PROCESSOR
# =========================================================
def process_excel(input_path, output_path, mapping_path, dept_json_output,
                  target_column, sheet_name=None,
                  return_df=False, return_changes=False):

    # Load Excel/CSV
    if input_path.endswith('.xlsx'):
        df = pd.read_excel(input_path, sheet_name=sheet_name) if sheet_name else pd.read_excel(input_path)
    else:
        df = pd.read_csv(input_path)

    if target_column not in df.columns:
        raise ValueError(f"Column '{target_column}' not found in file.")

    # Load mapping
    mapping = load_mapping(mapping_path)
    known_keys = list(mapping.keys())
    known_embeddings = model.encode(known_keys, normalize_embeddings=True)

    standardized = []
    unknowns = set()

    total_rows = len(df)
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, raw in enumerate(df[target_column]):
        mapped, is_unknown = map_title(
            str(raw), mapping, known_embeddings, known_keys, mapping_path
        )
        standardized.append(capitalize_title(mapped))

        if is_unknown:
            unknowns.add(normalize_title(raw))

        # Progress bar
        if (i + 1) % 100 == 0 or i + 1 == total_rows:
            percent = int(((i + 1) / total_rows) * 100)
            progress_bar.progress(percent)
            status_text.text(f"Processing row {i + 1} of {total_rows}...")

    progress_bar.progress(100)
    status_text.text("Processing complete!")

    # Add normalized column
    normalized_col = f"Normalized {target_column}"
    df[normalized_col] = standardized
    df.to_excel(output_path, index=False)

    # (Optional) change analysis logic could be added back here if you want

    if return_df:
        return df

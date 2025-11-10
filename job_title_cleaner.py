import pandas as pd
import numpy as np
import json
import re
from sentence_transformers import SentenceTransformer, util

# Load model only once globally
model = SentenceTransformer('all-mpnet-base-v2')
SIMILARITY_THRESHOLD = 0.75  # cosine similarity threshold

# --- Load job title mapping ---
def load_mapping(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# --- Capitalize each word properly ---
def capitalize_title(title):
    words = title.split()
    corrected_words = []
    for word in words:
        if word.isupper():
            corrected_words.append(word)
        else:
            parts = re.split(r'(-)', word)
            corrected_parts = [p.capitalize() if p != '-' else p for p in parts]
            corrected_words.append(''.join(corrected_parts))
    return ' '.join(corrected_words)

# --- Normalize text ---
def normalize_title(title):
    return str(title).lower().strip()

# --- Map job title using dictionary and embeddings ---
def map_title(raw_title, mapping, known_titles_embed):
    normalized = normalize_title(raw_title)

    if normalized in mapping:
        return mapping[normalized], False

    raw_emb = model.encode(normalized, normalize_embeddings=True)
    known_keys = list(mapping.keys())
    similarities = util.cos_sim(raw_emb, known_titles_embed)[0].cpu().numpy()
    best_match_idx = int(np.argmax(similarities))
    best_score = similarities[best_match_idx]

    if best_score >= SIMILARITY_THRESHOLD:
        matched_title = mapping[known_keys[best_match_idx]]
        return matched_title, False
    else:
        return 'Unknown - Needs Review', True

# --- Main Processing Function ---
def process_excel(input_path, output_path, mapping_path, dept_json_output, target_column):
    df = pd.read_excel(input_path) if input_path.endswith('.xlsx') else pd.read_csv(input_path)

    # Ensure the selected column exists
    if target_column not in df.columns:
        raise ValueError(f"Column '{target_column}' not found in file.")

    # Load and prepare mapping
    mapping = load_mapping(mapping_path)
    known_keys = list(mapping.keys())
    known_embeddings = model.encode(known_keys, normalize_embeddings=True)

    standard_titles = []
    unknown_titles = set()

    for raw_title in df[target_column]:
        mapped_title, is_unknown = map_title(str(raw_title), mapping, known_embeddings)
        standard_titles.append(capitalize_title(mapped_title))
        if is_unknown:
            unknown_titles.add(normalize_title(str(raw_title)))

    df[f"{target_column}_Cleaned"] = standard_titles

    # Save cleaned file
    df.to_excel(output_path, index=False)

    # Department grouping only if 'Department*' exists
    if 'Department*' in df.columns:
        grouped = (
            df[df[f"{target_column}_Cleaned"] != 'Unknown - Needs Review']
            .groupby('Department*')[f"{target_column}_Cleaned"]
            .unique()
            .apply(sorted)
            .to_dict()
        )
        with open(dept_json_output, 'w', encoding='utf-8') as f:
            json.dump(grouped, f, indent=4)

    # Print unknowns for debugging
    if unknown_titles:
        print(f"Unknown titles found in {target_column}:")
        for title in sorted(unknown_titles):
            print(" -", title)

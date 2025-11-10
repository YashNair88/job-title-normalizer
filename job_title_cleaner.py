import pandas as pd
import numpy as np
import json
import re
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-mpnet-base-v2')
SIMILARITY_THRESHOLD = 0.75

def load_mapping(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

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

def map_title(raw_title, mapping, known_titles_embed):
    normalized = normalize_title(raw_title)
    if normalized in mapping:
        return mapping[normalized], False

    raw_emb = model.encode(normalized, normalize_embeddings=True)
    known_keys = list(mapping.keys())
    similarities = util.cos_sim(raw_emb, known_titles_embed)[0].cpu().numpy()
    best_idx = int(np.argmax(similarities))
    best_score = similarities[best_idx]

    if best_score >= SIMILARITY_THRESHOLD:
        return mapping[known_keys[best_idx]], False
    else:
        return 'Unknown - Needs Review', True

def process_excel(input_path, output_path, mapping_path, dept_json_output,
                  target_column, sheet_name=None, return_df=False, return_changes=False):
    # Load file
    if input_path.endswith('.xlsx'):
        if sheet_name:
            df = pd.read_excel(input_path, sheet_name=sheet_name)
        else:
            df = pd.read_excel(input_path)
    else:
        df = pd.read_csv(input_path)

    if target_column not in df.columns:
        raise ValueError(f"Column '{target_column}' not found.")

    mapping = load_mapping(mapping_path)
    known_keys = list(mapping.keys())
    known_embeddings = model.encode(known_keys, normalize_embeddings=True)

    standardized, unknowns = [], set()

    for raw in df[target_column]:
        mapped, is_unknown = map_title(str(raw), mapping, known_embeddings)
        standardized.append(capitalize_title(mapped))
        if is_unknown:
            unknowns.add(normalize_title(raw))

    normalized_col = f"Normalized {target_column}"
    df[normalized_col] = standardized
    df.to_excel(output_path, index=False)

    # Compute similarity scores for difference detection
    raw_embeds = model.encode(df[target_column].astype(str).tolist(), normalize_embeddings=True)
    norm_embeds = model.encode(df[normalized_col].astype(str).tolist(), normalize_embeddings=True)
    similarity_scores = util.cos_sim(raw_embeds, norm_embeds).diagonal().cpu().numpy()
    df["Change Score"] = 1 - similarity_scores  # Higher = more changed

    # Identify major changes
    major_changes = (
        df[[target_column, normalized_col, "Change Score"]]
        .sort_values("Change Score", ascending=False)
        .head(5)
    )

    # Optional department grouping
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

    if return_df:
        if return_changes:
            return df, major_changes
        return df

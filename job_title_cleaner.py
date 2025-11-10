import pandas as pd
import numpy as np
import json
import re
from sentence_transformers import SentenceTransformer, util

# Global model
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
    best_match_idx = int(np.argmax(similarities))
    best_score = similarities[best_match_idx]

    if best_score >= SIMILARITY_THRESHOLD:
        matched = mapping[known_keys[best_match_idx]]
        return matched, False
    else:
        return 'Unknown - Needs Review', True

def process_excel(input_path, output_path, mapping_path, dept_json_output, target_column, sheet_name=None):
    # Load data
    if input_path.endswith('.xlsx'):
        if sheet_name:
            df = pd.read_excel(input_path, sheet_name=sheet_name)
        else:
            xls = pd.ExcelFile(input_path)
            df = pd.read_excel(xls, xls.sheet_names[0])
    else:
        df = pd.read_csv(input_path)

    if target_column not in df.columns:
        raise ValueError(f"Column '{target_column}' not found in {sheet_name or 'file'}.")

    # Load mapping
    mapping = load_mapping(mapping_path)
    keys = list(mapping.keys())
    known_embeds = model.encode(keys, normalize_embeddings=True)

    standardized, unknowns = [], set()

    for raw in df[target_column]:
        mapped, is_unknown = map_title(str(raw), mapping, known_embeds)
        standardized.append(capitalize_title(mapped))
        if is_unknown:
            unknowns.add(normalize_title(raw))

    df[f"{target_column}_Cleaned"] = standardized
    df.to_excel(output_path, index=False)

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

    if unknowns:
        print(f"Unknown entries found in column '{target_column}' ({len(unknowns)} values).")

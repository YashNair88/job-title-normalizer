
# Imports
import pandas as pd
import numpy as np
import json
import re
from sentence_transformers import SentenceTransformer, util
from sklearn.metrics.pairwise import cosine_similarity

# Load model
model = SentenceTransformer('all-mpnet-base-v2')

# --- Config ---
EXCEL_INPUT_PATH = '/content/master_CLMS_data.xlsx'   # path to input file
EXCEL_OUTPUT_PATH = '/content/employee_data_cleaned.xlsx'  # path to output file
JSON_MAPPING_PATH = '/content/canonical_mapping_raw.json'  # path to json mapping file
DEPT_JSON_OUTPUT_PATH = '/content/department_title_mapping.json'  # output grouped json
SIMILARITY_THRESHOLD = 0.75  # cosine similarity threshold to auto-map

# --- Load job title mapping ---
def load_mapping(json_path):
    with open(json_path, 'r') as f:
        return json.load(f)

# --- Save updated mapping ---
def save_mapping(mapping, json_path):
    with open(json_path, 'w') as f:
        json.dump(mapping, f, indent=4)

# --- Clean and normalize job title for matching ---
def normalize_title(title):
    return title.lower().strip()

# --- Capitalize each word properly ---
def capitalize_title(title):
    # Split by spaces to preserve multi-word structure
    words = title.split()
    corrected_words = []
    for word in words:
        # Preserve acronyms or all-uppercase tokens
        if word.isupper():
            corrected_words.append(word)
        else:
            # For hyphenated words, capitalize each part properly
            parts = re.split(r'(-)', word)  # keep hyphen separators
            corrected_parts = [p.capitalize() if p != '-' else p for p in parts]
            corrected_words.append(''.join(corrected_parts))
    return ' '.join(corrected_words)

# --- Get SBERT embedding ---
def get_embedding(text):
    return model.encode(text, normalize_embeddings=True)

# --- Map job title using dictionary and embeddings ---
def map_title(raw_title, mapping, known_titles_embed):
    normalized = normalize_title(raw_title)

    # Direct dictionary match
    if normalized in mapping:
        return mapping[normalized], False

    # Else use embeddings
    raw_embed = get_embedding(normalized)
    known_keys = list(mapping.keys())
    similarities = util.cos_sim(raw_embed, known_titles_embed)[0].cpu().numpy()
    best_match_idx = int(np.argmax(similarities))
    best_score = similarities[best_match_idx]

    if best_score >= SIMILARITY_THRESHOLD:
        matched_title = mapping[known_keys[best_match_idx]]
        return matched_title, False
    else:
        return 'Unknown - Needs Review', True

# --- Main Processing Function ---
def process_excel(input_path, output_path, mapping_path, dept_json_output):
    df = pd.read_excel(input_path, sheet_name='BC', header=0)

    # Load and prepare mapping
    mapping = load_mapping(mapping_path)
    known_keys = list(mapping.keys())
    known_embeddings = model.encode(known_keys, normalize_embeddings=True)

    # Process job titles
    standard_titles = []
    unknown_titles = set()

    for raw_title in df['Designation*']:
        mapped_title, is_unknown = map_title(str(raw_title), mapping, known_embeddings)
        standard_titles.append(capitalize_title(mapped_title))
        if is_unknown:
            unknown_titles.add(normalize_title(str(raw_title)))

    # Update DataFrame
    df['Standardized Title'] = standard_titles

    # Save cleaned data
    df.to_excel(output_path, index=False)
    print(f"Cleaned Excel saved to {output_path}")

    # --- Create Department-wise JSON mapping ---
    grouped = (
        df[df['Standardized Title'] != 'Unknown - Needs Review']
        .groupby('Department*')['Standardized Title']
        .unique()
        .apply(sorted)
        .to_dict()
    )

    with open(dept_json_output, 'w') as f:
        json.dump(grouped, f, indent=4)

    print(f"\nDepartment-Title JSON saved to {dept_json_output}")

    # Show unknowns
    if unknown_titles:
        print("\nUnknown titles found (needs manual review):")
        for title in sorted(unknown_titles):
            print(" -", title)

# --- Run the cleaner ---
# process_excel(EXCEL_INPUT_PATH, EXCEL_OUTPUT_PATH, JSON_MAPPING_PATH, DEPT_JSON_OUTPUT_PATH)
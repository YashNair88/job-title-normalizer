import streamlit as st
import pandas as pd
import tempfile
import os
from job_title_cleaner import process_excel

st.set_page_config(page_title="Job Title Normalizer", page_icon="🧹", layout="centered")

# Custom CSS to fix title visibility on all devices and themes
st.markdown("""
    <style>
        /* Base page */
        .stApp {
            background-color: #f8fafc;
            font-family: 'Inter', sans-serif;
            padding-top: 2rem;
        }

        /* Hide Streamlit dark header bar */
        header[data-testid="stHeader"] {
            background: transparent !important;
        }

        /* Title */
        h1 {
            color: #111111 !important;
            text-align: center !important;
            font-size: clamp(1.6rem, 4vw, 2.4rem) !important;
            font-weight: 700 !important;
            margin-bottom: 0.4rem !important;
        }

        /* Subtitle */
        .subtitle {
            text-align: center;
            font-size: clamp(0.95rem, 2.5vw, 1.1rem);
            color: #333333;
            margin-bottom: 2rem;
        }

        /* File uploader box */
        section[data-testid="stFileUploader"] > label div {
            color: #222222 !important; /* <-- makes “Upload Excel or CSV file” visible */
            font-weight: 500 !important;
            font-size: 1rem !important;
            margin-bottom: 0.3rem !important;
        }

        .stFileUploader {
            border: 2px dashed #0078ff !important;
            border-radius: 10px !important;
            background-color: #ffffff !important;
            padding: 1.2rem !important;
            margin-bottom: 1.2rem;
        }

        /* Buttons */
        .stDownloadButton button, .stButton button {
            background-color: #0078ff !important;
            color: white !important;
            border-radius: 8px !important;
            padding: 0.7rem 1.4rem !important;
            font-weight: 600 !important;
            border: none !important;
        }

        /* Info box */
        .stAlert {
            border-radius: 10px !important;
            padding: 1rem !important;
        }

        /* Mobile optimization */
        @media (max-width: 600px) {
            .stApp {
                padding: 1rem 0.5rem;
            }
            h1 {
                font-size: 1.6rem !important;
            }
        }
    </style>
""", unsafe_allow_html=True)



# Title & subtitle (these will now be visible everywhere)
st.markdown("<h1>Job Title Normalizer</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtext'>Upload your Excel or CSV file to automatically clean and standardize job titles.</p>", unsafe_allow_html=True)



uploaded_file = st.file_uploader("📤 Upload Excel or CSV file", type=["xlsx", "csv"])

if uploaded_file is not None:
    with st.spinner("Processing your file... Please wait ⏳"):
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
            tmp.write(uploaded_file.read())
            temp_input = tmp.name

        # Create output paths
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx').name
        dept_json_output = tempfile.NamedTemporaryFile(delete=False, suffix='.json').name

        # Run the cleaner
        process_excel(
            input_path=temp_input,
            output_path=temp_output,
            mapping_path="canonical_mapping_raw.json",
            dept_json_output=dept_json_output
        )

        st.success("✅ Cleaning complete! Click below to download your cleaned file.")

        with open(temp_output, "rb") as f:
            st.download_button(
                label="📥 Download Cleaned Excel File",
                data=f,
                file_name="Cleaned_Employee_Data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        # st.markdown("---")
        # st.info("✨ Job titles have been standardized using AI-based matching and your canonical dictionary.")
else:
    st.info("Please upload a file to begin.")

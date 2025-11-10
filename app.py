import streamlit as st
import pandas as pd
import tempfile
import os
from job_title_cleaner import process_excel

st.set_page_config(page_title="Job Title Normalizer", page_icon="🧹", layout="centered")

st.title("🧹 Job Title Normalizer")
st.markdown("Upload your Excel or CSV file to automatically clean and standardize job titles.")

st.markdown("""
    <style>
        .stApp {
            background-color: #f7f9fc;
            font-family: 'Inter', sans-serif;
        }
        .stDownloadButton button {
            background-color: #0078ff !important;
            color: white !important;
            border-radius: 8px;
            padding: 10px 18px;
            font-weight: 600;
        }
        .stFileUploader {
            border: 2px dashed #0078ff;
            border-radius: 10px;
            background-color: #ffffff;
            padding: 15px;
        }
    </style>
""", unsafe_allow_html=True)

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

        st.success("✅ Cleaning complete! Click below to download your cleaned file:")

        with open(temp_output, "rb") as f:
            st.download_button(
                label="📥 Download Cleaned Excel File",
                data=f,
                file_name="Cleaned_Employee_Data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        st.markdown("---")
        # st.info("✨ Job titles have been standardized using AI-based matching and your canonical dictionary.")
else:
    st.info("Please upload a file to begin.")

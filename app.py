import streamlit as st
import pandas as pd
import tempfile
import os
from job_title_cleaner import process_excel

st.set_page_config(page_title="Job Title Normalizer", page_icon="🧹", layout="centered")

# ---- Custom CSS ----
st.markdown("""
<style>
.stApp { background-color:#f8fafc; font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
.block-container { max-width: 820px; margin: 0 auto; padding-top: 2rem; }
header[data-testid="stHeader"]{ background:transparent !important; }
.jt-title { color:#111; text-align:center; font-size:clamp(1.6rem,4vw,2.4rem); font-weight:700; margin-bottom:0.35rem; }
.jt-subtitle { text-align:center; color:#333; font-size:clamp(.95rem,2.4vw,1.1rem); margin-bottom:1.25rem; }
.jt-uplabel { display:block; color:#222; font-weight:600; margin:.25rem 0 .4rem; }
.stFileUploader { border:2px dashed #0078ff !important; border-radius:10px !important; background:#fff !important; padding:1.1rem !important; }
[data-testid="stFileUploader"] label, section[data-testid="stFileUploader"] > label > div { color:#222 !important; opacity:1 !important; }
.stDownloadButton button, .stButton button{ background:#0078ff !important; color:#fff !important; border:none !important; border-radius:8px !important; padding:.7rem 1.3rem !important; font-weight:600 !important; }
.stAlert { border-radius:10px !important; }
@media (max-width: 600px){ .block-container{ padding-top:1.2rem; } .stFileUploader{ padding:.85rem !important; } }
</style>
""", unsafe_allow_html=True)

# ---- Header ----
st.markdown("<h1 class='jt-title'>Job Title Normalizer</h1>", unsafe_allow_html=True)
st.markdown("<p class='jt-subtitle'>Upload your Excel or CSV file, choose the sheet and column you want to standardize, and download the cleaned version.</p>", unsafe_allow_html=True)

# ---- Upload ----
# st.markdown("<label class='jt-uplabel'>Upload Excel or CSV file</label>", unsafe_allow_html=True)
uploaded_file = st.file_uploader(label="", type=["xlsx", "csv"], label_visibility="collapsed")

if uploaded_file is not None:
    try:
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()

        # --- For Excel files ---
        if file_ext == ".xlsx":
            excel_file = pd.ExcelFile(uploaded_file)
            sheet_names = excel_file.sheet_names
            selected_sheet = st.selectbox("Select a sheet to process:", options=sheet_names)

            if selected_sheet:
                df = pd.read_excel(excel_file, sheet_name=selected_sheet)
                # st.success(f"Loaded sheet: {selected_sheet}")
                columns = list(df.columns)
                selected_column = st.selectbox("Select the column to clean:", options=columns)

                if st.button("Clean Selected Column"):
                    with st.spinner("Processing your file... Please wait ⏳"):
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                            uploaded_file.seek(0)
                            tmp.write(uploaded_file.getbuffer())
                            temp_input = tmp.name

                        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx').name
                        dept_json_output = tempfile.NamedTemporaryFile(delete=False, suffix='.json').name

                        process_excel(
                            input_path=temp_input,
                            output_path=temp_output,
                            mapping_path="canonical_mapping_raw.json",
                            dept_json_output=dept_json_output,
                            target_column=selected_column,
                            sheet_name=selected_sheet
                        )

                        st.success(f"Cleaning complete for sheet '{selected_sheet}' and column '{selected_column}'.")

                        with open(temp_output, "rb") as f:
                            st.download_button(
                                label="Download Cleaned Excel File",
                                data=f,
                                file_name="Cleaned_Employee_Data.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )

                        # st.info("Job titles have been standardized using AI-based matching and your canonical dictionary.")

        # --- For CSV files ---
        elif file_ext == ".csv":
            df = pd.read_csv(uploaded_file)
            columns = list(df.columns)
            selected_column = st.selectbox("Select the column to clean:", options=columns)

            if st.button("Clean Selected Column"):
                with st.spinner("Processing your file... Please wait ⏳"):
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                        tmp.write(uploaded_file.getbuffer())
                        temp_input = tmp.name

                    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx').name
                    dept_json_output = tempfile.NamedTemporaryFile(delete=False, suffix='.json').name

                    process_excel(
                        input_path=temp_input,
                        output_path=temp_output,
                        mapping_path="canonical_mapping_raw.json",
                        dept_json_output=dept_json_output,
                        target_column=selected_column,
                        sheet_name=None
                    )

                    st.success(f"Cleaning complete for column '{selected_column}'.")

                    with open(temp_output, "rb") as f:
                        st.download_button(
                            label="Download Cleaned Excel File",
                            data=f,
                            file_name="Cleaned_Employee_Data.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

                    st.info("Job titles have been standardized using AI-based matching and the canonical dictionary.")

        else:
            st.error("Unsupported file format. Please upload a .xlsx or .csv file.")

    except Exception as e:
        st.error(f"Error processing file: {e}")
else:
    st.info("Please upload a file to begin.")

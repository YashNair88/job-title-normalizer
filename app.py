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
.block-container { max-width: 900px; margin: 0 auto; padding-top: 2rem; }
header[data-testid="stHeader"]{ background:transparent !important; }
.jt-title { color:#111; text-align:center; font-size:clamp(1.6rem,4vw,2.4rem); font-weight:700; margin-bottom:0.35rem; }
.jt-subtitle { text-align:center; color:#333; font-size:clamp(.95rem,2.4vw,1.1rem); margin-bottom:1.25rem; }
.stFileUploader { border:2px dashed #0078ff !important; border-radius:10px !important; background:#fff !important; padding:1.1rem !important; }
[data-testid="stFileUploader"] label, section[data-testid="stFileUploader"] > label > div { color:#222 !important; opacity:1 !important; }
.stDownloadButton button, .stButton button{ background:#0078ff !important; color:#fff !important; border:none !important; border-radius:8px !important; padding:.7rem 1.3rem !important; font-weight:600 !important; }
.stAlert { border-radius:10px !important; }
@media (max-width: 600px){ .block-container{ padding-top:1.2rem; } .stFileUploader{ padding:.85rem !important; } }
</style>
""", unsafe_allow_html=True)

# ---- Header ----
st.markdown(
    "<div style='text-align:center; font-size:28px; font-weight:700; color:#111; margin:0 0 6px;'>Job Title Normalizer</div>",
    unsafe_allow_html=True
)
st.markdown(
    "<p style='text-align:center; font-size:16px; color:#333; margin:0 0 18px;'>Clean and standardize job titles instantly from your Excel or CSV file.</p>",
    unsafe_allow_html=True
)

# ---- Session State ----
if "cleaned_df" not in st.session_state:
    st.session_state.cleaned_df = None
    st.session_state.major_changes_df = None
    st.session_state.temp_output = None
    st.session_state.cleaning_done = False

# ---- Upload ----
uploaded_file = st.file_uploader(label="", type=["xlsx", "csv"], label_visibility="collapsed")

if uploaded_file is not None:
    try:
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()

        if file_ext == ".xlsx":
            excel_file = pd.ExcelFile(uploaded_file)
            sheet_names = excel_file.sheet_names
            selected_sheet = st.selectbox("Select a sheet to process:", options=sheet_names)

            if selected_sheet:
                df = pd.read_excel(excel_file, sheet_name=selected_sheet)
                columns = list(df.columns)
                selected_column = st.selectbox("Select the column to clean:", options=columns)

                if selected_column:
                    st.subheader("Selected Column")
                    preview_df = df[[selected_column]].head().copy()
                    preview_df.index = range(1, len(preview_df) + 1)
                    preview_df.index.name = ""
                    st.dataframe(preview_df)

                if st.button("Clean Selected Column"):
                    with st.spinner("Processing your file... Please wait ⏳"):
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                            uploaded_file.seek(0)
                            tmp.write(uploaded_file.getbuffer())
                            temp_input = tmp.name

                        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx').name
                        dept_json_output = tempfile.NamedTemporaryFile(delete=False, suffix='.json').name

                        cleaned_df, major_changes_df = process_excel(
                            input_path=temp_input,
                            output_path=temp_output,
                            mapping_path="canonical_mapping.json",
                            dept_json_output=dept_json_output,
                            target_column=selected_column,
                            sheet_name=selected_sheet,
                            return_df=True,
                            return_changes=True
                        )

                        st.session_state.cleaned_df = cleaned_df
                        st.session_state.major_changes_df = major_changes_df
                        st.session_state.temp_output = temp_output
                        st.session_state.cleaning_done = True
                        st.success(f"Cleaning complete for column '{selected_column}'.")

        elif file_ext == ".csv":
            df = pd.read_csv(uploaded_file)
            columns = list(df.columns)
            selected_column = st.selectbox("Select the column to clean:", options=columns)

            if selected_column:
                st.subheader("Selected Column")
                st.dataframe(df[[selected_column]].head())

            if st.button("Clean Selected Column"):
                with st.spinner("Processing your file... Please wait ⏳"):
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
                        tmp.write(uploaded_file.getbuffer())
                        temp_input = tmp.name

                    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx').name
                    dept_json_output = tempfile.NamedTemporaryFile(delete=False, suffix='.json').name

                    cleaned_df, major_changes_df = process_excel(
                        input_path=temp_input,
                        output_path=temp_output,
                        mapping_path="canonical_mapping.json",
                        dept_json_output=dept_json_output,
                        target_column=selected_column,
                        sheet_name=None,
                        return_df=True,
                        return_changes=True
                    )

                    st.session_state.cleaned_df = cleaned_df
                    st.session_state.major_changes_df = major_changes_df
                    st.session_state.temp_output = temp_output
                    st.session_state.cleaning_done = True
                    st.success(f"Cleaning complete for column '{selected_column}'.")

        else:
            st.error("Unsupported file format. Please upload a .xlsx or .csv file.")

    except Exception as e:
        st.error(f"Error processing file: {e}")

# ---- After Cleaning (Persistent Download Options) ----
if st.session_state.cleaning_done and st.session_state.cleaned_df is not None:
    st.subheader("Preview")
    preview_changes = st.session_state.major_changes_df.copy()
    preview_changes.index = range(1, len(preview_changes) + 1)
    preview_changes.index.name = ""
    st.dataframe(preview_changes)

    download_format = st.selectbox("Select download format:", ["Excel (.xlsx)", "CSV (.csv)"])

    if download_format == "Excel (.xlsx)":
        with open(st.session_state.temp_output, "rb") as f:
            st.download_button(
                label="Download Cleaned Excel File",
                data=f,
                file_name="Cleaned_Employee_Data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        csv_data = st.session_state.cleaned_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Cleaned CSV File",
            data=csv_data,
            file_name="Cleaned_Employee_Data.csv",
            mime="text/csv"
        )

# Only show info message if no file is uploaded yet
if uploaded_file is None and not st.session_state.cleaning_done:
    st.info("Please upload a file to begin.")

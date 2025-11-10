import streamlit as st
import pandas as pd
import tempfile
import os
from job_title_cleaner import process_excel

st.set_page_config(page_title="Job Title Normalizer", page_icon="🧹", layout="centered")

# Custom CSS to fix title visibility on all devices and themes
st.markdown("""
<style>
/* Page and container */
.stApp { background-color:#f8fafc; font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
.block-container { max-width: 820px; margin: 0 auto; padding-top: 2rem; }

/* Hide dark header bar background so titles are readable */
header[data-testid="stHeader"]{ background:transparent !important; }

/* Title and subtitle */
h1.st-title, .jt-title { 
  color:#111 !important; text-align:center !important; 
  font-size:clamp(1.6rem,4vw,2.4rem) !important; font-weight:700; margin:0 0 .35rem 0;
}
.jt-subtitle { 
  text-align:center; color:#333; 
  font-size:clamp(.95rem,2.4vw,1.1rem); margin:0 0 1.25rem 0;
}

/* Our own visible label above the uploader */
.jt-uplabel {
  display:block; color:#222; font-weight:600; margin:.25rem 0 .4rem;
}

/* Uploader box */
.stFileUploader { 
  border:2px dashed #0078ff !important; border-radius:10px !important; 
  background:#fff !important; padding:1.1rem !important;
}
/* Make sure any internal label inside uploader is fully visible if present */
[data-testid="stFileUploader"] label, 
section[data-testid="stFileUploader"] > label > div {
  color:#222 !important; opacity:1 !important; -webkit-text-fill-color:#222 !important;
}

/* Buttons */
.stDownloadButton button, .stButton button{
  background:#0078ff !important; color:#fff !important; 
  border:none !important; border-radius:8px !important; 
  padding:.7rem 1.3rem !important; font-weight:600 !important;
}

/* Alerts */
.stAlert { border-radius:10px !important; }

/* Mobile tweaks */
@media (max-width: 600px){
  .block-container{ padding-top:1.2rem; }
  .stFileUploader{ padding:.85rem !important; }
}
</style>
""", unsafe_allow_html=True)



# Title & subtitle (these will now be visible everywhere)
st.markdown("<h1 class='jt-title'>Job Title Normalizer</h1>", unsafe_allow_html=True)
st.markdown(
    "<p class='jt-subtitle'>Upload your Excel or CSV file to automatically clean and standardize job titles.</p>",
    unsafe_allow_html=True
)

st.markdown("<label class='jt-uplabel'>Upload Excel or CSV file</label>", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    label="",                      # we render our own label above
    type=["xlsx", "csv"],
    label_visibility="collapsed"   # hide Streamlit's internal label
)

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

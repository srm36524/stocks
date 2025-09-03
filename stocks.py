import streamlit as st
import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

def get_bse_isin_mapping():
    """Fetch or load BSE ISIN mapping (SC_CODE → ISIN)."""
    file_name = "BSE_ISIN_MAPPING.csv"
    url = "https://www.bseindia.com/download/BhavCopy/Equity/EQ_ISINCODE.csv"

    # Check if mapping file exists & is fresh (<1 day old)
    if os.path.exists(file_name):
        modified_time = datetime.fromtimestamp(os.path.getmtime(file_name))
        if datetime.now() - modified_time < timedelta(days=1):
            return pd.read_csv(file_name)  # ✅ Use cached file

    # Otherwise download fresh copy
    try:
        st.info("Fetching fresh BSE ISIN mapping file from BSE...")
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        df = pd.read_csv(io.BytesIO(r.content))

        # Standardize columns
        df = df.rename(columns={
            "SC_CODE": "SC_CODE",
            "SC_NAME": "SC_NAME",
            "ISIN_CODE": "ISIN"
        })

        mapping = df[["SC_CODE", "SC_NAME", "ISIN"]].drop_duplicates()
        mapping.to_csv(file_name, index=False)
        st.success(f"BSE_ISIN_MAPPING.csv updated with {len(mapping)} rows ✅")
        return mapping

    except Exception as e:
        st.error(f"❌ Failed to fetch BSE ISIN mapping: {e}")
        if os.path.exists(file_name):
            st.warning("Using last saved copy...")
            return pd.read_csv(file_name)
        else:
            st.stop()  # Cannot continue without mapping

# Example usage inside app
st.title("NSE–BSE Daily Returns Dashboard")

bse_mapping = get_bse_isin_mapping()
st.write("Sample BSE ISIN Mapping:", bse_mapping.head())

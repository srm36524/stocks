import streamlit as st
import pandas as pd
import glob
import os

# -------------------------
# Load BSE ISIN mapping
# -------------------------
def load_bse_isin_mapping():
    files = sorted(glob.glob("EQ_MAP_CC_*.csv"))
    if not files:
        st.error("❌ No BSE ISIN mapping file (EQ_MAP_CC_*.csv) found.")
        st.stop()

    latest_file = files[-1]
    st.info(f"Using BSE ISIN mapping file: {os.path.basename(latest_file)}")

    df = pd.read_csv(latest_file)

    # Only keep required columns
    keep_cols = [c for c in ["SC_CODE", "SC_NAME", "ISIN"] if c in df.columns]
    mapping = df[keep_cols].drop_duplicates()

    return mapping

# -------------------------
# Load Bhavcopy
# -------------------------
def load_bhavcopy(file, exchange, bse_mapping=None):
    df = pd.read_csv(file)

    if exchange == "NSE":
        # Only take EQ series
        if "SERIES" in df.columns:
            df = df[df["SERIES"] == "EQ"]

        df = df.rename(columns={
            "ISIN": "ISIN",
            "SYMBOL": "SYMBOL",
            "CLOSE": "CLOSE",
            "TOTTRDQTY": "VOLUME"
        })

        df = df[["ISIN", "SYMBOL", "CLOSE", "VOLUME"]]

    elif exchange == "BSE":
        df = df.rename(columns={
            "SC_CODE": "SC_CODE",
            "SC_NAME": "SYMBOL",
            "CLOSE": "CLOSE",
            "NO_OF_SHRS": "VOLUME"
        })

        if bse_mapping is not None and "SC_CODE" in df.columns:
            df = df.merge(bse_mapping, on="SC_CODE", how="left")

        # Ensure ISIN column exists
        if "ISIN" not in df.columns and bse_mapping is not None:
            if "ISIN" in bse_mapping.columns:
                df = df.merge(bse_mapping[["SC_CODE", "ISIN"]], on="SC_CODE", how="left")

        df = df[["ISIN", "SYMBOL", "CLOSE", "VOLUME"]]

    df["EXCHANGE"] = exchange
    return df

# -------------------------
# Compute Returns
# -------------------------
def compute_returns(all_data):
    result = []
    for isin, group in all_data.groupby("ISIN"):
        group = group.sort_values("DATE")

        # Prefer NSE if duplicate exists
        if "NSE" in group["EXCHANGE"].values:
            group = group[group["EXCHANGE"] == "NSE"]

        group["DAILY_CHANGE"] = group["CLOSE"].diff().fillna(0)
        group["TOTAL_CHANGE"] = group["CLOSE"].iloc[-1] - group["CLOSE"].iloc[0]

        result.append(group)

    return pd.concat(result)

# -------------------------
# Color formatting
# -------------------------
def color_change(val):
    if val > 0:
        return "color: green"
    elif val < 0:
        return "color: red"
    else:
        return "color: black"

# -------------------------
# Streamlit UI
# -------------------------
st.title("📈 NSE–BSE Daily Returns Dashboard")

bse_mapping = load_bse_isin_mapping()

uploaded_files = st.file_uploader(
    "Upload NSE & BSE Bhavcopy CSVs (last 7 days)", 
    accept_multiple_files=True, type="csv"
)

if uploaded_files:
    dfs = []
    for file in uploaded_files:
        name = os.path.basename(file.name).upper()

        if "NSE" in name:
            df = load_bhavcopy(file, "NSE")
        elif "BSE" in name:
            df = load_bhavcopy(file, "BSE", bse_mapping)
        else:
            st.warning(f"⚠️ Skipping {file.name} (cannot detect exchange)")
            continue

        # Parse date from filename (YYYYMMDD at start)
        try:
            date_str = name[:8]  # e.g., 20250903_NSE.csv
            df["DATE"] = pd.to_datetime(date_str, format="%Y%m%d", errors="coerce")
        except:
            df["DATE"] = pd.NaT

        dfs.append(df)

    if dfs:
        all_data = pd.concat(dfs, ignore_index=True)
        returns_df = compute_returns(all_data)

        st.subheader("📊 Stock Returns (Last 7 Days)")
        styled = returns_df.style.applymap(color_change, subset=["DAILY_CHANGE", "TOTAL_CHANGE"])
        st.dataframe(styled, use_container_width=True)

        # Download option
        csv = returns_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="💾 Download Results as CSV",
            data=csv,
            file_name="returns_last7days.csv",
            mime="text/csv"
        )

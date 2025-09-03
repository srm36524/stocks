import streamlit as st
import pandas as pd
import requests, zipfile, io
from datetime import datetime, timedelta

# ------------------------
# Helper functions (cached)
# ------------------------
@st.cache_data(show_spinner=False)
def download_nse_bhavcopy(date):
    """Download NSE Bhavcopy for a given date (cached)."""
    fname = f"EQ{date.strftime('%d%b%Y').upper()}CSV.zip"
    url = f"https://archives.nseindia.com/content/historical/EQUITIES/{date.strftime('%Y')}/{date.strftime('%b').upper()}/{fname}"
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    if r.status_code != 200:
        return None
    z = zipfile.ZipFile(io.BytesIO(r.content))
    csv_file = z.namelist()[0]
    df = pd.read_csv(z.open(csv_file))
    df = df[df["SERIES"] == "EQ"]
    return df

@st.cache_data(show_spinner=False)
def download_bse_bhavcopy(date):
    """Download BSE Bhavcopy for a given date (cached)."""
    fname = f"EQ{date.strftime('%d%m%y')}_CSV.ZIP"
    url = f"https://www.bseindia.com/download/BhavCopy/Equity/{fname}"
    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    if r.status_code != 200:
        return None
    z = zipfile.ZipFile(io.BytesIO(r.content))
    csv_file = z.namelist()[0]
    df = pd.read_csv(z.open(csv_file))
    return df

@st.cache_data(show_spinner=False)
def load_bse_mapping():
    """Load BSE ISIN mapping file (cached)."""
    mapping_file = "BSE_ISIN_MAPPING.csv"
    return pd.read_csv(mapping_file)

# ------------------------
# Streamlit UI
# ------------------------
st.title("📊 Daily Stock Returns with Volumes (NSE Preferred, BSE Fallback)")

days = st.slider("Number of past days", 3, 10, 7)

try:
    bse_map = load_bse_mapping()
except:
    st.error("⚠️ Please provide BSE_ISIN_MAPPING.csv with SC_CODE→ISIN mapping.")
    st.stop()

end_date = datetime.today()
dates = [end_date - timedelta(days=i) for i in range(1, 15)]  # last 2 weeks

nse_data, bse_data = [], []

for d in dates:
    nse_df = download_nse_bhavcopy(d)
    bse_df = download_bse_bhavcopy(d)

    if nse_df is not None:
        nse_df = nse_df[["SYMBOL", "ISIN", "CLOSE", "TOTTRDQTY"]].drop_duplicates()
        nse_df["DATE"] = d.strftime("%Y-%m-%d")
        nse_df = nse_df.rename(columns={"TOTTRDQTY": "VOLUME"})
        nse_data.append(nse_df)

    if bse_df is not None:
        bse_df = bse_df[["SC_CODE", "SC_NAME", "CLOSE", "NO_OF_SHRS"]].drop_duplicates()
        bse_df = bse_df.merge(bse_map, on="SC_CODE", how="left")
        bse_df = bse_df.rename(columns={"NO_OF_SHRS": "VOLUME"})
        bse_df = bse_df[["SC_NAME", "ISIN", "CLOSE", "VOLUME"]]
        bse_df["DATE"] = d.strftime("%Y-%m-%d")
        bse_data.append(bse_df)

if nse_data or bse_data:
    # Combine
    if nse_data:
        nse_all = pd.concat(nse_data, ignore_index=True)
    else:
        nse_all = pd.DataFrame(columns=["SYMBOL", "ISIN", "CLOSE", "VOLUME", "DATE"])
    
    if bse_data:
        bse_all = pd.concat(bse_data, ignore_index=True)
    else:
        bse_all = pd.DataFrame(columns=["SC_NAME", "ISIN", "CLOSE", "VOLUME", "DATE"])

    # NSE preferred, BSE fallback
    nse_isins = set(nse_all["ISIN"].dropna().unique())
    bse_filtered = bse_all[~bse_all["ISIN"].isin(nse_isins)]

    # Standardize names
    nse_all = nse_all.rename(columns={"SYMBOL": "NAME"})
    bse_filtered = bse_filtered.rename(columns={"SC_NAME": "NAME"})

    combined = pd.concat(
        [nse_all[["DATE", "ISIN", "NAME", "CLOSE", "VOLUME"]],
         bse_filtered[["DATE", "ISIN", "NAME", "CLOSE", "VOLUME"]]],
        ignore_index=True
    )

    # Pivot for prices & volumes
    price_df = combined.pivot(index="NAME", columns="DATE", values="CLOSE")
    vol_df   = combined.pivot(index="NAME", columns="DATE", values="VOLUME")

    # Keep only last N days
    last_days = sorted(price_df.columns)[-days:]
    price_df = price_df[last_days]
    vol_df   = vol_df[last_days]

    # Daily % change
    daily_change = price_df.pct_change(axis=1) * 100

    # Add total change (first → last)
    daily_change["Total Change %"] = ((price_df[last_days[-1]] - price_df[last_days[0]]) / price_df[last_days[0]]) * 100

    # Build final table: interleave change + volume
    final_df = pd.DataFrame(index=price_df.index)
    for d in last_days:
        final_df[f"{d} Change %"] = daily_change[d]
        final_df[f"{d} Volume"] = vol_df[d]
    final_df["Total Change %"] = daily_change["Total Change %"]

    # Styling function
    def colorize(val):
        if pd.isna(val):
            return "color: black"
        if isinstance(val, (int, float)):
            if val > 0:
                return "color: green"
            elif val < 0:
                return "color: red"
            else:
                return "color: black"
        return "color: black"

    st.subheader(f"Daily Price Change % with Volumes – Last {days} Days")
    styled = final_df.style.applymap(colorize, subset=[c for c in final_df.columns if "Change" in c])
    st.dataframe(styled, use_container_width=True)

    # Plot selected stock
    stock = st.selectbox("Select Stock", final_df.index)
    st.line_chart(price_df.loc[stock].dropna())

    # Download option
    csv = final_df.to_csv().encode("utf-8")
    st.download_button("⬇️ Download Daily Changes & Volumes (CSV)", csv, "daily_changes_volumes.csv", "text/csv")

else:
    st.warning("No Bhavcopy data found for last 2 weeks.")

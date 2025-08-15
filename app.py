
import io
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from datetime import datetime, date, time, timedelta

# --- Color palette (distinct hues, similar sat/value)
DEP_COLOR = '#1f77b4'          # Departure
ARR_COLOR = '#d62728'          # Arrival
DEP_EXTRA_COLOR = '#17becf'    # Departure (extra)
ARR_EXTRA_COLOR = '#ff7f0e'    # Arrival (extra)


st.set_page_config(page_title="Flight Handling Schedule", layout="wide")

# ---- Sidebar controls ----
st.sidebar.header("Settings")
service_start_hour = st.sidebar.number_input("Service day starts at (hour)", min_value=0, max_value=23, value=2, step=1)
base_date = st.sidebar.date_input("BASE_DATE", value=date.today())
interval_min = st.sidebar.selectbox("Overlap interval (min)", options=[10, 20, 30], index=0)

st.sidebar.subheader("Operation windows (minutes)")
dep_before = st.sidebar.number_input("Departure window start (before ATD)", 0, 240, 50, 5)
dep_after  = st.sidebar.number_input("Departure window end (after ATD)", 0, 240, 10, 5)
arr_before = st.sidebar.number_input("Arrival window start (before ATA)", 0, 240, 20, 5)
arr_after  = st.sidebar.number_input("Arrival window end (after ATA)", 0, 240, 30, 5)

st.sidebar.subheader("Labels on bars")
show_flt = st.sidebar.checkbox("Show FLT", value=False)
show_reg = st.sidebar.checkbox("Show REG", value=False)

st.title(f"Flight Handling Schedule ({base_date.strftime('%Y-%m-%d')})")

st.sidebar.markdown("---")
st.sidebar.write("Upload files with headers:")
st.sidebar.write("- Departures: **FLT, ATD, REG**")
st.sidebar.write("- Arrivals: **FLT, ATA, REG**")
st.sidebar.write("- Extra data (mixed dep/arr): **FLT, DES, ATA, ATD**  (HHMM)")

col1, col2, col3 = st.columns(3)
with col1:
    dep_file = st.file_uploader("Departures file", type=["xlsx","xls","csv"], key="dep")
with col2:
    arr_file = st.file_uploader("Arrivals file", type=["xlsx","xls","csv"], key="arr")
with col3:
    extra_file = st.file_uploader("Extra data file (FLT, DES, ATA, ATD)", type=["xlsx","xls","csv"], key="extra")

use_sample = st.button("Load sample data")

def find_col(df, target):
    target = target.strip().upper()
    mapping = {str(c).strip().upper(): c for c in df.columns}
    if target in mapping:
        return mapping[target]
    raise KeyError(f"Required column '{target}' not found.")

def read_tabular(file):
    name = file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(file)
    else:
        return pd.read_excel(file)

def load_dep(file):
    df = read_tabular(file)
    c_flt = find_col(df, "FLT"); c_atd = find_col(df, "ATD"); c_reg = find_col(df, "REG")
    out = df[[c_flt, c_atd, c_reg]].copy(); out.columns = ["FLT","ATD","REG"]; return out

def load_arr(file):
    df = read_tabular(file)
    c_flt = find_col(df, "FLT"); c_ata = find_col(df, "ATA"); c_reg = find_col(df, "REG")
    out = df[[c_flt, c_ata, c_reg]].copy(); out.columns = ["FLT","ATA","REG"]; return out

def load_extra(file):
    if file is None: return None
    df = read_tabular(file)
    c_flt = find_col(df, "FLT"); c_des = find_col(df, "DES"); c_ata = find_col(df, "ATA"); c_atd = find_col(df, "ATD")
    out = df[[c_flt, c_des, c_ata, c_atd]].copy(); out.columns = ["FLT","DES","ATA","ATD"]; return out

def hhmm_to_datetime(base_date, hhmm, service_hour):
    s = str(hhmm).strip()
    if s.isdigit() and len(s) in (3,4):
        s = s.zfill(4)
    tt = datetime.strptime(s, "%H%M").time()
    dt = datetime.combine(base_date, tt)
    if time(tt.hour, tt.minute) < time(service_hour, 0):
        dt += timedelta(days=1)
    return dt

# Load data
if use_sample:
    base_raw = pd.read_csv("flights_sample.csv")
    dep_df = base_raw[["FLT_DEP","ATD"]].rename(columns={"FLT_DEP":"FLT"}); dep_df["REG"] = "HL-" + (dep_df.index+100).astype(str)
    arr_df = base_raw[["FLT_ARR","ATA"]].rename(columns={"FLT_ARR":"FLT"}); arr_df["REG"] = "HL-" + (arr_df.index+200).astype(str)
    extra_df = pd.read_csv("sample_extra_v64.csv")
elif dep_file is not None and arr_file is not None:
    dep_df = load_dep(dep_file); arr_df = load_arr(arr_file); extra_df = load_extra(extra_file)
else:
    st.info("Upload departures & arrivals (and optional extra data), or click 'Load sample data'.")
    st.stop()

# Helper to format HHMM text
def hhmm_text(v): 
    s = str(v).zfill(4)
    return s[:2] + ":" + s[2:]

# Build labels conditionally
def label_for(flt, reg):
    parts = []
    if show_flt:
        parts.append(str(flt).replace("ESR","ZE"))
    if show_reg and pd.notna(reg) and str(reg).strip():
        parts.append(str(reg))
    return " / ".join(parts)

# Compute dep/arr windows (base)
dep_df = dep_df.copy()
dep_df["ATD_dt"] = dep_df["ATD"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
dep_df["start"] = dep_df["ATD_dt"] - timedelta(minutes=int(dep_before))
dep_df["end"]   = dep_df["ATD_dt"] + timedelta(minutes=int(dep_after))
dep_df["marker"] = dep_df["ATD_dt"]; dep_df["type"] = "DEP"; dep_df["time_str"] = dep_df["ATD"].apply(hhmm_text)
dep_df["Label"] = dep_df.apply(lambda r: label_for(r["FLT"], r["REG"]), axis=1)

arr_df = arr_df.copy()
arr_df["ATA_dt"] = arr_df["ATA"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
arr_df["start"] = arr_df["ATA_dt"] - timedelta(minutes=int(arr_before))
arr_df["end"]   = arr_df["ATA_dt"] + timedelta(minutes=int(arr_after))
arr_df["marker"] = arr_df["ATA_dt"]; arr_df["type"] = "ARR"; arr_df["time_str"] = arr_df["ATA"].apply(hhmm_text)
arr_df["Label"] = arr_df.apply(lambda r: label_for(r["FLT"], r["REG"]), axis=1)

# Extra data -> split into dep-like (ATD present) and arr-like (ATA present)
extra_dep = None; extra_arr = None
if extra_df is not None and len(extra_df) > 0:
    ex = extra_df.copy()
    if "ATD" in ex.columns:
        ed = ex[ex["ATD"].notna()].copy()
        if len(ed)>0:
            ed["ATD_dt"] = ed["ATD"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
            ed["start"] = ed["ATD_dt"] - timedelta(minutes=int(dep_before))
            ed["end"]   = ed["ATD_dt"] + timedelta(minutes=int(dep_after))
            ed["marker"] = ed["ATD_dt"]
            ed["type"] = "DEP_EXTRA"
            ed["time_str"] = ed["ATD"].apply(hhmm_text)
            ed["Label"] = ed.apply(lambda r: label_for(str(r["FLT"]).replace("ESR","ZE"), r.get("REG","")), axis=1) if ("REG" in ed.columns) else ed["FLT"].apply(lambda f: label_for(str(f).replace("ESR","ZE"), ""))
            extra_dep = ed[["Label","start","end","marker","type","time_str"]]
    if "ATA" in ex.columns:
        ea = ex[ex["ATA"].notna()].copy()
        if len(ea)>0:
            ea["ATA_dt"] = ea["ATA"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
            ea["start"] = ea["ATA_dt"] - timedelta(minutes=int(arr_before))
            ea["end"]   = ea["ATA_dt"] + timedelta(minutes=int(arr_after))
            ea["marker"] = ea["ATA_dt"]
            ea["type"] = "ARR_EXTRA"
            ea["time_str"] = ea["ATA"].apply(hhmm_text)
            ea["Label"] = ea.apply(lambda r: label_for(str(r["FLT"]).replace("ESR","ZE"), r.get("REG","")), axis=1) if ("REG" in ea.columns) else ea["FLT"].apply(lambda f: label_for(str(f).replace("ESR","ZE"), ""))
            extra_arr = ea[["Label","start","end","marker","type","time_str"]]

# ---- Top panel: classic split ----
fig1, ax1 = plt.subplots(figsize=(12, 8))

# departures block: base + extra (dotted)
dep_block = pd.concat([
    dep_df[["Label","start","end","marker","type","time_str"]],
    (extra_dep if extra_dep is not None else pd.DataFrame(columns=["Label","start","end","marker","type","time_str"]))
], ignore_index=True).sort_values("start").reset_index(drop=True)

for i, row in dep_block.iterrows():
    dotted = ("EXTRA" in row["type"])
    style = (0,(1,2)) if dotted else '-'
    # line segment
    ax1.plot([row["start"], row["end"]], [i, i],
             color=(DEP_EXTRA_COLOR if dotted else DEP_COLOR),
             linewidth=4, linestyle=style, alpha=0.95 if dotted else 1.0,
             label=None)
    # flight label at end
    if row["Label"]:
        ax1.text(row["end"] + timedelta(minutes=5), i, row["Label"],
                 va="center", fontsize=8, color=(DEP_EXTRA_COLOR if dotted else DEP_COLOR))
    # marker (diamond for extra, circle for base)
    ax1.plot(row["marker"], i, marker=('D' if dotted else 'o'),
             color=(DEP_EXTRA_COLOR if dotted else DEP_COLOR))
    # off-block time string
    ax1.text(row["marker"] + timedelta(minutes=3), i+0.15, row["time_str"],
             fontsize=7, color=(DEP_EXTRA_COLOR if dotted else DEP_COLOR))

# ---- Render ----
st.pyplot(fig1, use_container_width=True)

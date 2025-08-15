
import io
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, date, time, timedelta

st.set_page_config(page_title="Flight Handling Schedule", layout="wide")

# ---- Sidebar controls ----
st.sidebar.header("Settings")
service_start_hour = st.sidebar.number_input("Service day starts at (hour)", min_value=0, max_value=23, value=2, step=1)
base_date = st.sidebar.date_input("BASE_DATE", value=date.today())
interval_min = st.sidebar.selectbox("Overlap interval (min)", options=[5, 10, 15], index=1)

st.sidebar.subheader("Operation windows (minutes)")
dep_before = st.sidebar.number_input("Departure window start (before ATD)", 0, 240, 50, 5)
dep_after  = st.sidebar.number_input("Departure window end (after ATD)", 0, 240, 10, 5)
arr_before = st.sidebar.number_input("Arrival window start (before ATA)", 0, 240, 20, 5)
arr_after  = st.sidebar.number_input("Arrival window end (after ATA)", 0, 240, 30, 5)

show_labels = st.sidebar.checkbox("Show FLT/REG labels on bars", value=False)

st.title(f"Flight Handling Schedule ({base_date.strftime('%Y-%m-%d')})")

st.sidebar.markdown("---")
st.sidebar.write("Upload files with headers:")
st.sidebar.write("- Departures: **FLT, ATD, REG**")
st.sidebar.write("- Arrivals: **FLT, ATA, REG**")
st.sidebar.write("- Extra schedule: **FLT, DES, START, END** (HHMM)")

col1, col2, col3 = st.columns(3)
with col1:
    dep_file = st.file_uploader("Departures file", type=["xlsx","xls","csv"], key="dep")
with col2:
    arr_file = st.file_uploader("Arrivals file", type=["xlsx","xls","csv"], key="arr")
with col3:
    extra_file = st.file_uploader("Extra schedule file (FLT, DES, START, END)", type=["xlsx","xls","csv"], key="extra")

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
    c_flt = find_col(df, "FLT"); c_des = find_col(df, "DES"); c_st = find_col(df, "START"); c_en = find_col(df, "END")
    out = df[[c_flt, c_des, c_st, c_en]].copy(); out.columns = ["FLT","DES","START","END"]; return out

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
    extra_df = pd.read_csv("sample_extra.csv")
elif dep_file is not None and arr_file is not None:
    dep_df = load_dep(dep_file); arr_df = load_arr(arr_file); extra_df = load_extra(extra_file)
else:
    st.info("Upload departures & arrivals (and optional extra schedule), or click 'Load sample data'.")
    st.stop()

# Compute windows
dep_df = dep_df.copy()
dep_df["ATD_dt"] = dep_df["ATD"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
dep_df["start"] = dep_df["ATD_dt"] - timedelta(minutes=int(dep_before))
dep_df["end"]   = dep_df["ATD_dt"] + timedelta(minutes=int(dep_after))
dep_df["marker"] = dep_df["ATD_dt"]; dep_df["type"] = "DEP"
dep_df["time_str"] = dep_df["ATD"].astype(str).str.zfill(4).str[:2] + ":" + dep_df["ATD"].astype(str).str.zfill(4).str[2:]

arr_df = arr_df.copy()
arr_df["ATA_dt"] = arr_df["ATA"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
arr_df["start"] = arr_df["ATA_dt"] - timedelta(minutes=int(arr_before))
arr_df["end"]   = arr_df["ATA_dt"] + timedelta(minutes=int(arr_after))
arr_df["marker"] = arr_df["ATA_dt"]; arr_df["type"] = "ARR"
arr_df["time_str"] = arr_df["ATA"].astype(str).str.zfill(4).str[:2] + ":" + arr_df["ATA"].astype(str).str.zfill(4).str[2:]

# Label builder (when enabled)
def build_label(flt, reg):
    flt_str = str(flt).replace("ESR", "ZE")
    reg_str = str(reg) if pd.notna(reg) else ""
    if reg_str.strip():
        return f"{flt_str} ({reg_str})"
    return flt_str

dep_df["Label"] = dep_df.apply(lambda r: build_label(r["FLT"], r["REG"]) if show_labels else "", axis=1)
arr_df["Label"] = arr_df.apply(lambda r: build_label(r["FLT"], r["REG"]) if show_labels else "", axis=1)

# Extra schedule
extra_df_clean = None
if extra_df is not None and len(extra_df) > 0:
    ex = extra_df.copy()
    ex["start_dt"] = ex["START"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
    ex["end_dt"]   = ex["END"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
    ex["start"] = ex["start_dt"]; ex["end"] = ex["end_dt"]
    ex["marker"] = ex["end_dt"]  # END marker as requested
    ex["type"] = "EXTRA"
    ex["Label"] = ex.apply(lambda r: f"{str(r['FLT']).replace('ESR','ZE')} ({r['DES']})" if show_labels else "", axis=1)
    ex["time_str"] = ex["end_dt"].dt.strftime("%H:%M")  # show END time near marker
    extra_df_clean = ex[["Label","start","end","marker","type","time_str"]]

# ---- Top panel: classic split (DEP blue at y=i, ARR red at y=i+0.4) ----
fig1, ax1 = plt.subplots(figsize=(12, 8))

# departures
dep_df = dep_df.sort_values("start").reset_index(drop=True)
for i, row in dep_df.iterrows():
    ax1.plot([row["start"], row["end"]], [i, i], color="blue", linewidth=4, label="Departure" if i==0 else "")
    if row["Label"]:
        ax1.text(row["end"] + timedelta(minutes=5), i, row["Label"], va="center", fontsize=8, color="blue")
    ax1.plot(row["marker"], i, marker="o", color="blue")
    ax1.text(row["marker"] + timedelta(minutes=3), i+0.15, row["time_str"], fontsize=7, color="blue")

# arrivals
arr_df = arr_df.sort_values("start").reset_index(drop=True)
for i, row in arr_df.iterrows():
    y = i + 0.4
    ax1.plot([row["start"], row["end"]], [y, y], color="red", linewidth=4, label="Arrival" if i==0 else "")
    if row["Label"]:
        ax1.text(row["end"] + timedelta(minutes=5), y, row["Label"], va="center", fontsize=8, color="red")
    ax1.plot(row["marker"], y, marker="o", color="red")
    ax1.text(row["marker"] + timedelta(minutes=3), y+0.15, row["time_str"], fontsize=7, color="red")

# extra (orange) stacked after both groups so it doesn't mix lanes
if extra_df_clean is not None:
    base_y = max(len(dep_df), len(arr_df)) + 1
    for j, row in extra_df_clean.reset_index(drop=True).iterrows():
        y = base_y + j
        ax1.plot([row["start"], row["end"]], [y, y], color="orange", linewidth=4, label="Extra" if j==0 else "")
        if row["Label"]:
            ax1.text(row["end"] + timedelta(minutes=5), y, row["Label"], va="center", fontsize=8, color="orange")
        ax1.plot(row["marker"], y, marker="o", color="orange")
        ax1.text(row["marker"] + timedelta(minutes=3), y+0.15, row["time_str"], fontsize=7, color="orange")

ax1.legend(loc="upper left")
ax1.set_yticks([]); ax1.tick_params(axis='y', which='both', left=False, labelleft=False)
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
for lbl in ax1.get_xticklabels(): lbl.set_rotation(0); lbl.set_ha('center')
ax1.set_title("Flight Handling Timeline")
ax1.grid(True, axis="x", linestyle="--", alpha=0.3)

# ---- Bottom panel: overlaps (DEP & ARR only) ----
start_time = min(dep_df["start"].min(), arr_df["start"].min())
end_time   = max(dep_df["end"].max(),   arr_df["end"].max())
time_range = pd.date_range(start=start_time, end=end_time, freq=f"{interval_min}min")

def overlaps(df, t, s_col, e_col):
    return ((df[s_col] <= t) & (df[e_col] > t)).sum()

dep_counts = [overlaps(dep_df, t, "start", "end") for t in time_range]
arr_counts = [overlaps(arr_df, t, "start", "end") for t in time_range]

fig2, ax2 = plt.subplots(figsize=(12, 3.5))
ax2.plot(time_range, dep_counts, label="Departure", color="blue", linewidth=2)
ax2.plot(time_range, arr_counts, label="Arrival", color="red", linewidth=2)
ax2.set_ylabel("Count"); ax2.set_xlabel("Time")
ax2.set_title(f"Overlapping Flights (every {interval_min} min)")
ax2.legend(); ax2.grid(True, alpha=0.3)
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
for lbl in ax2.get_xticklabels(): lbl.set_rotation(0); lbl.set_ha('center')

# ---- Render ----
st.pyplot(fig1, use_container_width=True)
st.pyplot(fig2, use_container_width=True)

# Preview table
st.markdown("#### Preview (top 12 rows per table)")
st.write("Departures"); st.dataframe(dep_df.head(12))
st.write("Arrivals"); st.dataframe(arr_df.head(12))
if extra_df_clean is not None:
    st.write("Extra"); st.dataframe(extra_df_clean.head(12))

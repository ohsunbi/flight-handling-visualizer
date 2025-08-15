
import io
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, date, time, timedelta

st.set_page_config(page_title="Flight Handling Visualizer", layout="wide")

st.title("Flight Handling Schedule")

# ---- Sidebar controls ----
st.sidebar.header("Settings")
service_start_hour = st.sidebar.number_input("Service day starts at (hour)", min_value=0, max_value=23, value=2, step=1)
base_date = st.sidebar.date_input("BASE_DATE", value=date.today())
interval_min = st.sidebar.selectbox("Overlap interval (min)", options=[5, 10, 15], index=1)

st.sidebar.markdown("---")
st.sidebar.write("Upload two files with headers: Departures(FLT,ATD) & Arrivals(FLT,ATA).")
col1, col2 = st.columns(2)
with col1:
    dep_file = st.file_uploader("Departures file (Excel/CSV)", type=["xlsx","csv"], key="dep")
with col2:
    arr_file = st.file_uploader("Arrivals file (Excel/CSV)", type=["xlsx","csv"], key="arr")
use_sample = st.button("Load sample data")

def find_col(df, target):
    target = target.strip().upper()
    mapping = {str(c).strip().upper(): c for c in df.columns}
    if target in mapping:
        return mapping[target]
    raise KeyError(f"Required column '{target}' not found.")

def load_dep(file):
    df = pd.read_csv(file) if file.name.lower().endswith(".csv") else pd.read_excel(file)
    c_flt = find_col(df, "FLT"); c_atd = find_col(df, "ATD")
    out = df[[c_flt, c_atd]].copy(); out.columns = ["FLT","ATD"]; return out

def load_arr(file):
    df = pd.read_csv(file) if file.name.lower().endswith(".csv") else pd.read_excel(file)
    c_flt = find_col(df, "FLT"); c_ata = find_col(df, "ATA")
    out = df[[c_flt, c_ata]].copy(); out.columns = ["FLT","ATA"]; return out

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
    dep_df = pd.read_csv("flights_sample.csv")[["FLT_DEP","ATD"]].rename(columns={"FLT_DEP":"FLT"})
    arr_df = pd.read_csv("flights_sample.csv")[["FLT_ARR","ATA"]].rename(columns={"FLT_ARR":"FLT"})
elif dep_file is not None and arr_file is not None:
    dep_df = load_dep(dep_file); arr_df = load_arr(arr_file)
else:
    st.info("Upload both departure and arrival files, or click 'Load sample data'.")
    st.stop()

# Compute windows
dep_df = dep_df.copy()
dep_df["ATD_dt"] = dep_df["ATD"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
dep_df["DEP_start"] = dep_df["ATD_dt"] - timedelta(minutes=50)
dep_df["DEP_end"]   = dep_df["ATD_dt"] + timedelta(minutes=10)
dep_df["type"] = "DEP"
dep_df.sort_values("DEP_start", inplace=True, ignore_index=True)

arr_df = arr_df.copy()
arr_df["ATA_dt"] = arr_df["ATA"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
arr_df["ARR_start"] = arr_df["ATA_dt"] - timedelta(minutes=20)
arr_df["ARR_end"]   = arr_df["ATA_dt"] + timedelta(minutes=30)
arr_df["type"] = "ARR"
arr_df.sort_values("ARR_start", inplace=True, ignore_index=True)

# ---- Top panel: classic style ----
fig1, ax1 = plt.subplots(figsize=(12, 8))

# plot departures (blue) on y=i
for i, row in dep_df.iterrows():
    ax1.plot([row["DEP_start"], row["DEP_end"]], [i, i], color="blue", linewidth=4, label="Departure" if i==0 else "")
    ax1.text(row["DEP_end"] + timedelta(minutes=5), i, row["FLT"], va="center", fontsize=8, color="blue")
    ax1.plot(row["ATD_dt"], i, marker="o", color="blue")
    ax1.text(row["ATD_dt"] + timedelta(minutes=3), i+0.15, row["ATD"], fontsize=7, color="blue")

# plot arrivals (red) on y=i+0.4
for i, row in arr_df.iterrows():
    ax1.plot([row["ARR_start"], row["ARR_end"]], [i+0.4, i+0.4], color="red", linewidth=4, label="Arrival" if i==0 else "")
    ax1.text(row["ARR_end"] + timedelta(minutes=5), i+0.4, row["FLT"], va="center", fontsize=8, color="red")
    ax1.plot(row["ATA_dt"], i+0.4, marker="o", color="red")
    ax1.text(row["ATA_dt"] + timedelta(minutes=3), i+0.55, row["ATA"], fontsize=7, color="red")

# remove y-axis ticks/labels
ax1.set_yticks([])
ax1.tick_params(axis='y', which='both', left=False, labelleft=False)
ax1.set_xlabel("Time")
ax1.legend(loc="upper left")
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
fig1.autofmt_xdate()
ax1.grid(True, axis="x", linestyle="--", alpha=0.3)

# ---- Bottom line: overlaps every N minutes ----
start_time = min(dep_df["DEP_start"].min(), arr_df["ARR_start"].min())
end_time   = max(dep_df["DEP_end"].max(),   arr_df["ARR_end"].max())
time_range = pd.date_range(start=start_time, end=end_time, freq=f"{interval_min}min")

def overlaps(df, t, s_col, e_col):
    return ((df[s_col] <= t) & (df[e_col] > t)).sum()

dep_counts = [overlaps(dep_df, t, "DEP_start", "DEP_end") for t in time_range]
arr_counts = [overlaps(arr_df, t, "ARR_start", "ARR_end") for t in time_range]
count_df = pd.DataFrame({"Time": time_range, "Departure_Count": dep_counts, "Arrival_Count": arr_counts})

fig2, ax2 = plt.subplots(figsize=(12, 3.5))
ax2.plot(count_df["Time"], count_df["Departure_Count"], label="Departure", color="blue", linewidth=2)
ax2.plot(count_df["Time"], count_df["Arrival_Count"], label="Arrival", color="red", linewidth=2)
ax2.set_ylabel("Count")
ax2.set_xlabel("Time")
ax2.set_title(f"Number of Overlapping Flights ({interval_min}-min intervals)")
ax2.legend()
ax2.grid(True, axis="both", alpha=0.3)
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
fig2.autofmt_xdate()

# ---- Layout ----
st.pyplot(fig1, use_container_width=True)
st.pyplot(fig2, use_container_width=True)

# Download combined image
buf = io.BytesIO()
fig_all, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={"height_ratios":[3,1]})
# top replot
for i, row in dep_df.iterrows():
    ax_top.plot([row["DEP_start"], row["DEP_end"]], [i, i], color="blue", linewidth=4)
    ax_top.text(row["DEP_end"] + timedelta(minutes=5), i, row["FLT"], va="center", fontsize=8, color="blue")
    ax_top.plot(row["ATD_dt"], i, marker="o", color="blue")
    ax_top.text(row["ATD_dt"] + timedelta(minutes=3), i+0.15, row["ATD"], fontsize=7, color="blue")
for i, row in arr_df.iterrows():
    ax_top.plot([row["ARR_start"], row["ARR_end"]], [i+0.4, i+0.4], color="red", linewidth=4)
    ax_top.text(row["ARR_end"] + timedelta(minutes=5), i+0.4, row["FLT"], va="center", fontsize=8, color="red")
    ax_top.plot(row["ATA_dt"], i+0.4, marker="o", color="red")
    ax_top.text(row["ATA_dt"] + timedelta(minutes=3), i+0.55, row["ATA"], fontsize=7, color="red")
ax_top.set_yticks([]); ax_top.tick_params(axis='y', which='both', left=False, labelleft=False)
ax_top.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
ax_top.set_title("Flight Handling Schedule")

ax_bot.plot(count_df["Time"], count_df["Departure_Count"], label="Departure", color="blue", linewidth=2)
ax_bot.plot(count_df["Time"], count_df["Arrival_Count"], label="Arrival", color="red", linewidth=2)
ax_bot.set_ylabel("Count"); ax_bot.set_xlabel("Time")
ax_bot.set_title(f"Number of Overlapping Flights ({interval_min}-min intervals)")
ax_bot.legend(); ax_bot.grid(True, alpha=0.3)
ax_bot.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

plt.tight_layout()
fig_all.savefig(buf, format="png", dpi=200)
st.download_button("Download PNG", data=buf.getvalue(), file_name="flight_visualization.png", mime="image/png")

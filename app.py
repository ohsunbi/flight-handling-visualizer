
import io
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, date, time, timedelta

st.set_page_config(page_title="Flight Handling Visualizer", layout="wide")

st.title("✈️ Flight Handling Visualizer")
st.caption("출발편: ATD 기준 -50 ~ +10분 · 도착편: ATA 기준 -20 ~ +30분 · 운영일 시작시각 반영")

# ---- Sidebar controls ----
st.sidebar.header("⚙️ 설정")
service_start_hour = st.sidebar.number_input("운영일 시작 시각 (시)", min_value=0, max_value=23, value=2, step=1)
base_date = st.sidebar.date_input("BASE_DATE (운영일 시작 날짜)", value=date.today())
interval_min = st.sidebar.selectbox("동시작업 집계 간격(분)", options=[5, 10, 15], index=1)

st.sidebar.markdown("---")
st.sidebar.write("데이터 업로드: 출발편/도착편 엑셀 또는 CSV를 **각각** 올리세요.")
st.sidebar.write("- 출발편 파일: 헤더 행 포함, **FLT** 및 **ATD** 열이 있어야 함")
st.sidebar.write("- 도착편 파일: 헤더 행 포함, **FLT** 및 **ATA** 열이 있어야 함")

col1, col2 = st.columns(2)
with col1:
    dep_file = st.file_uploader("출발편 파일 업로드 (Excel/CSV)", type=["xlsx","csv"], key="dep")
with col2:
    arr_file = st.file_uploader("도착편 파일 업로드 (Excel/CSV)", type=["xlsx","csv"], key="arr")

use_sample = st.button("샘플 데이터로 테스트")

def find_col(df, target):
    # case-insensitive, trim spaces
    target = target.strip().upper()
    mapping = {str(c).strip().upper(): c for c in df.columns}
    if target in mapping:
        return mapping[target]
    raise KeyError(f"필수 열 '{target}'을(를) 찾을 수 없습니다. 실제 헤더를 확인하세요.")

def load_dep(file):
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)
    c_flt = find_col(df, "FLT")
    c_atd = find_col(df, "ATD")
    out = df[[c_flt, c_atd]].copy()
    out.columns = ["FLT", "ATD"]
    return out

def load_arr(file):
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)
    c_flt = find_col(df, "FLT")
    c_ata = find_col(df, "ATA")
    out = df[[c_flt, c_ata]].copy()
    out.columns = ["FLT", "ATA"]
    return out

def hhmm_to_datetime(base_date, hhmm, service_hour):
    s = str(hhmm).strip()
    if s.isdigit() and len(s) in (3,4):
        s = s.zfill(4)
    tt = datetime.strptime(s, "%H%M").time()
    dt = datetime.combine(base_date, tt)
    if time(tt.hour, tt.minute) < time(service_hour, 0):
        dt += timedelta(days=1)
    return dt

# Data assembly
if use_sample:
    dep_df = pd.read_csv("flights_sample.csv")[["FLT_DEP","ATD"]].rename(columns={"FLT_DEP":"FLT"})
    arr_df = pd.read_csv("flights_sample.csv")[["FLT_ARR","ATA"]].rename(columns={"FLT_ARR":"FLT"})
elif dep_file is not None and arr_file is not None:
    try:
        dep_df = load_dep(dep_file)
        arr_df = load_arr(arr_file)
    except Exception as e:
        st.error(f"파일 처리 중 오류: {e}")
        st.stop()
else:
    st.info("출발편/도착편 파일을 각각 업로드하거나, '샘플 데이터로 테스트'를 눌러보세요.")
    st.stop()

# Compute windows
# Departures
dep_df = dep_df.copy()
dep_df["ATD_dt"] = dep_df["ATD"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
dep_df["DEP_start"] = dep_df["ATD_dt"] - timedelta(minutes=50)
dep_df["DEP_end"]   = dep_df["ATD_dt"] + timedelta(minutes=10)

# Arrivals
arr_df = arr_df.copy()
arr_df["ATA_dt"] = arr_df["ATA"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
arr_df["ARR_start"] = arr_df["ATA_dt"] - timedelta(minutes=20)
arr_df["ARR_end"]   = arr_df["ATA_dt"] + timedelta(minutes=30)

# ---- Top timeline: departures on top block, arrivals on bottom block ----
fig1, ax1 = plt.subplots(figsize=(12, 8))

# Lane allocation
dep_y_base = 0
arr_y_base = len(dep_df) + 2  # add gap

# Departures (blue-ish by default)
for i, row in dep_df.reset_index(drop=True).iterrows():
    y = dep_y_base + i
    ax1.plot([row["DEP_start"], row["DEP_end"]], [y, y], linewidth=4)
    ax1.text(row["DEP_end"] + timedelta(minutes=5), y, row["FLT"], va="center", fontsize=8)
    ax1.plot(row["ATD_dt"], y, marker="o")
    ax1.text(row["ATD_dt"] + timedelta(minutes=3), y+0.15, row["ATD"], fontsize=7)

# Arrivals (second block)
for j, row in arr_df.reset_index(drop=True).iterrows():
    y = arr_y_base + j
    ax1.plot([row["ARR_start"], row["ARR_end"]], [y, y], linewidth=4)
    ax1.text(row["ARR_end"] + timedelta(minutes=5), y, row["FLT"], va="center", fontsize=8)
    ax1.plot(row["ATA_dt"], y, marker="o")
    ax1.text(row["ATA_dt"] + timedelta(minutes=3), y+0.15, row["ATA"], fontsize=7)

# y ticks & labels
yticks = list(range(dep_y_base, dep_y_base+len(dep_df))) + list(range(arr_y_base, arr_y_base+len(arr_df)))
yticklabels = [f"DEP {f}" for f in dep_df["FLT"].tolist()] + [f"ARR {f}" for f in arr_df["FLT"].tolist()]
ax1.set_yticks(yticks)
ax1.set_yticklabels(yticklabels, fontsize=8)
ax1.set_title("Flight Handling Timeline (separate lanes for Departures & Arrivals)")
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
fig1.autofmt_xdate()

# ---- Bottom line: overlaps every N minutes ----
start_time = min(dep_df["DEP_start"].min(), arr_df["ARR_start"].min())
end_time   = max(dep_df["DEP_end"].max(),   arr_df["ARR_end"].max())
time_range = pd.date_range(start=start_time, end=end_time, freq=f"{interval_min}min")
dep_counts, arr_counts = [], []
for t in time_range:
    dep_counts.append(((dep_df["DEP_start"] <= t) & (dep_df["DEP_end"] > t)).sum())
    arr_counts.append(((arr_df["ARR_start"] <= t) & (arr_df["ARR_end"] > t)).sum())
count_df = pd.DataFrame({"Time": time_range, "Departure_Count": dep_counts, "Arrival_Count": arr_counts})

fig2, ax2 = plt.subplots(figsize=(12, 3.5))
ax2.plot(count_df["Time"], count_df["Departure_Count"], linewidth=2)
ax2.plot(count_df["Time"], count_df["Arrival_Count"], linewidth=2)
for t, dep_c, arr_c in zip(count_df["Time"], count_df["Departure_Count"], count_df["Arrival_Count"]):
    if dep_c > 0:
        ax2.text(t, dep_c + 0.1, str(dep_c), fontsize=8, ha="center")
    if arr_c > 0:
        ax2.text(t, arr_c + 0.1, str(arr_c), fontsize=8, ha="center")
ax2.set_title(f"Overlapping Flights (every {interval_min} min)")
ax2.set_ylabel("Count")
ax2.set_xlabel("Time")
ax2.grid(True)
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
fig2.autofmt_xdate()

# ---- Layout in Streamlit ----
st.subheader("타임라인")
st.pyplot(fig1, use_container_width=True)
st.subheader("동시작업 수")
st.pyplot(fig2, use_container_width=True)

# ---- Preview tables ----
st.markdown("#### 출발편 데이터 미리보기 (상위 10행)")
st.dataframe(dep_df[["FLT","ATD","ATD_dt","DEP_start","DEP_end"]].head(10))
st.markdown("#### 도착편 데이터 미리보기 (상위 10행)")
st.dataframe(arr_df[["FLT","ATA","ATA_dt","ARR_start","ARR_end"]].head(10))

# ---- Export combined figure ----
buf = io.BytesIO()
fig_all, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={"height_ratios":[3,1]}, sharex=False)

# replot top
for i, row in dep_df.reset_index(drop=True).iterrows():
    y = i
    ax_top.plot([row["DEP_start"], row["DEP_end"]], [y, y], linewidth=4)
    ax_top.text(row["DEP_end"] + timedelta(minutes=5), y, row["FLT"], va="center", fontsize=8)
    ax_top.plot(row["ATD_dt"], y, marker="o")
    ax_top.text(row["ATD_dt"] + timedelta(minutes=3), y+0.15, row["ATD"], fontsize=7)
dep_block = len(dep_df) + 2
for j, row in arr_df.reset_index(drop=True).iterrows():
    y = dep_block + j
    ax_top.plot([row["ARR_start"], row["ARR_end"]], [y, y], linewidth=4)
    ax_top.text(row["ARR_end"] + timedelta(minutes=5), y, row["FLT"], va="center", fontsize=8)
    ax_top.plot(row["ATA_dt"], y, marker="o")
    ax_top.text(row["ATA_dt"] + timedelta(minutes=3), y+0.15, row["ATA"], fontsize=7)

yticks2 = list(range(0, len(dep_df))) + list(range(dep_block, dep_block+len(arr_df)))
yticklabels2 = [f"DEP {f}" for f in dep_df["FLT"].tolist()] + [f"ARR {f}" for f in arr_df["FLT"].tolist()]
ax_top.set_yticks(yticks2)
ax_top.set_yticklabels(yticklabels2, fontsize=8)
ax_top.set_title("Flight Handling Timeline")
ax_top.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
fig_all.autofmt_xdate()

# bottom
ax_bot.plot(count_df["Time"], count_df["Departure_Count"], linewidth=2)
ax_bot.plot(count_df["Time"], count_df["Arrival_Count"], linewidth=2)
for t, dep_c, arr_c in zip(count_df["Time"], count_df["Departure_Count"], count_df["Arrival_Count"]):
    if dep_c > 0:
        ax_bot.text(t, dep_c + 0.1, str(dep_c), fontsize=8, ha="center")
    if arr_c > 0:
        ax_bot.text(t, arr_c + 0.1, str(arr_c), fontsize=8, ha="center")
ax_bot.set_title(f"Overlapping Flights (every {interval_min} min)")
ax_bot.set_ylabel("Count")
ax_bot.set_xlabel("Time")
ax_bot.grid(True)
ax_bot.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))

plt.tight_layout()
fig_all.savefig(buf, format="png", dpi=200)
st.download_button("전체 그림 PNG로 다운로드", data=buf.getvalue(), file_name="flight_visualization.png", mime="image/png")

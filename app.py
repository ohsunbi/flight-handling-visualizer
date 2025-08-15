
import io
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, date, time, timedelta

st.set_page_config(page_title="Flight Handling Visualizer", layout="wide")

st.title("✈️ Flight Handling Visualizer")
st.caption("출발: ATD 기준 -50~+10분 · 도착: ATA 기준 -20~+30분 · 운영일 시작시각 반영")

# ---- Sidebar controls ----
st.sidebar.header("⚙️ 설정")
service_start_hour = st.sidebar.number_input("운영일 시작 시각 (시)", min_value=0, max_value=23, value=2, step=1)
base_date = st.sidebar.date_input("BASE_DATE (운영일 시작 날짜)", value=date.today())
interval_min = st.sidebar.selectbox("동시작업 집계 간격(분)", options=[5, 10, 15], index=1)

st.markdown(f"**BASE_DATE:** {base_date.strftime('%Y-%m-%d')}")  # 화면 왼쪽 상단 표기

st.sidebar.markdown("---")
st.sidebar.write("각 파일은 헤더 포함, 출발= FLT+ATD / 도착= FLT+ATA 열 필요")

col1, col2 = st.columns(2)
with col1:
    dep_file = st.file_uploader("출발편 파일 업로드 (Excel/CSV)", type=["xlsx","csv"], key="dep")
with col2:
    arr_file = st.file_uploader("도착편 파일 업로드 (Excel/CSV)", type=["xlsx","csv"], key="arr")

use_sample = st.button("샘플 데이터로 테스트")

def find_col(df, target):
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
dep_df["start"] = dep_df["ATD_dt"] - timedelta(minutes=50)
dep_df["end"]   = dep_df["ATD_dt"] + timedelta(minutes=10)
dep_df["marker"] = dep_df["ATD_dt"]
dep_df["type"] = "DEP"
dep_df["label_time"] = dep_df["ATD"]

# Arrivals
arr_df = arr_df.copy()
arr_df["ATA_dt"] = arr_df["ATA"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
arr_df["start"] = arr_df["ATA_dt"] - timedelta(minutes=20)
arr_df["end"]   = arr_df["ATA_dt"] + timedelta(minutes=30)
arr_df["marker"] = arr_df["ATA_dt"]
arr_df["type"] = "ARR"
arr_df["label_time"] = arr_df["ATA"]

# Unified table
dep_small = dep_df[["FLT","start","end","marker","type","label_time"]]
arr_small = arr_df[["FLT","start","end","marker","type","label_time"]]
all_df = pd.concat([dep_small, arr_small], ignore_index=True)
all_df = all_df.sort_values("start").reset_index(drop=True)

# ---- Unified timeline ----
fig1, ax1 = plt.subplots(figsize=(12, 8))

for i, row in all_df.iterrows():
    # 색상 지정: 출발=주황, 도착=초록
    color = "orange" if row["type"] == "DEP" else "green"
    ax1.plot([row["start"], row["end"]], [i, i], linewidth=6, color=color)
    # 편명 라벨
    ax1.text(row["end"] + timedelta(minutes=5), i, f"{row['type']} {row['FLT']}", va="center", fontsize=8, color=color)
    # 마커 + 시간
    ax1.plot(row["marker"], i, marker="o", color=color)
    ax1.text(row["marker"] + timedelta(minutes=3), i+0.18, row["label_time"], fontsize=7, color=color)

# Y축 제거
ax1.set_yticks([])
ax1.tick_params(axis='y', which='both', left=False, labelleft=False)

# X축 시간만 (날짜는 숨김)
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
fig1.autofmt_xdate()
ax1.set_title("Unified Flight Handling Timeline (sorted by work start)")

# ---- Overlaps every N minutes (by type) ----
start_time = all_df["start"].min()
end_time   = all_df["end"].max()
time_range = pd.date_range(start=start_time, end=end_time, freq=f"{interval_min}min")

def count_overlaps(sub_df, t):
    return ((sub_df["start"] <= t) & (sub_df["end"] > t)).sum()

dep_sub = all_df[all_df["type"]=="DEP"]
arr_sub = all_df[all_df["type"]=="ARR"]

dep_counts, arr_counts = [], []
for t in time_range:
    dep_counts.append(count_overlaps(dep_sub, t))
    arr_counts.append(count_overlaps(arr_sub, t))

count_df = pd.DataFrame({"Time": time_range, "Departure_Count": dep_counts, "Arrival_Count": arr_counts})

fig2, ax2 = plt.subplots(figsize=(12, 3.5))
ax2.plot(count_df["Time"], count_df["Departure_Count"], linewidth=2)  # 색상 지정 안함(요청 없음)
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
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
fig2.autofmt_xdate()

# ---- Layout in Streamlit ----
st.subheader("통합 타임라인")
st.pyplot(fig1, use_container_width=True)
st.subheader("동시작업 수")
st.pyplot(fig2, use_container_width=True)

# ---- Preview tables ----
st.markdown("#### 통합 테이블 (상위 12행)")
st.dataframe(all_df.head(12))

# ---- Export combined figure ----
buf = io.BytesIO()
fig_all, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={"height_ratios":[3,1]})
for i, row in all_df.iterrows():
    c = "orange" if row["type"]=="DEP" else "green"
    ax_top.plot([row["start"], row["end"]], [i, i], linewidth=6, color=c)
    ax_top.text(row["end"] + timedelta(minutes=5), i, f"{row['type']} {row['FLT']}", va="center", fontsize=8, color=c)
    ax_top.plot(row["marker"], i, marker="o", color=c)
    ax_top.text(row["marker"] + timedelta(minutes=3), i+0.18, row["label_time"], fontsize=7, color=c)
ax_top.set_yticks([])
ax_top.tick_params(axis='y', which='both', left=False, labelleft=False)
ax_top.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
ax_top.set_title("Unified Flight Handling Timeline")

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
ax_bot.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

plt.tight_layout()
fig_all.savefig(buf, format="png", dpi=200)
st.download_button("전체 그림 PNG로 다운로드", data=buf.getvalue(), file_name="flight_visualization.png", mime="image/png")

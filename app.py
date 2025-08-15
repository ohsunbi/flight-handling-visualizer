
import io
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, date, time, timedelta

st.set_page_config(page_title="이스타항공 운항편 차트", layout="wide")

# ---- Sidebar controls ----
st.sidebar.header("설정")
service_start_hour = st.sidebar.number_input("운영일 시작 시각 (시)", min_value=0, max_value=23, value=2, step=1)
base_date = st.sidebar.date_input("BASE_DATE (운항일 기준 날짜)", value=date.today())
interval_min = st.sidebar.selectbox("중복 집계 간격(분)", options=[5, 10, 15], index=1)

st.title(f"이스타항공 운항편 차트 ({base_date.strftime('%Y-%m-%d')})")

st.sidebar.markdown("---")
st.sidebar.write("각 파일은 헤더 포함, 출발= **FLT, ATD, REG** / 도착= **FLT, ATA, REG** 열이 있어야 합니다.")

col1, col2 = st.columns(2)
with col1:
    dep_file = st.file_uploader("Departures file  ·  도착편", type=["xlsx","csv"], key="dep")  # as requested
with col2:
    arr_file = st.file_uploader("Arrivals file  ·  출발편", type=["xlsx","csv"], key="arr")    # as requested
use_sample = st.button("샘플 데이터 불러오기")

def find_col(df, target):
    target = target.strip().upper()
    mapping = {str(c).strip().upper(): c for c in df.columns}
    if target in mapping:
        return mapping[target]
    raise KeyError(f"필수 열 '{target}'을(를) 찾을 수 없습니다. 파일 헤더를 확인하세요.")

def load_dep(file):
    df = pd.read_csv(file) if file.name.lower().endswith(".csv") else pd.read_excel(file)
    c_flt = find_col(df, "FLT")
    c_atd = find_col(df, "ATD")
    c_reg = find_col(df, "REG")
    out = df[[c_flt, c_atd, c_reg]].copy()
    out.columns = ["FLT", "ATD", "REG"]
    return out

def load_arr(file):
    df = pd.read_csv(file) if file.name.lower().endswith(".csv") else pd.read_excel(file)
    c_flt = find_col(df, "FLT")
    c_ata = find_col(df, "ATA")
    c_reg = find_col(df, "REG")
    out = df[[c_flt, c_ata, c_reg]].copy()
    out.columns = ["FLT", "ATA", "REG"]
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

# Load data
if use_sample:
    raw = pd.read_csv("flights_sample.csv")
    dep_df = raw[["FLT_DEP","ATD"]].rename(columns={"FLT_DEP":"FLT"})
    dep_df["REG"] = "HL-" + (dep_df.index+100).astype(str)
    arr_df = raw[["FLT_ARR","ATA"]].rename(columns={"FLT_ARR":"FLT"})
    arr_df["REG"] = "HL-" + (arr_df.index+200).astype(str)
elif dep_file is not None and arr_file is not None:
    dep_df = load_dep(dep_file)
    arr_df = load_arr(arr_file)
else:
    st.info("출발편/도착편 파일을 각각 업로드하거나, '샘플 데이터 불러오기'를 눌러보세요.")
    st.stop()

# Compute windows & unify
# Departures
dep_df = dep_df.copy()
dep_df["ATD_dt"] = dep_df["ATD"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
dep_df["start"] = dep_df["ATD_dt"] - timedelta(minutes=50)
dep_df["end"]   = dep_df["ATD_dt"] + timedelta(minutes=10)
dep_df["marker"] = dep_df["ATD_dt"]
dep_df["type"] = "DEP"
dep_df["time_str"] = dep_df["ATD"].astype(str).str.zfill(4).str[:2] + ":" + dep_df["ATD"].astype(str).str.zfill(4).str[2:]

# Arrivals
arr_df = arr_df.copy()
arr_df["ATA_dt"] = arr_df["ATA"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
arr_df["start"] = arr_df["ATA_dt"] - timedelta(minutes=20)
arr_df["end"]   = arr_df["ATA_dt"] + timedelta(minutes=30)
arr_df["marker"] = arr_df["ATA_dt"]
arr_df["type"] = "ARR"
arr_df["time_str"] = arr_df["ATA"].astype(str).str.zfill(4).str[:2] + ":" + arr_df["ATA"].astype(str).str.zfill(4).str[2:]

# Normalize FLT display (ESR -> ZE) and append (REG)
def display_flt(flt, reg):
    s = str(flt)
    s = s.replace("ESR", "ZE")
    return f"{s} ({reg})" if pd.notna(reg) and str(reg).strip() != "" else s

dep_df["FLT_disp"] = dep_df.apply(lambda r: display_flt(r["FLT"], r["REG"]), axis=1)
arr_df["FLT_disp"] = arr_df.apply(lambda r: display_flt(r["FLT"], r["REG"]), axis=1)

# Unified table, sorted by start
all_df = pd.concat([
    dep_df[["FLT_disp","start","end","marker","type","time_str"]],
    arr_df[["FLT_disp","start","end","marker","type","time_str"]]
], ignore_index=True).sort_values("start").reset_index(drop=True)

# ---- Unified timeline ----
fig, ax = plt.subplots(figsize=(12, 8))
for i, row in all_df.iterrows():
    color = "red" if row["type"]=="DEP" else "blue"
    ax.plot([row["start"], row["end"]], [i, i], linewidth=6, color=color)
    ax.text(row["end"] + timedelta(minutes=5), i, row["FLT_disp"], va="center", fontsize=8, color=color)
    ax.plot(row["marker"], i, marker="o", color=color)
    ax.text(row["marker"] + timedelta(minutes=3), i+0.18, row["time_str"], fontsize=7, color=color)

# Hide Y-axis
ax.set_yticks([]); ax.tick_params(axis='y', which='both', left=False, labelleft=False)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
fig.autofmt_xdate()
ax.set_title("운항 작업 타임라인 (작업 시작시간 기준 정렬)")
ax.grid(True, axis="x", linestyle="--", alpha=0.3)

# ---- Overlap line chart ----
start_time = all_df["start"].min(); end_time = all_df["end"].max()
time_range = pd.date_range(start=start_time, end=end_time, freq=f"{interval_min}min")
dep_counts = [ ((all_df["type"]=="DEP") & (all_df["start"]<=t) & (all_df["end"]>t)).sum() for t in time_range ]
arr_counts = [ ((all_df["type"]=="ARR") & (all_df["start"]<=t) & (all_df["end"]>t)).sum() for t in time_range ]
count_df = pd.DataFrame({"Time": time_range, "Departure_Count": dep_counts, "Arrival_Count": arr_counts})

fig2, ax2 = plt.subplots(figsize=(12, 3.5))
ax2.plot(count_df["Time"], count_df["Departure_Count"], label="Departure", color="red", linewidth=2)
ax2.plot(count_df["Time"], count_df["Arrival_Count"], label="Arrival", color="blue", linewidth=2)
ax2.set_ylabel("Count"); ax2.set_xlabel("Time")
ax2.set_title("운항편 중복 개수")
ax2.legend(); ax2.grid(True, alpha=0.3)
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
fig2.autofmt_xdate()

st.pyplot(fig, use_container_width=True)
st.pyplot(fig2, use_container_width=True)

# Preview
st.markdown("#### 통합 데이터 (상위 12행)")
st.dataframe(all_df.head(12))

# Download PNG
buf = io.BytesIO()
fig_all, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={"height_ratios":[3,1]})
for i, row in all_df.iterrows():
    c = "red" if row["type"]=="DEP" else "blue"
    ax_top.plot([row["start"], row["end"]], [i, i], linewidth=6, color=c)
    ax_top.text(row["end"] + timedelta(minutes=5), i, row["FLT_disp"], va="center", fontsize=8, color=c)
    ax_top.plot(row["marker"], i, marker="o", color=c)
    ax_top.text(row["marker"] + timedelta(minutes=3), i+0.18, row["time_str"], fontsize=7, color=c)
ax_top.set_yticks([]); ax_top.tick_params(axis='y', which='both', left=False, labelleft=False)
ax_top.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
ax_top.set_title(f"이스타항공 운항편 차트 ({base_date.strftime('%Y-%m-%d')})")

ax_bot.plot(count_df["Time"], count_df["Departure_Count"], label="Departure", color="red", linewidth=2)
ax_bot.plot(count_df["Time"], count_df["Arrival_Count"], label="Arrival", color="blue", linewidth=2)
ax_bot.set_ylabel("Count"); ax_bot.set_xlabel("Time")
ax_bot.set_title("운항편 중복 개수")
ax_bot.legend(); ax_bot.grid(True, alpha=0.3)
ax_bot.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

plt.tight_layout()
fig_all.savefig(buf, format="png", dpi=200)
st.download_button("PNG로 저장", data=buf.getvalue(), file_name="flight_visualization.png", mime="image/png")

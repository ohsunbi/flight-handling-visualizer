
import io
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams
from datetime import datetime, date, time, timedelta

# ---- Fonts for Korean (fallbacks) ----
rcParams['font.family'] = ['NanumGothic', 'Malgun Gothic', 'AppleGothic', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False

st.set_page_config(page_title="이스타항공 운항편 차트", layout="wide")

# ---- Sidebar controls ----
st.sidebar.header("설정")
service_start_hour = st.sidebar.number_input("운영일 시작 시각 (시)", min_value=0, max_value=23, value=2, step=1)
base_date = st.sidebar.date_input("BASE_DATE (운항일 기준 날짜)", value=date.today())
interval_min = st.sidebar.selectbox("중복 집계 간격(분)", options=[5, 10, 15], index=1)
hide_flt = st.sidebar.checkbox("편명(FLT) 숨기기 — 괄호 안 REG만 표기", value=False)

st.sidebar.subheader("작업 시간(분) 조정")
dep_before = st.sidebar.number_input("출발 작업 시작(ATD 기준 이전)", min_value=0, max_value=240, value=50, step=5)
dep_after  = st.sidebar.number_input("출발 작업 종료(ATD 기준 이후)", min_value=0, max_value=240, value=10, step=5)
arr_before = st.sidebar.number_input("도착 작업 시작(ATA 기준 이전)", min_value=0, max_value=240, value=20, step=5)
arr_after  = st.sidebar.number_input("도착 작업 종료(ATA 기준 이후)", min_value=0, max_value=240, value=30, step=5)

st.title(f"이스타항공 운항편 차트 ({base_date.strftime('%Y-%m-%d')})")

st.sidebar.markdown("---")
st.sidebar.write("파일 형식:")
st.sidebar.write("- 출발= **FLT, ATD, REG**")
st.sidebar.write("- 도착= **FLT, ATA, REG**")
st.sidebar.write("- 추가 일정= **FLT, DES, START, END** (HHMM)")

col1, col2, col3 = st.columns(3)
with col1:
    dep_file = st.file_uploader("Departures file  ·  도착편", type=["xlsx","xls","csv"], key="dep")
with col2:
    arr_file = st.file_uploader("Arrivals file  ·  출발편", type=["xlsx","xls","csv"], key="arr")
with col3:
    extra_file = st.file_uploader("추가 일정 파일 업로드 (FLT, DES, START, END)", type=["xlsx","xls","csv"], key="extra")

use_sample = st.button("샘플 데이터 불러오기")

def find_col(df, target):
    target = target.strip().upper()
    mapping = {str(c).strip().upper(): c for c in df.columns}
    if target in mapping:
        return mapping[target]
    raise KeyError(f"필수 열 '{target}'을(를) 찾을 수 없습니다. 파일 헤더를 확인하세요.")

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
    raw = pd.read_csv("flights_sample.csv")
    dep_df = raw[["FLT_DEP","ATD"]].rename(columns={"FLT_DEP":"FLT"}); dep_df["REG"] = "HL-" + (dep_df.index+100).astype(str)
    arr_df = raw[["FLT_ARR","ATA"]].rename(columns={"FLT_ARR":"FLT"}); arr_df["REG"] = "HL-" + (arr_df.index+200).astype(str)
    extra_df = pd.read_csv("sample_extra.csv")
elif dep_file is not None and arr_file is not None:
    dep_df = load_dep(dep_file); arr_df = load_arr(arr_file)
    extra_df = load_extra(extra_file) if extra_file is not None else None
else:
    st.info("출발/도착 파일을 업로드하고(선택: 추가 일정 파일), 또는 '샘플 데이터 불러오기'를 눌러보세요.")
    st.stop()

# Compute windows & unify
# Departures
dep_df = dep_df.copy()
dep_df["ATD_dt"] = dep_df["ATD"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
dep_df["start"] = dep_df["ATD_dt"] - timedelta(minutes=int(dep_before))
dep_df["end"]   = dep_df["ATD_dt"] + timedelta(minutes=int(dep_after))
dep_df["marker"] = dep_df["ATD_dt"]; dep_df["type"] = "DEP"
dep_df["time_str"] = dep_df["ATD"].astype(str).str.zfill(4).str[:2] + ":" + dep_df["ATD"].astype(str).str.zfill(4).str[2:]

# Arrivals
arr_df = arr_df.copy()
arr_df["ATA_dt"] = arr_df["ATA"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
arr_df["start"] = arr_df["ATA_dt"] - timedelta(minutes=int(arr_before))
arr_df["end"]   = arr_df["ATA_dt"] + timedelta(minutes=int(arr_after))
arr_df["marker"] = arr_df["ATA_dt"]; arr_df["type"] = "ARR"
arr_df["time_str"] = arr_df["ATA"].astype(str).str.zfill(4).str[:2] + ":" + arr_df["ATA"].astype(str).str.zfill(4).str[2:]

# Normalize FLT display (ESR -> ZE) and append (REG)
def display_label(flt, reg, hide_flt):
    flt_str = str(flt).replace("ESR", "ZE")
    if hide_flt:
        return f"({reg})" if pd.notna(reg) and str(reg).strip() != "" else ""
    else:
        base = flt_str
        return f"{base} ({reg})" if pd.notna(reg) and str(reg).strip() != "" else base

dep_df["Label"] = dep_df.apply(lambda r: display_label(r["FLT"], r["REG"], hide_flt), axis=1)
arr_df["Label"] = arr_df.apply(lambda r: display_label(r["FLT"], r["REG"], hide_flt), axis=1)

# Extra schedule
extra_df_clean = None
if extra_df is not None and len(extra_df) > 0:
    ex = extra_df.copy()
    ex["start_dt"] = ex["START"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
    ex["end_dt"]   = ex["END"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
    ex["start"] = ex["start_dt"]; ex["end"] = ex["end_dt"]; ex["marker"] = ex["start_dt"]
    ex["type"] = "EXTRA"
    ex["Label"] = ex.apply(lambda r: f"{str(r['FLT']).replace('ESR','ZE')} ({r['DES']})", axis=1)
    ex["time_str"] = ex["start_dt"].dt.strftime("%H:%M")
    extra_df_clean = ex[["Label","start","end","marker","type","time_str"]]

# Unified table, sorted by start
frames = [
    dep_df[["Label","start","end","marker","type","time_str"]],
    arr_df[["Label","start","end","marker","type","time_str"]]
]
if extra_df_clean is not None:
    frames.append(extra_df_clean)
all_df = pd.concat(frames, ignore_index=True).sort_values("start").reset_index(drop=True)

# -------- Small-offset label collision minimization --------
# Sort by marker time; if adjacent markers are within threshold, nudge labels slightly.
all_df = all_df.reset_index(drop=False).rename(columns={"index":"row_id"})
all_df_sorted = all_df.sort_values("marker").reset_index(drop=True)

min_dx = timedelta(minutes=6)   # consider as "close"
y_nudge = 0.12                  # small vertical offset
x_nudge = timedelta(minutes=1)  # small horizontal offset

y_offsets = [0.0] * len(all_df)
x_offsets = [timedelta(0)] * len(all_df)

for i in range(1, len(all_df_sorted)):
    prev = all_df_sorted.loc[i-1]; curr = all_df_sorted.loc[i]
    if (curr["marker"] - prev["marker"]) < min_dx:
        direction = 1 if (i % 2 == 1) else -1
        y_offsets[curr["row_id"]] += direction * y_nudge
        x_offsets[curr["row_id"]] += x_nudge
        if y_offsets[prev["row_id"]] == 0.0:
            y_offsets[prev["row_id"]] -= direction * y_nudge
            x_offsets[prev["row_id"]] -= x_nudge

all_df["y_off"] = y_offsets; all_df["x_off"] = x_offsets

# ---- Timeline (Matplotlib) ----
fig, ax = plt.subplots(figsize=(12, 8))
for _, row in all_df.sort_values("start").iterrows():
    color = "red" if row["type"]=="DEP" else ("blue" if row["type"]=="ARR" else "orange")
    y = row["row_id"]
    ax.plot([row["start"], row["end"]], [y, y], linewidth=3, color=color)
    if row["Label"]:
        ax.text(row["end"] + timedelta(minutes=5), y, row["Label"], va="center", fontsize=9, color=color)
    ax.plot(row["marker"], y, marker="o", color=color, markersize=5)
    ax.text(row["marker"] + row["x_off"], y + 0.18 + row["y_off"], row["time_str"], fontsize=8, color=color)

from matplotlib.lines import Line2D
legend_elems = [
    Line2D([0],[0], color='red', lw=3, label='출발'),
    Line2D([0],[0], color='blue', lw=3, label='도착'),
    Line2D([0],[0], color='orange', lw=3, label='추가 일정'),
    Line2D([0],[0], marker='o', color='black', lw=0, label='ATD/ATA/START', markerfacecolor='black', markersize=5)
]
ax.legend(handles=legend_elems, loc="upper left")

ax.set_yticks([]); ax.tick_params(axis='y', which='both', left=False, labelleft=False)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
for lbl in ax.get_xticklabels():
    lbl.set_rotation(0); lbl.set_ha('center')
ax.set_title("운항 작업 타임라인 (작업 시작시간 기준 정렬)")
ax.grid(True, axis="x", linestyle="--", alpha=0.3)

# ---- Overlap line chart (DEP & ARR only) ----
dep_mask = all_df["type"]=="DEP"; arr_mask = all_df["type"]=="ARR"
start_time = all_df["start"].min(); end_time = all_df["end"].max()
time_range = pd.date_range(start=start_time, end=end_time, freq=f"{interval_min}min")
dep_counts = [ ((dep_mask) & (all_df["start"]<=t) & (all_df["end"]>t)).sum() for t in time_range ]
arr_counts = [ ((arr_mask) & (all_df["start"]<=t) & (all_df["end"]>t)).sum() for t in time_range ]
count_df = pd.DataFrame({"Time": time_range, "Departure_Count": dep_counts, "Arrival_Count": arr_counts})

fig2, ax2 = plt.subplots(figsize=(12, 3.5))
ax2.plot(count_df["Time"], count_df["Departure_Count"], label="출발", color="red", linewidth=2)
ax2.plot(count_df["Time"], count_df["Arrival_Count"], label="도착", color="blue", linewidth=2)
ax2.set_ylabel("개수"); ax2.set_xlabel("시간")
ax2.set_title("운항편 중복 개수")
ax2.legend(); ax2.grid(True, alpha=0.3)
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
for lbl in ax2.get_xticklabels():
    lbl.set_rotation(0); lbl.set_ha('center')

st.pyplot(fig, use_container_width=True)
st.pyplot(fig2, use_container_width=True)

# Preview
st.markdown("#### 통합 데이터 (상위 12행)")
st.dataframe(all_df.head(12))

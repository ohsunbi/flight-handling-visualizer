
import io
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams
from datetime import datetime, date, time, timedelta

# Optional interactive timeline
import plotly.express as px
import plotly.graph_objects as go

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
use_interactive = st.sidebar.checkbox("인터랙티브(툴팁) 타임라인 사용", value=True)

st.title(f"이스타항공 운항편 차트 ({base_date.strftime('%Y-%m-%d')})")

st.sidebar.markdown("---")
st.sidebar.write("각 파일은 헤더 포함, 출발= **FLT, ATD, REG** / 도착= **FLT, ATA, REG** 열이 있어야 합니다.")

col1, col2 = st.columns(2)
with col1:
    dep_file = st.file_uploader("Departures file  ·  도착편", type=["xlsx","csv"], key="dep")
with col2:
    arr_file = st.file_uploader("Arrivals file  ·  출발편", type=["xlsx","csv"], key="arr")
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
def display_label(flt, reg, hide_flt):
    flt_str = str(flt).replace("ESR", "ZE")
    if hide_flt:
        return f"({reg})" if pd.notna(reg) and str(reg).strip() != "" else ""
    else:
        base = flt_str
        return f"{base} ({reg})" if pd.notna(reg) and str(reg).strip() != "" else base

dep_df["Label"] = dep_df.apply(lambda r: display_label(r["FLT"], r["REG"], hide_flt), axis=1)
arr_df["Label"] = arr_df.apply(lambda r: display_label(r["FLT"], r["REG"], hide_flt), axis=1)

# Unified table, sorted by start
all_df = pd.concat([
    dep_df[["Label","FLT","REG","start","end","marker","type","time_str"]],
    arr_df[["Label","FLT","REG","start","end","marker","type","time_str"]]
], ignore_index=True).sort_values("start").reset_index(drop=True)

# -------- Label collision avoidance (simple heuristic) --------
# Shift labels horizontally/vertically when two consecutive items are too close.
label_dx_min = timedelta(minutes=6)   # minimum horizontal gap
label_dy = 0.25                       # vertical nudge
last_x = None
toggle = 1
y_offsets = []
x_offsets = []
for i, row in all_df.iterrows():
    x = row["marker"]
    if last_x is None:
        y_offsets.append(0.0); x_offsets.append(timedelta(0))
    else:
        if abs((x - last_x)) < label_dx_min:
            y_offsets.append(label_dy * toggle)
            x_offsets.append(timedelta(minutes=3) * toggle)
            toggle *= -1
        else:
            y_offsets.append(0.0); x_offsets.append(timedelta(0))
    last_x = x
all_df["y_off"] = y_offsets
all_df["x_off"] = x_offsets

# ---- Timeline ----
if use_interactive:
    # Plotly timeline with hover
    plot_df = all_df.copy()
    plot_df["y"] = plot_df.index  # numeric y
    plot_df["type_color"] = plot_df["type"].map({"DEP":"red","ARR":"blue"})
    plot_df["hover"] = (
        "구분: " + plot_df["type"].map({"DEP":"출발","ARR":"도착"}) +
        "<br>편명: " + plot_df["FLT"].astype(str).str.replace("ESR","ZE") +
        "<br>REG: " + plot_df["REG"].astype(str) +
        "<br>작업: " + plot_df["start"].dt.strftime("%H:%M") + " ~ " + plot_df["end"].dt.strftime("%H:%M") +
        "<br>시각: " + plot_df["time_str"]
    )

    fig_tl = go.Figure()
    # bars
    for _, r in plot_df.iterrows():
        fig_tl.add_trace(go.Scatter(
            x=[r["start"], r["end"]],
            y=[r["y"], r["y"]],
            mode="lines",
            line=dict(color=r["type_color"], width=6),
            hoverinfo="text",
            text=r["hover"],
            showlegend=False
        ))
    # markers
    fig_tl.add_trace(go.Scatter(
        x=plot_df["marker"],
        y=plot_df["y"],
        mode="markers",
        marker=dict(color=plot_df["type_color"], size=6),
        hoverinfo="text",
        text=plot_df["hover"],
        name="ATD/ATA"
    ))
    fig_tl.update_layout(
        height=500,
        title="운항 작업 타임라인 (툴팁 포함)",
        xaxis=dict(tickformat="%H:%M"),
        yaxis=dict(showticklabels=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10,r=10,t=50,b=40)
    )
    # custom legend
    fig_tl.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='red', width=6), name='출발'))
    fig_tl.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='blue', width=6), name='도착'))
    st.plotly_chart(fig_tl, use_container_width=True)
else:
    # Matplotlib static with collision-avoidance
    fig, ax = plt.subplots(figsize=(12, 8))
    for i, row in all_df.iterrows():
        color = "red" if row["type"]=="DEP" else "blue"
        y = i + row["y_off"]
        ax.plot([row["start"], row["end"]], [y, y], linewidth=3, color=color)
        if row["Label"]:
            ax.text(row["end"] + timedelta(minutes=5), y, row["Label"], va="center", fontsize=9, color=color)
        ax.plot(row["marker"], y, marker="o", color=color, markersize=5)
        ax.text(row["marker"] + timedelta(minutes=3) + row["x_off"], y+0.18, row["time_str"], fontsize=8, color=color)

    # Legend
    from matplotlib.lines import Line2D
    legend_elems = [
        Line2D([0],[0], color='red', lw=3, label='출발'),
        Line2D([0],[0], color='blue', lw=3, label='도착'),
        Line2D([0],[0], marker='o', color='black', lw=0, label='ATD/ATA', markerfacecolor='black', markersize=5)
    ]
    ax.legend(handles=legend_elems, loc="upper left")
    ax.set_yticks([]); ax.tick_params(axis='y', which='both', left=False, labelleft=False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    for lbl in ax.get_xticklabels(): lbl.set_rotation(0); lbl.set_ha('center')
    ax.set_title("운항 작업 타임라인 (작업 시작시간 기준 정렬)")
    ax.grid(True, axis="x", linestyle="--", alpha=0.3)
    st.pyplot(fig, use_container_width=True)

# ---- Overlap line chart ----
start_time = all_df["start"].min(); end_time = all_df["end"].max()
time_range = pd.date_range(start=start_time, end=end_time, freq=f"{interval_min}min")
dep_counts = [ ((all_df["type"]=="DEP") & (all_df["start"]<=t) & (all_df["end"]>t)).sum() for t in time_range ]
arr_counts = [ ((all_df["type"]=="ARR") & (all_df["start"]<=t) & (all_df["end"]>t)).sum() for t in time_range ]
count_df = pd.DataFrame({"Time": time_range, "출발": dep_counts, "도착": arr_counts})

if use_interactive:
    fig_line = px.line(count_df, x="Time", y=["출발","도착"], title="운항편 중복 개수")
    fig_line.update_layout(xaxis=dict(tickformat="%H:%M"))
    st.plotly_chart(fig_line, use_container_width=True)
else:
    fig2, ax2 = plt.subplots(figsize=(12, 3.5))
    ax2.plot(count_df["Time"], count_df["출발"], label="출발", color="red", linewidth=2)
    ax2.plot(count_df["Time"], count_df["도착"], label="도착", color="blue", linewidth=2)
    ax2.set_ylabel("개수"); ax2.set_xlabel("시간")
    ax2.set_title("운항편 중복 개수")
    ax2.legend(); ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    for lbl in ax2.get_xticklabels(): lbl.set_rotation(0); lbl.set_ha('center')
    st.pyplot(fig2, use_container_width=True)

# Preview
st.markdown("#### 통합 데이터 (상위 12행)")
st.dataframe(all_df.head(12))

# Note: For PNG export, interactive charts are not embedded; keeping prior PNG download out for simplicity.

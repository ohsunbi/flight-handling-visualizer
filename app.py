
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
st.sidebar.write("데이터 포맷: 컬럼 `FLT_DEP, ATD, FLT_ARR, ATA` (ATD/ATA는 HHMM)")

uploaded = st.file_uploader("CSV 또는 Excel 업로드", type=["csv", "xlsx"])
sample_btn = st.button("샘플 데이터 불러오기")

def load_sample():
    return pd.read_csv("flights_sample.csv")

def normalize_columns(df):
    cols = [str(c).strip().upper() for c in df.columns]
    df.columns = cols
    # Case A: already standard
    if {"FLT_DEP","ATD","FLT_ARR","ATA"}.issubset(set(cols)):
        return df[["FLT_DEP","ATD","FLT_ARR","ATA"]].copy()
    # Case B: first 4 columns
    if len(df.columns) >= 4:
        tmp = df.iloc[:, :4].copy()
        tmp.columns = ["FLT_DEP","ATD","FLT_ARR","ATA"]
        return tmp
    raise ValueError("헤더를 인식할 수 없습니다. FLT_DEP, ATD, FLT_ARR, ATA 4개 컬럼이 필요합니다.")

def hhmm_to_datetime(base_date, hhmm, service_hour):
    s = str(hhmm).strip()
    if s.isdigit() and len(s) in (3,4):
        s = s.zfill(4)
    tt = datetime.strptime(s, "%H%M").time()
    dt = datetime.combine(base_date, tt)
    if time(tt.hour, tt.minute) < time(service_hour, 0):
        dt += timedelta(days=1)
    return dt

if uploaded is not None:
    if uploaded.name.lower().endswith(".csv"):
        raw = pd.read_csv(uploaded)
    else:
        raw = pd.read_excel(uploaded)
    df = normalize_columns(raw)
elif sample_btn:
    df = load_sample()
else:
    st.info("좌측에서 파일을 업로드하거나 '샘플 데이터 불러오기'를 클릭하세요.")
    df = None

if df is not None:
    # Compute windows
    df["ATD_dt"] = df["ATD"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
    df["ATA_dt"] = df["ATA"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
    df["DEP_start"] = df["ATD_dt"] - timedelta(minutes=50)
    df["DEP_end"]   = df["ATD_dt"] + timedelta(minutes=10)
    df["ARR_start"] = df["ATA_dt"] - timedelta(minutes=20)
    df["ARR_end"]   = df["ATA_dt"] + timedelta(minutes=30)

    # ---- Top timeline: flights with markers ----
    fig1, ax1 = plt.subplots(figsize=(12, 7))
    for i, row in df.iterrows():
        # Departure window (blue)
        ax1.plot([row["DEP_start"], row["DEP_end"]], [i, i], linewidth=4)
        ax1.text(row["DEP_end"] + timedelta(minutes=5), i, row["FLT_DEP"], va="center", fontsize=8)
        ax1.plot(row["ATD_dt"], i, marker="o")
        ax1.text(row["ATD_dt"] + timedelta(minutes=3), i+0.15, row["ATD"], fontsize=7)

    for i, row in df.iterrows():
        # Arrival window (red-ish, but default color used to comply with Streamlit chart color rule)
        ax1.plot([row["ARR_start"], row["ARR_end"]], [i+0.4, i+0.4], linewidth=4)
        ax1.text(row["ARR_end"] + timedelta(minutes=5), i+0.4, row["FLT_ARR"], va="center", fontsize=8)
        ax1.plot(row["ATA_dt"], i+0.4, marker="o")
        ax1.text(row["ATA_dt"] + timedelta(minutes=3), i+0.55, row["ATA"], fontsize=7)

    ax1.set_yticks([])
    ax1.set_title("Flight Handling Timeline (ATD/ATA markers included)")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    fig1.autofmt_xdate()

    # ---- Bottom line: overlaps every N minutes ----
    start_time = min(df["DEP_start"].min(), df["ARR_start"].min())
    end_time   = max(df["DEP_end"].max(),   df["ARR_end"].max())
    time_range = pd.date_range(start=start_time, end=end_time, freq=f"{interval_min}min")
    dep_counts, arr_counts = [], []
    for t in time_range:
        dep_counts.append(((df["DEP_start"] <= t) & (df["DEP_end"] > t)).sum())
        arr_counts.append(((df["ARR_start"] <= t) & (df["ARR_end"] > t)).sum())
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

    # ---- Show tables + download ----
    st.markdown("#### 계산 결과 (상위 10행)")
    st.dataframe(df.head(10))

    buf = io.BytesIO()
    fig_all, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={"height_ratios":[3,1]}, sharex=False)
    # Replot into export figure
    # top
    for i, row in df.iterrows():
        ax_top.plot([row["DEP_start"], row["DEP_end"]], [i, i], linewidth=4)
        ax_top.text(row["DEP_end"] + timedelta(minutes=5), i, row["FLT_DEP"], va="center", fontsize=8)
        ax_top.plot(row["ATD_dt"], i, marker="o")
        ax_top.text(row["ATD_dt"] + timedelta(minutes=3), i+0.15, row["ATD"], fontsize=7)
    for i, row in df.iterrows():
        ax_top.plot([row["ARR_start"], row["ARR_end"]], [i+0.4, i+0.4], linewidth=4)
        ax_top.text(row["ARR_end"] + timedelta(minutes=5), i+0.4, row["FLT_ARR"], va="center", fontsize=8)
        ax_top.plot(row["ATA_dt"], i+0.4, marker="o")
        ax_top.text(row["ATA_dt"] + timedelta(minutes=3), i+0.55, row["ATA"], fontsize=7)
    ax_top.set_yticks([])
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

else:
    st.stop()

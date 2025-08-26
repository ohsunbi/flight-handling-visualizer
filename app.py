
import io
import math
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import transforms
from datetime import datetime, date, time, timedelta

st.set_page_config(page_title="Flight Handling Schedule", layout="wide")


# ===== Global Settings =====
F_BEFORE = 20   # F 편일 때 기본 before 시간
F_AFTER  = 10   # F 편일 때 기본 after 시간

# ---- Sidebar controls ----
st.sidebar.header("Settings")
service_start_hour = st.sidebar.number_input("Service day starts at (hour)", min_value=0, max_value=23, value=2, step=1)
base_date = st.sidebar.date_input("BASE_DATE", value=date.today())
interval_min = st.sidebar.selectbox("Overlap interval (min)", options=[10, 20, 30], index=2)

# Extra 데이터 ON/OFF 토글 추가
use_extra = st.sidebar.checkbox("Include Extra data", value=True)

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
st.sidebar.write("- Departures: **FLT, ATD, (optional: ETD, STD), REG**")
st.sidebar.write("- Arrivals: **FLT, ATA, (optional: ETA, STA), REG**")
st.sidebar.write("- Extra data (mixed dep/arr): **FLT, DES, ATA, ATD**  (HHMM)")

col1, col2, col3 = st.columns(3)
with col1:
    dep_file = st.file_uploader("Departures file", type=["xlsx","xls","csv"], key="dep")
with col2:
    arr_file = st.file_uploader("Arrivals file", type=["xlsx","xls","csv"], key="arr")
with col3:
    extra_file = st.file_uploader("Extra data file (FLT, DES, ATA, ATD)", type=["xlsx","xls","csv"], key="extra")

col_btn1, col_btn2 = st.columns([1, 1])
with col_btn1:
    use_sample = st.button("Load sample data")
with col_btn2:
    reset_data = st.button("Reset data")

# Reset logic
if reset_data:
    # clear file uploaders & any temp flags
    for k in ("dep", "arr", "extra"):
        st.session_state.pop(k, None)
    for k in ("dep_df", "arr_df", "extra_df", "use_sample"):
        st.session_state.pop(k, None)
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

def find_col(df, target):
    target = target.strip().upper()
    mapping = {str(c).strip().upper(): c for c in df.columns}
    if target in mapping:
        return mapping[target]
    raise KeyError(f"Required column '{target}' not found.")

def read_tabular(file):
    # file is an UploadedFile with .name or a path-like when using samples
    if hasattr(file, "name"):
        name = file.name.lower()
        if name.endswith(".csv"):
            return pd.read_csv(file)
        else:
            return pd.read_excel(file)
    else:
        # assume it's a path string
        p = str(file).lower()
        if p.endswith(".csv"):
            return pd.read_csv(file)
        else:
            return pd.read_excel(file)

def load_dep(file):
    df = read_tabular(file)
    # case-insensitive column map
    cmap = {str(c).strip().upper(): c for c in df.columns}

    def get(col):
        return df[cmap[col]] if col in cmap else pd.Series([pd.NA] * len(df))

    if "FLT" not in cmap:
        raise KeyError("Departures must include FLT column.")
    c_flt = cmap["FLT"]
    reg_series = get("REG")
    out = pd.DataFrame({
        "FLT": df[c_flt],
        "REG": reg_series if reg_series is not None else ""
    })
    # optional time columns: ATD > ETD > STD
    out["ATD"] = get("ATD")
    out["ETD"] = get("ETD")
    out["STD"] = get("STD")
    return out

def load_arr(file):
    df = read_tabular(file)
    cmap = {str(c).strip().upper(): c for c in df.columns}

    def get(col):
        return df[cmap[col]] if col in cmap else pd.Series([pd.NA] * len(df))

    if "FLT" not in cmap:
        raise KeyError("Arrivals must include FLT column.")
    c_flt = cmap["FLT"]
    reg_series = get("REG")
    out = pd.DataFrame({
        "FLT": df[c_flt],
        "REG": reg_series if reg_series is not None else ""
    })
    # optional time columns: ATA > ETA > STA
    out["ATA"] = get("ATA")
    out["ETA"] = get("ETA")
    out["STA"] = get("STA")
    return out

def load_extra(file):
    if file is None: return None
    df = read_tabular(file)
    # require FLT and at least one of ATA/ATD for extra
    cmap = {str(c).strip().upper(): c for c in df.columns}
    if "FLT" not in cmap:
        raise KeyError("Extra must include FLT column.")
    c_flt = cmap["FLT"]
    # DES optional
    des_col = cmap["DES"] if "DES" in cmap else None
    ata_col = cmap["ATA"] if "ATA" in cmap else None
    atd_col = cmap["ATD"] if "ATD" in cmap else None
    out = pd.DataFrame({"FLT": df[c_flt]})
    if des_col: out["DES"] = df[des_col]
    if ata_col: out["ATA"] = df[ata_col]
    if atd_col: out["ATD"] = df[atd_col]
    return out

def hhmm_to_datetime(base_date, hhmm, service_hour):
    # 1) NA 처리
    if pd.isna(hhmm):
        return None

    # 2) datetime/Timestamp는 그대로 사용
    if isinstance(hhmm, (datetime, pd.Timestamp)):
        tt = hhmm.time()
    else:
        # 3) 숫자면 반올림→정수→4자리 제로패딩 (313.0 -> "0313")
        if isinstance(hhmm, (int, float)) and not (isinstance(hhmm, float) and math.isnan(hhmm)):
            try:
                val = int(round(hhmm))
                s = f"{val:04d}"
            except Exception:
                return None
        else:
            # 4) 문자열이면 숫자만 추출 + 3자리면 0 패드
            s_raw = str(hhmm).strip()
            digits = "".join(ch for ch in s_raw if ch.isdigit())
            if len(digits) == 3:
                digits = "0" + digits
            s = digits

        if len(s) != 4:
            return None
        try:
            tt = datetime.strptime(s, "%H%M").time()
        except ValueError:
            return None

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

if not use_extra:
    extra_df = None

def hhmm_text(v):
    s = str(v).zfill(4)
    return s[:2] + ":" + s[2:]

def label_for(flt, reg):
    parts = []
    if show_flt: parts.append(str(flt).replace("ESR","ZE"))
    if show_reg and pd.notna(reg) and str(reg).strip(): parts.append(str(reg))
    return " / ".join(parts)

# ==============================
# Compute windows with fallbacks
# ==============================

# ---- DEPARTURES (ATD > ETD > STD) ----
dep_df = dep_df.copy()

def pick_time_dep(r):

    # 반영 우선 순위, 현재는 ATD 기반
    
    for k in ("ATD", "ETD", "STD"):
    # for k in ("STD", "ATD", "ETD"):
        
        v = r.get(k, pd.NA)
        if pd.notna(v) and str(v).strip() != "":
            return v
    return pd.NA



dep_df["TIME_RAW"] = dep_df.apply(pick_time_dep, axis=1)
dep_df = dep_df[pd.notna(dep_df["TIME_RAW"])].reset_index(drop=True)  # drop rows with no time

dep_df["time_dt"] = dep_df["TIME_RAW"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
dep_df["time_dt"] = pd.to_datetime(dep_df["time_dt"], errors="coerce")
dep_df = dep_df.dropna(subset=["time_dt"]).reset_index(drop=True)

# F-flag
dep_df["is_F"] = dep_df["FLT"].astype(str).str.strip().str.upper().str.endswith("F")
dep_df["start"] = dep_df.apply(
    lambda r: r["time_dt"] - timedelta(minutes=(F_BEFORE if r["is_F"] else int(dep_before))), axis=1
)
dep_df["end"] = dep_df.apply(
    lambda r: r["time_dt"] + timedelta(minutes=(F_AFTER if r["is_F"] else int(dep_after))), axis=1
)

dep_df["marker"]  = dep_df["time_dt"]
dep_df["type"]    = "DEP"
dep_df["time_str"] = dep_df["time_dt"].dt.strftime("%H:%M")
dep_df["Label"]   = dep_df.apply(lambda r: label_for(r["FLT"], r["REG"]), axis=1)

# ---- ARRIVALS (ATA > ETA > STA) ----
arr_df = arr_df.copy()

def pick_time_arr(r):

    # 반영 우선 순위, 현재는 ATA 기반
    
    for k in ("ATA", "ETA", "STA"):     
    # for k in ("STA", "ATA", "ETA"):      
        v = r.get(k, pd.NA)
        if pd.notna(v) and str(v).strip() != "":
            return v
    return pd.NA

arr_df["TIME_RAW"] = arr_df.apply(pick_time_arr, axis=1)
arr_df = arr_df[pd.notna(arr_df["TIME_RAW"])].reset_index(drop=True)  # drop rows with no time

arr_df["time_dt"] = arr_df["TIME_RAW"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
arr_df["time_dt"] = pd.to_datetime(arr_df["time_dt"], errors="coerce")
arr_df = arr_df.dropna(subset=["time_dt"]).reset_index(drop=True)

# F-flag
arr_df["is_F"] = arr_df["FLT"].astype(str).str.strip().str.upper().str.endswith("F")


# 변경: F면 -20 ~ +10, 아니면 기존 사이드바 값
arr_df["start"] = arr_df.apply(
    lambda r: r["time_dt"] - timedelta(minutes=(F_BEFORE if r["is_F"] else int(arr_before))), axis=1
)
arr_df["end"] = arr_df.apply(
    lambda r: r["time_dt"] + timedelta(minutes=(F_AFTER if r["is_F"] else int(arr_after))), axis=1
)

arr_df["marker"]  = arr_df["time_dt"]
arr_df["type"]    = "ARR"
arr_df["time_str"] = arr_df["time_dt"].dt.strftime("%H:%M")
arr_df["Label"]   = arr_df.apply(lambda r: label_for(r["FLT"], r["REG"]), axis=1)

# Extra split (unchanged logic: extras still use ATA/ATD when present)
extra_dep = None; extra_arr = None
if isinstance(extra_file, type(None)) and use_sample and isinstance(extra_df, pd.DataFrame):
    pass  # sample already loaded
if extra_df is not None and isinstance(extra_df, pd.DataFrame) and len(extra_df) > 0:
    ex = extra_df.copy()
    if "ATD" in ex.columns:
        ed = ex[ex["ATD"].notna()].copy()
        if len(ed)>0:
            ed["ATD_dt"] = ed["ATD"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
            ed["is_F"] = ed["FLT"].astype(str).str.strip().str.upper().str.endswith("F")
            ed["start"] = ed.apply(lambda r: r["ATD_dt"] - timedelta(minutes=(F_BEFORE if r["is_F"] else int(dep_before))), axis=1)
            ed["end"]   = ed.apply(lambda r: r["ATD_dt"] + timedelta(minutes=(F_AFTER  if r["is_F"] else int(dep_after))),  axis=1)

            ed["marker"] = ed["ATD_dt"]
            ed["type"] = "DEP_EXTRA"
            ed["time_str"] = ed["ATD"].apply(hhmm_text)
            ed["Label"] = ed.apply(lambda r: label_for(str(r.get("FLT","")).replace("ESR","ZE"), r.get("REG","")), axis=1) if ("REG" in ed.columns) else ed["FLT"].apply(lambda f: label_for(str(f).replace("ESR","ZE"), ""))
            extra_dep = ed[["Label","start","end","marker","type","time_str"]]
    if "ATA" in ex.columns:
        ea = ex[ex["ATA"].notna()].copy()
        if len(ea)>0:
            ea["ATA_dt"] = ea["ATA"].apply(lambda x: hhmm_to_datetime(base_date, x, service_start_hour))
            ea["is_F"] = ea["FLT"].astype(str).str.strip().str.upper().str.endswith("F")
            ea["start"] = ea.apply(lambda r: r["ATA_dt"] - timedelta(minutes=(F_BEFORE if r["is_F"] else int(arr_before))), axis=1)
            ea["end"]   = ea.apply(lambda r: r["ATA_dt"] + timedelta(minutes=(F_AFTER  if r["is_F"] else int(arr_after))),  axis=1)
            ea["marker"] = ea["ATA_dt"]
            ea["type"] = "ARR_EXTRA"
            ea["time_str"] = ea["ATA"].apply(hhmm_text)
            ea["Label"] = ea.apply(lambda r: label_for(str(r.get("FLT","")).replace("ESR","ZE"), r.get("REG","")), axis=1) if ("REG" in ea.columns) else ea["FLT"].apply(lambda f: label_for(str(f).replace("ESR","ZE"), ""))
            extra_arr = ea[["Label","start","end","marker","type","time_str"]]

# Colors (Reversed scheme: Arrivals blue, Departures red; extras cyan/orange)
COL_ARR    = "#1f77b4"   # blue
COL_DEP    = "#d62728"   # red
COL_ARR_EX = "#17becf"   # cyan (arrival extra)
COL_DEP_EX = "#ff7f0e"   # orange (departure extra)

# ---- Build intervals for overlaps (incl. extras) ----
def _to_intervals(df):
    return df[["start","end"]].copy()

dep_intervals = _to_intervals(dep_df) if len(dep_df)>0 else pd.DataFrame(columns=["start","end"])
arr_intervals = _to_intervals(arr_df) if len(arr_df)>0 else pd.DataFrame(columns=["start","end"])
if extra_dep is not None and len(extra_dep)>0:
    dep_intervals = pd.concat([dep_intervals, _to_intervals(extra_dep)], ignore_index=True)
if extra_arr is not None and len(extra_arr)>0:
    arr_intervals = pd.concat([arr_intervals, _to_intervals(extra_arr)], ignore_index=True)

if len(dep_intervals)==0 and len(arr_intervals)==0:
    st.warning("No records to plot after applying time fallbacks.")
    st.stop()

start_candidates = []
end_candidates = []
if len(dep_intervals)>0:
    start_candidates.append(dep_intervals["start"].min())
    end_candidates.append(dep_intervals["end"].max())
if len(arr_intervals)>0:
    start_candidates.append(arr_intervals["start"].min())
    end_candidates.append(arr_intervals["end"].max())

start_time = min(start_candidates)
end_time   = max(end_candidates)

time_range = pd.date_range(start=start_time, end=end_time, freq=f"{interval_min}min")

def count_overlaps(intervals, t):
    if len(intervals)==0: return 0
    return ((intervals["start"] <= t) & (intervals["end"] > t)).sum()

# compute overlaps at the midpoint of each interval
mid_times = [time_range[i] + (time_range[i+1] - time_range[i]) / 2
             for i in range(len(time_range) - 1)]
dep_counts = [count_overlaps(dep_intervals, t) for t in mid_times]
arr_counts = [count_overlaps(arr_intervals, t) for t in mid_times]


# ---- Timeline with inline overlap numbers (two rows) ----
fig1, ax1 = plt.subplots(figsize=(12, 8))

# departures block
dep_block = pd.concat([
    dep_df[["Label","start","end","marker","type","time_str"]],
    (extra_dep if isinstance(extra_dep, pd.DataFrame) else pd.DataFrame(columns=["Label","start","end","marker","type","time_str"]))
], ignore_index=True).sort_values("start").reset_index(drop=True)

dep_normal_labeled = False
dep_extra_labeled = False
for i, row in dep_block.iterrows():
    is_extra = ("EXTRA" in row["type"])
    color = COL_DEP_EX if is_extra else COL_DEP
    if is_extra:
        label_once = "Departure (extra)" if not dep_extra_labeled else ""
        dep_extra_labeled = True
    else:
        label_once = "Departure" if not dep_normal_labeled else ""
        dep_normal_labeled = True

    ax1.plot([row["start"], row["end"]], [i, i], color=color, linewidth=4, label=label_once)
    if row["Label"]:
        ax1.text(row["end"] + timedelta(minutes=5), i, row["Label"], va="center", fontsize=7, color=color)
    ax1.plot(row["marker"], i, marker=("D" if is_extra else "o"), color=color)
    # time label at top-left of marker
    ax1.text(row["marker"] - timedelta(minutes=3), i+0.15, row["time_str"],
             fontsize=7, color=color, ha="right", va="bottom")

# arrivals block
arr_block = pd.concat([
    arr_df[["Label","start","end","marker","type","time_str"]],
    (extra_arr if isinstance(extra_arr, pd.DataFrame) else pd.DataFrame(columns=["Label","start","end","marker","type","time_str"]))
], ignore_index=True).sort_values("start").reset_index(drop=True)

arr_normal_labeled = False
arr_extra_labeled = False
for i, row in arr_block.iterrows():
    y = i + 0.6
    is_extra = ("EXTRA" in row["type"])
    color = COL_ARR_EX if is_extra else COL_ARR
    if is_extra:
        label_once = "Arrival (extra)" if not arr_extra_labeled else ""
        arr_extra_labeled = True
    else:
        label_once = "Arrival" if not arr_normal_labeled else ""
        arr_normal_labeled = True

    ax1.plot([row["start"], row["end"]], [y, y], color=color, linewidth=4, label=label_once)
    if row["Label"]:
        ax1.text(row["end"] + timedelta(minutes=5), y, row["Label"], va="center", fontsize=7, color=color)
    ax1.plot(row["marker"], y, marker=("D" if is_extra else "o"), color=color)
    # time label at top-left of marker
    ax1.text(row["marker"] - timedelta(minutes=3), y+0.15, row["time_str"],
             fontsize=7, color=color, ha="right", va="bottom")

# Totals and legend
total_dep = len(dep_block)
total_arr = len(arr_block)
ax1.text(
    0.01, 1.02,
    f"{base_date.strftime('%Y-%m-%d')} ({base_date.strftime('%a').upper()})",
    transform=ax1.transAxes, fontsize=11, ha="left", va="bottom"
)


ax1.text(0.99, 1.02, f"Total Departure: {total_dep}   Total Arrival: {total_arr}", transform=ax1.transAxes,
         fontsize=11, ha="right", va="bottom", color="black")

ax1.legend(loc="upper left")
ax1.set_yticks([]); ax1.tick_params(axis='y', which='both', left=False, labelleft=False)
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
for lbl in ax1.get_xticklabels(): lbl.set_rotation(0); lbl.set_ha('center')
ax1.set_title("Flight Handling Timeline")

# Inline overlap numbers (two rows, top line = Departure (red), bottom line = Arrival (blue))
trans = transforms.blended_transform_factory(ax1.transData, ax1.transAxes)
max_d = max(dep_counts) if dep_counts else 1
max_a = max(arr_counts) if arr_counts else 1

# place at interval centers (use mid_times)
for i, mid in enumerate(mid_times):
    d = dep_counts[i]; a = arr_counts[i]

    # 합계(검정, 최상단) — 0이면 표시 안 함
    total_val = d + a
    if total_val > 0:
        ax1.text(mid, -0.06, str(total_val), transform=trans,
                 ha="center", va="top", fontsize=8, color="black")

    if d > 0:
        alpha = 0.35 + 0.65 * (d / max_d)
        ax1.text(mid, -0.10, str(d), transform=trans, ha="center", va="top",
                 fontsize=8, color=(0.84, 0.15, 0.16, alpha))  # Departure (red)

    if a > 0:
        alpha = 0.35 + 0.65 * (a / max_a)
        ax1.text(mid, -0.14, str(a), transform=trans, ha="center", va="top",
                 fontsize=8, color=(0.12, 0.46, 0.70, alpha))  # Arrival (blue)



# Align x-limits and grid without gray bands
ax1.set_xlim(start_time, end_time)
ax1.grid(True, axis="x", linestyle="--", alpha=0.3)

# ----- Save / Download chart image -----
# filename: YYYY-MM-DD_Weekday_D{dep}_A{arr}.png
extra_tag = "(E)" if use_extra else ""
filename = f"{base_date.strftime('%Y-%m-%d')}_{base_date.strftime('%a')}_D{total_dep}_A{total_arr}{extra_tag}.png"



# Create PNG bytes
buf = io.BytesIO()
fig1.savefig(buf, format="png", dpi=200, bbox_inches="tight")
buf.seek(0)

# Download button
st.download_button(
    label="Download chart as PNG",
    data=buf,
    file_name=filename,
    mime="image/png"
)

# Render
st.pyplot(fig1, use_container_width=True)

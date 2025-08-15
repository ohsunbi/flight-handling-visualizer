
import io
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from matplotlib import transforms
from datetime import datetime, date, time, timedelta

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

col_btn1, col_btn2 = st.columns([1, 1])
with col_btn1:
    use_sample = st.button("Load sample data")
with col_btn2:
    reset_data = st.button("Reset data")

# Reset logic (replace this block)
if reset_data:
    # clear file uploaders & any temp flags
    for k in ("dep", "arr", "extra"):
        st.session_state.pop(k, None)

    # if you stored any dataframes/flags in session_state, clear them too (optional)
    for k in ("dep_df", "arr_df", "extra_df", "use_sample"):
        st.session_state.pop(k, None)

    # rerun (new API)
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        # fallback for very old Streamlit
        st.experimental_rerun()


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

def hhmm_text(v):
    s = str(v).zfill(4)
    return s[:2] + ":" + s[2:]

def label_for(flt, reg):
    parts = []
    if show_flt: parts.append(str(flt).replace("ESR","ZE"))
    if show_reg and pd.notna(reg) and str(reg).strip(): parts.append(str(reg))
    return " / ".join(parts)

# Compute windows
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

# Extra split
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

# Colors
COL_ARR = "#1f77b4"      # blue (base)
COL_DEP = "#d62728"      # red (base)
COL_ARR_EX = "#17becf"   # cyan for extra dep
COL_DEP_EX = "#ff7f0e"   # orange for extra arr

# ---- Build intervals for overlaps (incl. extras) ----
def _to_intervals(df):
    return df[["start","end"]].copy()

dep_intervals = _to_intervals(dep_df)
arr_intervals = _to_intervals(arr_df)
if extra_dep is not None: dep_intervals = pd.concat([dep_intervals, _to_intervals(extra_dep)], ignore_index=True)
if extra_arr is not None: arr_intervals = pd.concat([arr_intervals, _to_intervals(extra_arr)], ignore_index=True)

start_time = min(dep_intervals["start"].min() if len(dep_intervals)>0 else pd.Timestamp(base_date),
                 arr_intervals["start"].min() if len(arr_intervals)>0 else pd.Timestamp(base_date))
end_time   = max(dep_intervals["end"].max() if len(dep_intervals)>0 else pd.Timestamp(base_date)+timedelta(hours=23,minutes=59),
                 arr_intervals["end"].max() if len(arr_intervals)>0 else pd.Timestamp(base_date)+timedelta(hours=23,minutes=59))

time_range = pd.date_range(start=start_time, end=end_time, freq=f"{interval_min}min")

def count_overlaps(intervals, t):
    if len(intervals)==0: return 0
    return ((intervals["start"] <= t) & (intervals["end"] > t)).sum()

dep_counts = [count_overlaps(dep_intervals, t) for t in time_range]
arr_counts = [count_overlaps(arr_intervals, t) for t in time_range]

# ---- Timeline with inline overlap numbers (two rows) ----
fig1, ax1 = plt.subplots(figsize=(12, 8))

# departures block
dep_block = pd.concat([
    dep_df[["Label","start","end","marker","type","time_str"]],
    (extra_dep if extra_dep is not None else pd.DataFrame(columns=["Label","start","end","marker","type","time_str"]))
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
        ax1.text(row["end"] + timedelta(minutes=5), i, row["Label"], va="center", fontsize=8, color=color)
    ax1.plot(row["marker"], i, marker=("D" if is_extra else "o"), color=color)
    ax1.text(row["marker"] - timedelta(minutes=3), i+0.15, row["time_str"],
             fontsize=7, color=color, ha="right", va="bottom")

# arrivals block
arr_block = pd.concat([
    arr_df[["Label","start","end","marker","type","time_str"]],
    (extra_arr if extra_arr is not None else pd.DataFrame(columns=["Label","start","end","marker","type","time_str"]))
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
        ax1.text(row["end"] + timedelta(minutes=5), y, row["Label"], va="center", fontsize=8, color=color)
    ax1.plot(row["marker"], y, marker=("D" if is_extra else "o"), color=color)
    ax1.text(row["marker"] - timedelta(minutes=3), y+0.15, row["time_str"],
             fontsize=7, color=color, ha="right", va="bottom")

# Totals and legend
total_dep = len(dep_block)
total_arr = len(arr_block)
ax1.text(0.01, 1.02, f"Date: {base_date.strftime('%Y-%m-%d')}", transform=ax1.transAxes, fontsize=11, ha="left", va="bottom")
ax1.text(0.99, 1.02, f"Total Departure: {total_dep}   Total Arrival: {total_arr}", transform=ax1.transAxes,
         fontsize=11, ha="right", va="bottom", color="black")

ax1.legend(loc="upper left")
ax1.set_yticks([]); ax1.tick_params(axis='y', which='both', left=False, labelleft=False)
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
for lbl in ax1.get_xticklabels(): lbl.set_rotation(0); lbl.set_ha('center')
ax1.set_title("Flight Handling Timeline")

# Inline overlap numbers (two rows, numbers only, blue over red, darker for higher values)
trans = transforms.blended_transform_factory(ax1.transData, ax1.transAxes)
max_d = max(dep_counts) if len(dep_counts)>0 else 1
max_a = max(arr_counts) if len(arr_counts)>0 else 1
# place at interval centers
for i in range(len(time_range)-1):
    t1 = time_range[i]; t2 = time_range[i+1]
    mid = t1 + (t2 - t1)/2
    d = dep_counts[i]; a = arr_counts[i]
    if d>0:
        alpha = 0.35 + 0.65*(d/max_d)
        ax1.text(mid, -0.045, str(d), transform=trans, ha="center", va="top",
                 fontsize=8, color=(0.84,0.15,0.16, alpha))  # red RGBA with alpha
    if a>0:
        alpha = 0.35 + 0.65*(a/max_a)
        ax1.text(mid, -0.095, str(a), transform=trans, ha="center", va="top",
                 fontsize=8, color=(0.12,0.46,0.70, alpha))  # blue RGBA with alpha

# Align x-limits and grid without gray bands
start_time = min(dep_df["start"].min(), arr_df["start"].min())
end_time = max(dep_df["end"].max(), arr_df["end"].max())
if 'extra_dep' in locals() and extra_dep is not None:
    start_time = min(start_time, extra_dep["start"].min())
    end_time = max(end_time, extra_dep["end"].max())
if 'extra_arr' in locals() and extra_arr is not None:
    start_time = min(start_time, extra_arr["start"].min())
    end_time = max(end_time, extra_arr["end"].max())

ax1.set_xlim(start_time, end_time)
ax1.grid(True, axis="x", linestyle="--", alpha=0.3)

# ----- Save / Download chart image -----
# filename: YYYY-MM-DD_Weekday_D{dep}_A{arr}.png
filename = f"{base_date.strftime('%Y-%m-%d')}_{base_date.strftime('%a')}_D{total_dep}_A{total_arr}.png"

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

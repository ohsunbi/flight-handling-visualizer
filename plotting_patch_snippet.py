
# ---- Top panel: classic split with new palette ----
fig1, ax1 = plt.subplots(figsize=(12, 8))

# departures block: base + extra (dotted)
dep_block = pd.concat([
    dep_df[["Label","start","end","marker","type","time_str"]],
    (extra_dep if extra_dep is not None else pd.DataFrame(columns=["Label","start","end","marker","type","time_str"]))
], ignore_index=True).sort_values("start").reset_index(drop=True)

for i, row in dep_block.iterrows():
    dotted = ("EXTRA" in row["type"])
    style = (0,(1,2)) if dotted else '-'   # tight dotted for extra
    ax1.plot([row["start"], row["end"]], [i, i],
             color=(DEP_EXTRA_COLOR if dotted else DEP_COLOR),
             linewidth=4, linestyle=style, alpha=0.95 if dotted else 1.0,
             label=None)
    if row["Label"]:
        ax1.text(row["end"] + timedelta(minutes=5), i, row["Label"], va="center",
                 fontsize=8, color=(DEP_EXTRA_COLOR if dotted else DEP_COLOR))
    ax1.plot(row["marker"], i, marker=('D' if dotted else 'o'),
             color=(DEP_EXTRA_COLOR if dotted else DEP_COLOR))
    ax1.text(row["marker"] + timedelta(minutes=3), i+0.15, row["time_str"],
             fontsize=7, color=(DEP_EXTRA_COLOR if dotted else DEP_COLOR))

# arrivals block: base + extra (dotted), plotted below departures with offset 0.4
arr_block = pd.concat([
    arr_df[["Label","start","end","marker","type","time_str"]],
    (extra_arr if extra_arr is not None else pd.DataFrame(columns=["Label","start","end","marker","type","time_str"]))
], ignore_index=True).sort_values("start").reset_index(drop=True)

for i, row in arr_block.iterrows():
    y = i + 0.4
    dotted = ("EXTRA" in row["type"])
    style = (0,(1,2)) if dotted else '-'
    ax1.plot([row["start"], row["end"]], [y, y],
             color=(ARR_EXTRA_COLOR if dotted else ARR_COLOR),
             linewidth=4, linestyle=style, alpha=0.95 if dotted else 1.0,
             label=None)
    if row["Label"]:
        ax1.text(row["end"] + timedelta(minutes=5), y, row["Label"], va="center",
                 fontsize=8, color=(ARR_EXTRA_COLOR if dotted else ARR_COLOR))
    ax1.plot(row["marker"], y, marker=('D' if dotted else 'o'),
             color=(ARR_EXTRA_COLOR if dotted else ARR_COLOR))
    ax1.text(row["marker"] + timedelta(minutes=3), y+0.15, row["time_str"],
             fontsize=7, color=(ARR_EXTRA_COLOR if dotted else ARR_COLOR))

# totals (including extra)
total_dep = len(dep_block)
total_arr = len(arr_block)
ax1.text(0.01, 1.02, f"Date: {base_date.strftime('%Y-%m-%d')} | Service start: {service_start_hour:02d}:00", transform=ax1.transAxes,
         fontsize=11, ha="left", va="bottom")
ax1.text(0.99, 1.02, f"Total Departure: {total_dep}   Total Arrival: {total_arr}", transform=ax1.transAxes,
         fontsize=11, ha="right", va="bottom", color="black")

# custom legend: 4 categories
legend_handles = [
    Line2D([], [], color=DEP_COLOR, linewidth=4, label='Departure'),
    Line2D([], [], color=ARR_COLOR, linewidth=4, label='Arrival'),
    Line2D([], [], color=DEP_EXTRA_COLOR, linewidth=4, linestyle=(0,(1,2)), marker='D', label='Departure (extra)'),
    Line2D([], [], color=ARR_EXTRA_COLOR, linewidth=4, linestyle=(0,(1,2)), marker='D', label='Arrival (extra)'),
]
ax1.legend(handles=legend_handles, loc='upper left')

ax1.set_yticks([]); ax1.tick_params(axis='y', which='both', left=False, labelleft=False)
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
for lbl in ax1.get_xticklabels(): lbl.set_rotation(0); lbl.set_ha('center')
ax1.set_title("Flight Handling Timeline")
ax1.grid(True, axis="x", linestyle="--", alpha=0.3)

# ---- Overlap counts (integrated below timeline) ----
def _to_intervals(df):
    return df[["start","end"]].copy()

dep_intervals = _to_intervals(dep_block)
arr_intervals = _to_intervals(arr_block)

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

# overlay two numeric rows at the bottom of ax1
ax1.set_xlim(start_time, end_time)
_ymax = max(len(dep_block), len(arr_block)) + 0.8
ax1.set_ylim(-1.2, _ymax)
_y_dep = -0.25  # top row
_y_arr = -0.65  # bottom row

for x, d, a in zip(time_range, dep_counts, arr_counts):
    if d>0:
        ax1.text(x, _y_dep, str(d), ha='center', va='center', fontsize=8,
                 color=DEP_COLOR, alpha=min(1.0, 0.25 + 0.15*int(d)))
    if a>0:
        ax1.text(x, _y_arr, str(a), ha='center', va='center', fontsize=8,
                 color=ARR_COLOR, alpha=min(1.0, 0.25 + 0.15*int(a)))

ax1.axhline(-0.05, color='k', linewidth=0.5, alpha=0.3)

# ---- Render ----
st.pyplot(fig1, use_container_width=True)

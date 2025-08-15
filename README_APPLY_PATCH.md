# How to apply the visual update

This package contains your original files plus a ready-to-paste plotting patch.

Files:
- app.py (original, unchanged)
- requirements.txt
- flights_sample.csv
- sample_extra_v64.csv
- plotting_patch_snippet.py  ← paste this into app.py to replace the plotting section
- flight_timeline_patch_bundle.zip (contains the same snippet + README)

## Steps
1) Open `plotting_patch_snippet.py` and copy all contents.
2) In `app.py`, find the plotting section starting from a comment like `# ---- Top panel: classic split ----`
3) Replace that whole block (down through the overlap/second chart and final `st.pyplot(...)` calls) with the snippet.
4) Save, commit, push to GitHub. Streamlit Cloud will rebuild and you'll see:
   - New color palette:
     * Departure: #1f77b4
     * Arrival: #d62728
     * Departure (extra): #17becf
     * Arrival (extra): #ff7f0e
   - Extra markers are diamonds (◆) on both dep/arr.
   - Legend shows 4 categories with correct styles.
   - Overlap counts appear as two numeric rows under the timeline
     (top row = Departure, bottom row = Arrival) with higher counts drawn darker.

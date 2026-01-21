import streamlit as st
import pandas as pd
import sys
import os
import re

# Ensure we can import the backend logic (now in same dir)
sys.path.append(os.path.dirname(__file__))
import optimizer
import importlib
importlib.reload(optimizer)
from optimizer import OptimizerService
from layout_packer import pack_rectangles, render_layout
import subprocess
from datetime import datetime

def get_last_updated_db():
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    if not os.path.exists(data_dir):
        return "Unknown"
    files = [f for f in os.listdir(data_dir) if f.startswith("MLCC_Murata_") and f.endswith(".csv")]
    if not files:
        return "Unknown"
    # Extract date from filename e.g., MLCC_Murata_20260120.csv
    dates = []
    for f in files:
        match = re.search(r'(\d{8})', f)
        if match:
            dates.append(match.group(1))
    if not dates:
        return "Unknown"
    latest_date = max(dates)
    try:
        return datetime.strptime(latest_date, "%Y%m%d").strftime("%b %d, %Y")
    except:
        return latest_date

def get_last_updated_webapp():
    try:
        cmd = ["git", "log", "-1", "--format=%cd", "--date=format:%Y%m%d"]
        result = subprocess.check_output(cmd, cwd=os.path.dirname(__file__), stderr=subprocess.STDOUT).decode().strip()
        return datetime.strptime(result, "%Y%m%d").strftime("%b %d, %Y")
    except:
        return "Jan 20, 2026" # Fallback to current if git fails

# Page Config
st.set_page_config(
    page_title="Cap Finder",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- LOAD LOGIC ---
@st.cache_resource
def get_optimizer_v27():
    # Adjusted path: up one level from src, then into data
    library_path = os.path.join(os.path.dirname(__file__), "..", "data", "Murata_Unified_Library.csv")
    return OptimizerService(library_path)

optimizer = get_optimizer_v27()

# --- CSS TWEAKS ---
st.markdown("""
<style>
    /* Professional Header */
    .title-text {
        font-size: 20px;
        font-weight: 600;
        color: #333;
        margin-top: -50px;
    }
    
    /* Global Font Tweak */
    .stApp {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }

    /* Button Styling - Blue */
    div.stButton > button:first-child {
        width: 100%;
        height: 3.5em;
        font-size: 18px;
        font-weight: 600;
        background-color: #4A90E2; 
        color: white;
        border-radius: 8px;
        border: none;
    }
    
    /* Sidebar Layout - Fixed Width & No Resize */
    section[data-testid="stSidebar"] {
        min-width: 500px !important;
        max-width: 600px !important;
        /* Force Opaque - No Dimming */
        opacity: 1 !important;
        filter: unset !important;
        transition: none !important;
        will-change: opacity, transform;
    }
    
    /* Global Anti-Dimming (Main Content) */
    div[data-testid="stAppViewContainer"], section[data-testid="stMain"] {
        opacity: 1 !important;
        filter: none !important;
        transition: none !important;
        will-change: opacity;
    }

    /* Target inner content specifically to ensure it stays solid */
    div[data-testid="stSidebarUserContent"] {
        opacity: 1 !important;
        filter: unset !important;
    }
    
    /* Prevent the 'disabled' cursor/pointer-events if user wants to spam click */
    /* Note:# Streamlit App
# Force reload: 2026-01-20
might drop events if processing, but this allows correct visual feedback */
    section[data-testid="stSidebar"] * {
        cursor: default !important; /* Optional: forces default cursor even if busy */
    }
    
    /* Hides the drag handle */
    div[data-testid="stSidebar"] > div:nth-child(2) {
        display: none !important;
    }
    
    /* Footer */
    .footer {
        position: fixed;
        right: 0;
        bottom: 0;
        width: 450px; 
        background-color: transparent;
        color: #888;
        text-align: center;
        padding: 10px;
        font-size: 12px;
        z-index: 1000;
        pointer-events: none;
    }
</style>
""", unsafe_allow_html=True)

# --- INITIALIZE SESSION STATE ---
DEFAULTS = {
    "input_dc_bias": 12.0,
    "input_min_rated": 15.0,
    "input_min_cap": 9.9,
    "input_max_cap": 10.1,
    "input_conn_type": "upto 2",
    "input_max_cnt": 10,
    "input_min_temp": 85,
    "input_freq": 100.0,
    "input_max_esr": 10.0
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- SIDEBAR ---
with st.sidebar:
    c_hdr, c_rst = st.columns([2, 1])
    with c_hdr:
        st.markdown("### Configuration")
    with c_rst:
        if st.button("Reset Defaults", type="secondary", use_container_width=True):
            # Apply defaults from the DEFAULTS dict
            for key, val in DEFAULTS.items():
                st.session_state[key] = val
            
            # Explicitly Select All Packages (Common + Extended)
            # We access the global 'optimizer' instance to get available packages
            all_pkgs = optimizer.get_available_packages()
            common_list = ['01005', '0201', '0402', '0603', '0805', '1206', '1210', '2220']
            
            # Divide into Common & Other
            c_av = [p for p in common_list if p in all_pkgs]
            o_av = [p for p in all_pkgs if p not in common_list]
            
            # Set Session State directly
            st.session_state['pkg_common'] = c_av
            st.session_state['pkg_other'] = o_av

            # Clear result and selection keys (removed pkg_common/pkg_other since we set them above)
            keys_to_del = [
                "last_run_constraints", 
                "last_df_disp", "found_any", "final_count", 
                "last_results", "layout_select"
            ]
            for k in keys_to_del:
                if k in st.session_state:
                    del st.session_state[k]
                    
            st.rerun()

    # 1. Voltage Ratings first (TDK Style)
    c_bias, c_rated = st.columns([1, 1])
    # Gap Maintenance Logic (Push Behavior)
    GAP = 0.1

    def on_bias_change():
        # Ensure Min Rated Voltage >= DC Bias
        new_bias = st.session_state.input_dc_bias
        current_rated = st.session_state.get('input_min_rated', new_bias)
        
        if current_rated < new_bias:
            st.session_state.input_min_rated = new_bias

    # 1. Voltage Ratings first (TDK Style)
    c_bias, c_rated = st.columns([1, 1])
    with c_bias:
        dc_bias = st.number_input(
            "DC Bias (V)", 
            step=0.5, 
            min_value=0.0, 
            format="%g",
            key="input_dc_bias",
            on_change=on_bias_change,
            help="The DC voltage applied across the capacitors in your circuit. Most ceramic capacitors lose significant capacitance as DC bias increases (Voltage Coefficient)."
        )
    with c_rated:
        min_rated_v = st.number_input(
            "Min Rated Voltage (V)", 
            min_value=0.0, 
            step=1.0, 
            format="%g",
            key="input_min_rated",
            help="The minimum DC Voltage Rating required for the selected parts. Standard practice is to choose a rating ~20-50% higher than your operating DC Bias."
        )
    
    # 2. Capacitance Range
    st.markdown("**Capacitance Range**")
    c_min_col, c_max_col, c_unit_col = st.columns([1, 1, 0.8])
    
    with c_unit_col:
        cap_unit = st.selectbox("Unit", ["µF", "nF", "pF", "mF"], index=0, label_visibility="visible")
        
    unit_mult = {
        "mF": 1e-3,
        "µF": 1e-6,
        "nF": 1e-9,
        "pF": 1e-12
    }
    multiplier = unit_mult[cap_unit]



    def on_min_change():
        c_min = st.session_state.input_min_cap
        c_max = st.session_state.input_max_cap
        # If min pushed up too close to max, push max up
        if c_max - c_min < GAP - 1e-9:
            new_max = round(c_min + GAP, 6)
            if st.session_state.input_max_cap != new_max:
                st.session_state.input_max_cap = new_max
        # Ensure min doesn't exceed reasonable bounds if needed (optional)

    def on_max_change():
        c_min = st.session_state.input_min_cap
        c_max = st.session_state.input_max_cap
        # If max pushed down too close to min, push min down
        if c_max - c_min < GAP - 1e-9:
            target_min = round(c_max - GAP, 6)
            if target_min < 0: 
                target_min = 0.0
                # If we hit 0 and still gap < 0.1, restrict max? 
                # For now, just set min to 0. 
                # If max is 0.05, min=0. Gap=0.05. Violates requirement?
                # User said "dont allow cmax-cmin to be smaller than 0.1"
                # If max < 0.1, we must set max = 0.1?
                st.session_state.input_max_cap = max(st.session_state.input_max_cap, 0.1)
            
            if st.session_state.input_min_cap != target_min:
                st.session_state.input_min_cap = target_min

    with c_min_col:
        c_min_input = st.number_input("Min Cap", 
                                      step=0.1, min_value=0.0, format="%g", key="input_min_cap", on_change=on_min_change,
                                      help="Minimum target effective capacitance (after DC bias derating).")
    with c_max_col:
        c_max_input = st.number_input("Max Cap", 
                                      step=0.1, min_value=0.0, format="%g", key="input_max_cap", on_change=on_max_change,
                                      help="Maximum target effective capacitance (after DC bias derating).")

    # Use the session state values directly (logic handled in callback)
    c_min_real = c_min_input
    c_max_real = c_max_input

    # Ensure Min < Max logic handled by optimizer or simple swap? 
    # Let's enforce min <= max for the backend
    if c_min_real > c_max_real:
        c_min_real, c_max_real = c_max_real, c_min_real

    c_min_F = c_min_real * multiplier
    c_max_F = c_max_real * multiplier


    st.divider()
    
    # Parallel configurations & Max Count (Side by Side)
    # Squeeze radios (col1) and put Max Count (col2)
    c_types, c_count = st.columns([1, 1])
    
    with c_types:
        st.markdown("**Pool Depth**")
        conn_map = {
            "1": 1,
            "upto 2": 2, 
            "upto 3": 3
        }
        conn_keys = list(conn_map.keys())
        conn_type_label = st.radio("Depth", conn_keys, 
                                   label_visibility="collapsed", horizontal=True, key="input_conn_type",
                                   help="1: Only single part numbers. upto 2: Combines up to two different part numbers. upto 3: Combines up to three different part numbers.")
        conn_type = conn_map[conn_type_label]
        
    with c_count:
        max_count = st.number_input("Max Count", 
                                    min_value=1, step=1, format="%d", key="input_max_cnt",
                                    help="Maximum total number of capacitors allowed in the parallel bank.")

    
    
    # Packages (Grouped but Visible)
    st.markdown("### Allowed Packages")
    all_pkgs = optimizer.get_available_packages()
    # User requested 1005 at top. Sorted list.
    # 1005 is 0402 metric? No, 1005 metric is 0402 imperial. 
    # Wait, in the library, what are these? 
    # Usually we have 0201, 0402, 0603...
    # If 1005 is strictly 1005 (metric), it might correspond to 0402.
    # But assuming the user sees "1005", we place it first.
    # User said "sorted so 1005 appears at top".
    # Assuming '1005', '0201', '0402', '0603', '0805', '1206', '1210', '2220'.
    common_list = ['01005', '0201', '0402', '0603', '0805', '1206', '1210', '2220']
    
    # Common (Blue)
    st.markdown(":blue[**Common Sizes**]")
    common_available = [p for p in common_list if p in all_pkgs]
    sel_common = st.multiselect(
        "Common", 
        common_available,
        # default=common_available, # REMOVED: Managed by session_state 'pkg_common'
        label_visibility="collapsed",
        key="pkg_common",
        help="EIA package sizes frequently used in PCB design (e.g., 0402, 0603)."
    )
    
    # Others (Pink/Red)
    st.markdown(":red[**Extended Sizes**]")
    other_list = [p for p in all_pkgs if p not in common_list]
    sel_other = st.multiselect(
        "Extended", 
        other_list,
        # default=other_list, # REMOVED: Managed by session_state 'pkg_other'
        label_visibility="collapsed",
        key="pkg_other",
        help="Larger or specialized package sizes (e.g., 1812, 2220)."
    )
    
    selected_pkgs = sorted(list(set(sel_common + sel_other)))
    
    # st.markdown("---")
    
    with st.expander("Advanced Settings"):
        min_temp = st.selectbox("Min Temperature (C)", [85, 105, 125], 
                                 key="input_min_temp",
                                 help="Filters capacitors by their Maximum Operating Temperature (e.g., X7R is 125C, X5R is 85C).")
        st.caption("ESR Optimization")
        freq_khz = st.number_input("Operating Freq (kHz)", 
                                   step=10.0, min_value=0.1, format="%g", key="input_freq",
                                   help="Target frequency for ESR and Self-Resonant Frequency (SRF) calculations. Optimization will prioritize low ESR at this frequency.")
        max_esr_mohm = st.number_input("Max System ESR (mΩ)", 
                                       step=0.1, min_value=0.1, format="%.2f", key="input_max_esr",
                                       help="Upper limit for the combined Equivalent Series Resistance of the entire parallel capacitor bank.")

    # --- SIDEBAR FOOTER (Removed from bottom) ---

# --- MAIN AREA ---
# Single Header with Emoji
st.markdown('<div class="title-text">  CapStack Optimizer 🧮</div>', unsafe_allow_html=True)
# st.caption("Optimal Ceramic Capacitor Bank Finder") # Removed as per request

# Summary Banner
# Summary Banner
st.info(f"**Range:** {c_min_real:g} to {c_max_real:g} {cap_unit} @ {dc_bias}V Bias  |  **Min Rated:** {min_rated_v}V")

# Check Stale State (Must construct constraints BEFORE button)
constraints = {}
if selected_pkgs:
    constraints = {
        'min_cap': c_min_F,
        'max_cap': c_max_F,
        'dc_bias': dc_bias,
        'max_count': max_count,
        'min_rated_volt': min_rated_v,
        'min_temp': min_temp,
        'conn_type': conn_type,
        'packages': selected_pkgs,
        'target_freq': freq_khz * 1000.0,
        'max_esr': max_esr_mohm / 1000.0
    }

if 'last_run_constraints' not in st.session_state:
    st.session_state.last_run_constraints = {}

# Simple comparison (dicts compare by value)
is_stale = (constraints != st.session_state.last_run_constraints)

# Dynamic CSS for Button
# Refined: Keep Blue (@4A90E2) but add Red Glow/Pulse when stale
if is_stale:
    # Pulse animation (Cyan/Ice Blue Glow - Visible on White)
    st.markdown("""
    <style>
    @keyframes pulse-cyan {
        0% { box-shadow: 0 0 0 0 rgba(0, 191, 255, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(0, 191, 255, 0); }
        100% { box-shadow: 0 0 0 0 rgba(0, 191, 255, 0); }
    }
    div.stButton > button:first-child {
        background-color: #4A90E2 !important;
        border: 2px solid #00BFFF !important; /* Deep Cyan Border */
        animation: pulse-cyan 2s infinite;
    }
    </style>
    """, unsafe_allow_html=True)
else:
    # Default Blue
    st.markdown("""
    <style>
    div.stButton > button:first-child {
        background-color: #4A90E2 !important;
        border: none;
        box-shadow: none;
    }
    </style>
    """, unsafe_allow_html=True)

# Callback to update state BEFORE the re-run logic allows the button to render blue immediately
def update_run_state():
    st.session_state.last_run_constraints = constraints.copy()

# Compute Button
c_run, c_clear = st.columns([4, 1])
with c_run:
    run_btn = st.button("RUN OPTIMIZATION", type="primary", use_container_width=True, on_click=update_run_state)

with c_clear:
    if st.button("Clear", type="secondary", use_container_width=True):
        keys_to_del = ["last_results", "last_df_disp", "found_any", "final_count", "layout_select"]
        for k in keys_to_del:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

# Progress
progress_container = st.empty()

# Helper to render the styled results table
def render_results_table(df_to_render, placeholder):
    if df_to_render is None or df_to_render.empty:
        return

    # Columns are assumed to be already named correctly in df_to_render
    
    # Style
    styler = df_to_render.style.background_gradient(
        subset=["Vol\n(mm³)"], 
        cmap="Blues"
    ).format(
        "{:.4f}", subset=["Vol\n(mm³)"]
    ).format(
        "{:.4f}", subset=["Area (flat)\n(mm²)"]
    ).format(
        "{:.3f}", subset=["Height (flat)\n(mm)"]
    ).format(
        "{:.2f}", subset=["Derated Cap\n(µF)"]
    ).format(
        "{:.4f}", subset=["ESR\n(mΩ)"]
    )

    # Col Config
    col_cfg = {
        "Rank": st.column_config.NumberColumn("Rank", width="small"),
        "Vol\n(mm³)": st.column_config.NumberColumn("Vol\n(mm³)", width="small"),
        "Area (flat)\n(mm²)": st.column_config.NumberColumn("Area (flat)\n(mm²)", width="small"),
        "Height (flat)\n(mm)": st.column_config.NumberColumn("Height (flat)\n(mm)", width="small"),
        "Derated Cap\n(µF)": st.column_config.NumberColumn("Derated Cap\n(µF)", width="small"),
        "ESR\n(mΩ)": st.column_config.NumberColumn("ESR\n(mΩ)", format="%.2f", width="small"),
        "Configuration": st.column_config.TextColumn("Configuration", width="medium"), 
    }
    
    for k in range(1, 4):
        col_cfg[f"Part {k}"] = st.column_config.TextColumn(f"Part {k}", width="medium")
        col_cfg[f"Buy {k}"] = st.column_config.LinkColumn(
            f"Buy {k}", 
            display_text="DigiKey ↗", 
            width="small"
        )
    
    col_cfg["Alt Parts"] = st.column_config.TextColumn("Alt Parts", width="medium", help="Electrically identical alternative configurations found. The primary part number is shown in the columns to the left.")

    placeholder.dataframe(
        styler,
        column_config=col_cfg,
        hide_index=True,
        width="stretch",
        height=600
    )

# Table placeholder
table_placeholder = st.empty()

if run_btn:
    if not selected_pkgs:
        st.error("Select at least one package.")
    else:
        gen = optimizer.solve_generator(constraints)
        
        final_count = 0
        found_any = False
        
        try:
            for val in gen:
                # Defensive unpacking: Handle both legacy (2) and new (3) tuple formats
                if len(val) == 3:
                    prog, partial_sols, status = val
                elif len(val) == 2:
                    prog, partial_sols = val
                    status = f"Processing... ({prog}%)"
                else:
                    continue # Skip invalid usage

                progress_container.progress(prog, text=status)
                
                if partial_sols:
                    if 'error' in partial_sols[0]:
                        st.error(f"Solver Error: {partial_sols[0]['error']}")
                        break

                    found_any = True
                    df_raw = pd.DataFrame(partial_sols)
                    df_raw = df_raw.sort_values(by='Vol').head(50)
                    
                    # Store raw solutions for layout visualization
                    st.session_state.last_results = df_raw.to_dict('records')
                    
                    rows = []
                    for i, r in enumerate(df_raw.to_dict('records')):
                        row = {
                            'Rank': i + 1,
                            'Vol': r['Vol'], 
                            'Area': r.get('Area', 0),
                            'Height': r.get('Height', 0),
                            'Capacitance': r['Cap'] * 1e6,
                            'ESR': r.get('ESR', 0) * 1000.0,
                            'Configuration': r['BOM'] # User requested "3x 0603 + ..." which is 'BOM'
                        }
                        
                        # Columns for individual caps
                        parts = r.get('Parts', [])
                        for idx, p in enumerate(parts):
                            if idx >= 3: break
                            p_name = p['part']
                            cnt = p['count']
                            url = f"https://www.digikey.com/en/products/result?keywords={p_name}"
                            
                            row[f"P{idx+1}"] = f"{cnt}x {p_name}"
                            row[f"L{idx+1}"] = url
                        
                        if 'Alts' in r and r['Alts']:
                            alts_str = " | ".join(r['Alts'])
                            row['Alts'] = f"{len(r['Alts'])} options: {alts_str}"
                        else:
                            row['Alts'] = "None"
                        
                        rows.append(row)
                    
                    df_disp = pd.DataFrame(rows)
                    final_count = len(df_disp)
                    
                    # Fill missing
                    for k in range(1, 4):
                        if f"P{k}" not in df_disp.columns:
                            df_disp[f"P{k}"] = ""
                            df_disp[f"L{k}"] = None
                    
                    # Prepare for display
                    ordered_cols = ['Rank', 'Capacitance', 'Vol', 'Area', 'Height', 'ESR', 'Configuration', 'P1', 'L1', 'P2', 'L2', 'P3', 'L3', 'Alts']
                    df_disp = df_disp[ordered_cols]
                    
                    new_columns = [
                        "Rank", "Derated Cap\n(µF)", "Vol\n(mm³)", "Area (flat)\n(mm²)", 
                        "Height (flat)\n(mm)", "ESR\n(mΩ)", "Configuration",
                        "Part 1", "Buy 1", "Part 2", "Buy 2", "Part 3", "Buy 3",
                        "Alt Parts"
                    ]
                    df_disp.columns = new_columns

                    # Store for persistence
                    st.session_state.last_df_disp = df_disp
                    st.session_state.found_any = True
                    st.session_state.final_count = final_count

                    # Render
                    render_results_table(df_disp, table_placeholder)
        except Exception as e:
            st.error(f"Search Execution Failed: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

        progress_container.empty()

# --- PERSISTENT TABLE RENDERING ---
# This ensures the table stays visible during reruns (like when interacting with the layout preview)
if not run_btn and 'last_df_disp' in st.session_state:
    render_results_table(st.session_state.last_df_disp, table_placeholder)

# Display persistence-based warnings
f_any = st.session_state.get('found_any', False)
f_count = st.session_state.get('final_count', 0)

if not run_btn: # Only show these if not currently running a search
    if 'last_df_disp' in st.session_state and not f_any:
        st.error("No capacitors found matching your criteria. Try increasing Max ESR, lowering Frequency, or checking your constraints.")
    elif 'last_df_disp' in st.session_state and f_count < 25:
        st.warning(f"Fewer than 25 results found ({f_count}). Consider increasing the maximum capacitor count, total capacitor tolerance range, or available package options.")

# --- LAYOUT VISUALIZATION ---
if 'last_results' in st.session_state and st.session_state.last_results:
    st.markdown("---")
    st.subheader("📐 Layout Preview")
    
    results_for_layout = st.session_state.last_results
    options = [f"Rank {i+1}: {r['BOM']}" for i, r in enumerate(results_for_layout[:25])]
    
    selected = st.selectbox("Select a configuration to preview layout:", options, index=0, key="layout_select")
    
    if selected:
        idx = int(selected.split(":")[0].replace("Rank ", "")) - 1
        sol = results_for_layout[idx]
        
        # Build parts list for packer
        parts_for_pack = []
        for p in sol.get('Parts', []):
            # Get real dimensions from the part data
            part_L = p.get('L', 0)
            part_W = p.get('W', 0)
            
            # If dimensions are 0 or missing, we may have a data issue or stale search.
            # We'll use the package code as a fallback if dimensions are 0.
            # 0402 -> 1.0 x 0.5, 0603 -> 1.6 x 0.8 etc.
            if part_L <= 0 or part_W <= 0:
                pkg = str(sol.get('BOM', '')).split('x ')[1].split(' +')[0] if 'x ' in str(sol.get('BOM', '')) else ""
                # Simple fallback map for common packages if data is missing
                pkg_map = {'01005': (0.4, 0.2), '0201': (0.6, 0.3), '0402': (1.0, 0.5), '0603': (1.6, 0.8), '0805': (2.0, 1.25), '1206': (3.2, 1.6), '1210': (3.2, 2.5)}
                fallback = pkg_map.get(pkg, (1.0, 0.5))
                if part_L <= 0: part_L = fallback[0]
                if part_W <= 0: part_W = fallback[1]
                
            parts_for_pack.append({
                'label': p['part'],
                'width': part_W,
                'height': part_L,  # L is length
                'count': p['count'],
                'orig_L': p.get('L', part_L),
                'orig_W': p.get('W', part_W),
                'orig_H': p.get('H', sol.get('Height', 0)) # Try part height first, then system height
            })
        
        if parts_for_pack:
            placed = pack_rectangles(parts_for_pack)
            if placed:
                img_buf = render_layout(placed, title=f"Layout: {sol['BOM']}")
                if img_buf:
                    st.image(img_buf, caption=f"Top-down layout for {sol['BOM']}")
            else:
                st.info("No rectangles to pack.")
        else:
            st.info("No parts data available for layout preview.")

    # --- FOOTER ---
    st.markdown("---")
    db_date = get_last_updated_db()
    web_date = get_last_updated_webapp()
    st.markdown(f"""
    <div style="font-size: 11px; color: #888; text-align: center; padding-top: 10px;">
        <div style="margin-bottom: 5px; font-weight: 600;">Made with μεράκι by Nagesh Patle</div>
        <div><b>Last Updated (Murata Database):</b> {db_date}</div>
        <div><b>Last Updated (Website):</b> {web_date}</div>
    </div>
    """, unsafe_allow_html=True)

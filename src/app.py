import streamlit as st
import pandas as pd
import sys
import os

# Ensure we can import the backend logic (now in same dir)
sys.path.append(os.path.dirname(__file__))
from optimizer import OptimizerService

# Page Config
st.set_page_config(
    page_title="Cap Finder",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- LOAD LOGIC ---
@st.cache_resource
def get_optimizer_v3():
    # Adjusted path: up one level from src, then into data
    library_path = os.path.join(os.path.dirname(__file__), "..", "data", "Murata_Unified_Library.csv")
    return OptimizerService(library_path)

optimizer = get_optimizer_v3()

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
        min-width: 400px !important;
        max-width: 600px !important;
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

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### Configuration")

    # 1. Target Cap & Tolerance
    c1, c2 = st.columns([1, 1])
    with c1:
        target_cap_uF = st.number_input("Target Cap (uF)", value=10.0, step=1.0, format="%g")
    with c2:
        tolerance = st.number_input("Tol (%)", value=1.0, step=0.5, format="%g")
        # Dynamic Range Caption
        if target_cap_uF > 0:
            tol_dec = tolerance / 100.0
            min_c = target_cap_uF * (1 - tol_dec)
            max_c = target_cap_uF * (1 + tol_dec)
            st.caption(f"Range= {min_c:g} - {max_c:g} µF")

    # 2. Voltage Ratings
    c3, c4 = st.columns([1, 1])
    with c3:
        dc_bias = st.number_input("DC Bias (V)", value=12.0, step=0.5, format="%g")
    with c4:
        min_rated_v = st.number_input(
            "Min Rated Voltage (V)", 
            value=float(dc_bias), 
            min_value=float(dc_bias), 
            step=1.0, 
            format="%g"
        )
    
    if dc_bias > 0:
        overrate_pct = ((min_rated_v - dc_bias) / dc_bias) * 100
        if overrate_pct > 0:
            st.caption(f"⚡ Overrated by {overrate_pct:.0f}%")
        else:
            st.caption("⚡ Rated = Bias (0%)")

    st.divider()
    
    # Cap Types & Max Count (Side by Side)
    # Squeeze radios (col1) and put Max Count (col2)
    c_types, c_count = st.columns([1, 1])
    
    with c_types:
        st.markdown("**Cap Types**")
        conn_map = {
            "1": 1,
            "upto 2": 2, 
            "upto 3": 3
        }
        conn_keys = list(conn_map.keys())
        conn_type_label = st.radio("Depth", conn_keys, index=1, label_visibility="collapsed", horizontal=True)
        conn_type = conn_map[conn_type_label]
        
    with c_count:
        max_count = st.number_input("Max Count", value=10, min_value=1, step=1, format="%d")

    
    
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
    common_list = ['1005', '0201', '0402', '0603', '0805', '1206', '1210', '2220']
    
    # Common (Blue)
    st.markdown(":blue[**Common Sizes**]")
    common_available = [p for p in common_list if p in all_pkgs]
    sel_common = st.multiselect(
        "Common", 
        common_available,
        default=common_available, # Select All
        label_visibility="collapsed",
        key="pkg_common"
    )
    
    # Others (Pink/Red)
    st.markdown(":red[**Extended Sizes**]")
    other_list = [p for p in all_pkgs if p not in common_list]
    sel_other = st.multiselect(
        "Extended", 
        other_list,
        default=other_list, # Select All by default
        label_visibility="collapsed",
        key="pkg_other"
    )
    
    selected_pkgs = list(set(sel_common + sel_other))
    
    # st.markdown("---")
    
    with st.expander("Advanced Settings"):
        min_temp = st.selectbox("Min Temperature (C)", [85, 105, 125], index=0)

    st.markdown('<div class="footer">Made with Meraki by Nagesh Patle</div>', unsafe_allow_html=True)

# --- MAIN AREA ---
# Single Header with Emoji
st.markdown('<div class="title-text">Optimal Ceramic Capacitor Bank Finder 🧮</div>', unsafe_allow_html=True)
# st.caption("Optimal Ceramic Capacitor Bank Finder") # Removed as per request

# Summary Banner
st.info(f"**Target:** {target_cap_uF} µF ±{tolerance}% @ {dc_bias}V Bias  |  **Min Rated:** {min_rated_v}V")

# Compute Button
run_btn = st.button("RUN OPTIMIZATION", type="primary")

# Progress
progress_container = st.empty()

# Table
table_placeholder = st.empty()

if run_btn:
    if not selected_pkgs:
        st.error("Select at least one package.")
    else:
        # Constraints
        constraints = {
            'target_cap': target_cap_uF,
            'tolerance': tolerance,
            'dc_bias': dc_bias,
            'max_count': max_count,
            'min_rated_volt': min_rated_v,
            'min_temp': min_temp,
            'conn_type': conn_type,
            'packages': selected_pkgs
        }
        
        gen = optimizer.solve_generator(constraints)
        
        for prog, partial_sols in gen:
            progress_container.progress(prog, text=f"Searching... {prog}%")
            
            if partial_sols:
                df_raw = pd.DataFrame(partial_sols)
                df_raw = df_raw.sort_values(by='Vol').head(50)
                
                rows = []
                for i, r in enumerate(df_raw.to_dict('records')):
                    row = {
                        'Rank': i + 1,
                        'Vol': r['Vol'], 
                        'Capacitance': r['Cap'] * 1e6,
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
                    
                    rows.append(row)
                
                df_disp = pd.DataFrame(rows)
                
                # Fill missing
                for k in range(1, 4):
                    if f"P{k}" not in df_disp.columns:
                        df_disp[f"P{k}"] = ""
                        df_disp[f"L{k}"] = None
                
                # Style
                styler = df_disp.style.background_gradient(
                    subset=['Vol'], 
                    cmap="Blues"
                ).format(
                    "{:.4f}", subset=["Vol"]
                ).format(
                    "{:.2f}", subset=["Capacitance"]
                )

                # Col Config
                col_cfg = {
                    "Rank": st.column_config.NumberColumn("Rank", width="small"),
                    "Vol": st.column_config.NumberColumn("Vol (mm³)", width="small"),
                    "Capacitance": st.column_config.NumberColumn("Derated Cap (µF)", width="small"),
                    "Configuration": st.column_config.TextColumn("Configuration", width="medium"), 
                }
                
                for k in range(1, 4):
                    col_cfg[f"P{k}"] = st.column_config.TextColumn(f"Part {k}", width="medium")
                    col_cfg[f"L{k}"] = st.column_config.LinkColumn(
                        f"Buy {k}", 
                        display_text="DigiKey ↗", 
                        width="small"
                    )

                # Render
                table_placeholder.dataframe(
                    styler,
                    column_order=['Rank', 'Vol', 'Capacitance', 'Configuration', 'P1', 'L1', 'P2', 'L2', 'P3', 'L3'],
                    column_config=col_cfg,
                    hide_index=True,
                    width="stretch",
                    height=600
                )
        
        progress_container.empty()

import streamlit as st
import pandas as pd
import sys
import os

# Ensure we can import the backend logic
backend_path = os.path.join(os.path.dirname(__file__), "web_version", "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
from optimizer import OptimizerService

# Page Config
st.set_page_config(
    page_title="Murata Capacitor Architect",
    page_icon="⚡",
    layout="wide"
)

# --- LOAD LOGIC ---
@st.cache_resource
def get_optimizer():
    library_path = "Murata_Unified_Library.csv"
    return OptimizerService(library_path)

optimizer = get_optimizer()

# --- CSS TWEAKS (Optional "Dark/Sci-Fi" hint) ---
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        background-color: #00ffaa;
        color: black;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR INPUTS ---
st.sidebar.title("Configuration")

target_cap_uF = st.sidebar.number_input("Target Cap (uF)", value=100.0)
tolerance = st.sidebar.number_input("Tolerance (+/- %)", value=1.0)
dc_bias = st.sidebar.number_input("DC Bias (V)", value=5.0)
max_count = st.sidebar.number_input("Max Total Count", value=40, min_value=1)
min_rated = st.sidebar.number_input("Min Rated Voltage (V)", value=10.0)
min_temp = st.sidebar.selectbox("Min Temperature (C)", [85, 105, 125], index=0)

conn_map = {"1p (Single)": 1, "2p (Dual Parallel)": 2, "3p (Triple Parallel)": 3}
conn_type_label = st.sidebar.radio("Connection Type", list(conn_map.keys()), index=1)
conn_type = conn_map[conn_type_label]

st.sidebar.markdown("---")
st.sidebar.subheader("Allowed Packages")

all_pkgs = optimizer.get_available_packages()
selected_pkgs = st.sidebar.multiselect(
    "Select Packages", 
    all_pkgs, 
    default=all_pkgs # Select all by default
)

run_btn = st.sidebar.button("OPTIMIZE BANK")

# --- MAIN CONTENT ---
st.title("⚡ Capacitor Bank Architect")
st.markdown(f"**Target**: `{target_cap_uF} uF` @ `{dc_bias} V` Bias")

if run_btn:
    if not selected_pkgs:
        st.error("Please select at least one package type.")
    else:
        with st.spinner("Calculating optimal configurations..."):
            # Prepare constraints
            constraints = {
                'target_cap': target_cap_uF,
                'tolerance': tolerance,
                'dc_bias': dc_bias,
                'max_count': max_count,
                'min_rated_volt': min_rated,
                'min_temp': min_temp,
                'conn_type': conn_type,
                'packages': selected_pkgs
            }
            
            # Run Solver
            results = optimizer.solve(constraints)
            
            if not results:
                st.warning("No valid solutions found within constraints. Try widening tolerance or allowing more packages.")
            elif isinstance(results[0], dict) and 'error' in results[0]:
                st.error(results[0]['error'])
            else:
                st.success(f"Found {len(results)} solutions!")
                
                # Convert to DF for display
                df_res = pd.DataFrame(results)
                
                # Reorder columns for readability
                display_cols = ['Rank', 'Type', 'Vol', 'Cap', 'Cfg']
                
                # Add Rank
                df_res['Rank'] = range(1, len(df_res) + 1)
                
                # Format for display
                df_display = df_res.copy()
                df_display['Vol'] = df_display['Vol'].apply(lambda x: f"{x:.4f} mm³")
                df_display['Cap'] = df_display['Cap'].apply(lambda x: f"{x*1e6:.2f} uF")
                
                st.dataframe(
                    df_display[['Rank', 'Type', 'Vol', 'Cap', 'Cfg']],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Best Result Highlight
                best = df_res.iloc[0]
                st.info(f"**Winner**: {best['Cfg']} ({best['Vol']:.4f} mm³)")

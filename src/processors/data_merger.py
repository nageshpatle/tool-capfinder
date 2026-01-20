import pandas as pd
import numpy as np
import os
import re

# --- CONFIGURATION ---
# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")

METADATA_FILE = os.path.join(DATA_DIR, "MurataProdList-MLCCs_InProduction.csv")
DATA_FILE = os.path.join(DATA_DIR, "Murata_SideBySide_Master.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "Murata_Unified_Library.csv")

# --- HELPER: PACKAGE NORMALIZER ---
# Maps your specific list to Standard EIA/Murata Codes
PACKAGE_MAP = {
    # Tiny
    "8004": "008004",
    "102":  "01005",  # Shorthand for 01005
    "15008": "015008", # Murata GRMMDX Series (0.5 x 0.25mm)

    # Standard Imperial
    "201":  "0201",
    "402":  "0402",
    "603":  "0603",
    "805":  "0805",
    "1005": "0402", # Metric 1005 = Imperial 0402
    
    # Reverse Geometry / Arrays
    "204":  "0204",
    "704":  "0704",
    "2404": "2404", # Keep as is (likely 2.4x0.4 or similar specialized)
    
    # Large / Metal Terminal
    "2211": "2211"
}

# --- HELPER: NOMINAL AREA LOOKUP (mm^2) ---
# L x W
PACKAGE_AREAS = {
    # Tiny
    "008004": (0.25, 0.125),
    "015008": (0.50, 0.25), # GRMMDX
    "01005":  (0.40, 0.20),

    # Standard
    "0201":   (0.60, 0.30),
    "0402":   (1.00, 0.50),
    "0603":   (1.60, 0.80),
    "0805":   (2.00, 1.25),
    "1206":   (3.20, 1.60),
    "1210":   (3.20, 2.50),
    "1808":   (4.50, 2.00),
    "1812":   (4.50, 3.20),
    "2220":   (5.70, 5.00),

    # Specialized / RF / Metal Terminal
    "1111":   (2.80, 2.80), # GQM22
    "2211":   (5.70, 2.80), # KRM/GA3
    "0204":   (0.50, 1.00), # Reverse 0402
    "0704":   (1.80, 1.00), # NFM Array
    "2404":   (2.40, 0.40), # Estimate based on code structure (or NFM array)
    
    # Fallback for metric-named packages
    "1608":   (1.60, 0.80),
    "2012":   (2.00, 1.25),
    "3216":   (3.20, 1.60),
    "3225":   (3.20, 2.50)
}

def get_volume_data(size_str, max_thickness_mm):
    """
    Volume = Nominal_Area (from Lookup) * Max_Thickness (from Sheet)
    """
    try:
        parts = str(size_str).split('/')
        
        # 1. Get & Normalize Package Code
        if len(parts) > 1:
            raw_code = parts[1].strip()
            pkg_code = PACKAGE_MAP.get(raw_code, raw_code)
            
            # Ensure leading zeros for standard codes if missing
            if pkg_code in ["201", "402", "603", "805"]:
                pkg_code = "0" + pkg_code
        else:
            pkg_code = "Unknown"

        # 2. Get Nominal Area (L x W)
        if pkg_code in PACKAGE_AREAS:
            l, w = PACKAGE_AREAS[pkg_code]
        else:
            # Fallback: Parse Metric Code (e.g. "5750M")
            metric_str = parts[0].strip().upper().replace('M', '')
            if len(metric_str) >= 4:
                l = float(metric_str[:2]) / 10.0
                w = float(metric_str[2:4]) / 10.0
            else:
                l, w = 0.0, 0.0
        
        area_mm2 = l * w

        # 3. Get Height (ALWAYS use Sheet Max Thickness)
        try:
            t_mm = float(max_thickness_mm)
        except:
            t_mm = 0.0
            
        vol_mm3 = area_mm2 * t_mm
        
        return pkg_code, vol_mm3
        
    except:
        return "Unknown", 0.0

def clean_tolerance(val):
    if pd.isna(val): return ""
    return re.sub(r'[^\d.]', '', str(val))

def main():
    print("--- MURATA LIBRARY MERGER (HYBRID DIMENSIONS) ---")
    
    # 1. LOAD METADATA
    print(f"Loading Metadata: {METADATA_FILE}")
    try:
        with open(METADATA_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            meta_df = pd.read_csv(f, on_bad_lines='skip', low_memory=False)
    except Exception as e:
        print(f"Error loading metadata: {e}")
        return

    meta_df.columns = [c.strip() for c in meta_df.columns]
    meta_dict = meta_df.set_index('part_number').to_dict('index')

    # 2. LOAD DATA
    print(f"Loading Curves: {DATA_FILE}")
    if not os.path.exists(DATA_FILE):
        print("Data file missing!")
        return

    try:
        df_data = pd.read_csv(DATA_FILE)
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    data_cols = [c for c in df_data.columns if c.endswith("_V")]
    parts_with_data = [c.replace("_V", "") for c in data_cols]
    print(f"Found {len(parts_with_data)} parts with curves.")

    # 3. BUILD LIBRARY
    rows = []
    
    for i, part in enumerate(parts_with_data):
        if part not in meta_dict: continue
        
        specs = meta_dict[part]
        
        # --- Dimensions ---
        size_code = str(specs.get('LWSize_mm_inch', ''))
        raw_thickness = specs.get('size_thickness_max', 0)
        
        package_imp, vol_mm3 = get_volume_data(size_code, raw_thickness)
        
        # --- Specs ---
        try: r_vol = float(specs.get('rvol', 0))
        except: r_vol = 0.0
        
        try:
            cap_pf = float(specs.get('capacitance_sort[pF]', 0))
            cap_nom_f = cap_pf * 1e-12
        except:
            cap_nom_f = 0.0
        
        temp_char = specs.get('tcc', '-')
        max_temp = specs.get('opetemp-max', '-')
        tol_clean = clean_tolerance(specs.get('tolerance', '-'))
        
        # --- Curves ---
        col_v, col_c = f"{part}_V", f"{part}_C"
        subset = df_data[[col_v, col_c]].dropna()
        if subset.empty: continue
        
        v_arr = subset[col_v].values
        c_arr = subset[col_c].values
        
        # --- Formatting ---
        c_str = "[" + " ".join([f"{x:.6e}" for x in c_arr]) + "]"
        v_str = "[" + " ".join([f"{x:.6g}" for x in v_arr]) + "]"
        
        row = {
            "Manufacturer": "Murata",
            "MfrPartName": part,
            "TChar": temp_char,
            "MaxTemp": max_temp,
            "Tolerance": tol_clean,
            "MaxThickness_mm": raw_thickness,
            "Capacitance": f"{cap_nom_f:.6e}",
            "VoltageRatedDC": f"{r_vol:.6g}",
            "Volume_mm3": f"{vol_mm3:.10g}", 
            "Package": package_imp,
            "C_Cv": c_str,
            "V_Cv": v_str
        }
        rows.append(row)
        
        if i % 2000 == 0: print(f"\rMerging: {i}/{len(parts_with_data)}", end="")

    # 4. EXPORT
    print("\nWriting final CSV...")
    df_out = pd.DataFrame(rows)
    
    # Sort
    df_out.sort_values(by=['Package', 'VoltageRatedDC', 'Capacitance'], 
                       ascending=[True, True, False], inplace=True)
    
    # Final Columns
    cols = ['Manufacturer', 'MfrPartName', 'TChar', 'MaxTemp', 'Tolerance', 'MaxThickness_mm',
            'Capacitance', 'VoltageRatedDC', 'Volume_mm3', 'Package', 'C_Cv', 'V_Cv']
            
    df_out = df_out[cols] 
    df_out.to_csv(OUTPUT_FILE, index=False)
    
    print(f"DONE! Library generated: {OUTPUT_FILE}")
    print(f"Total Parts Merged: {len(df_out)}")

if __name__ == "__main__":
    main()
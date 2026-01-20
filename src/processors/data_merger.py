import pandas as pd
import numpy as np
import os
import re

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")

# INPUTS
_candidates = [f for f in os.listdir(DATA_DIR) if f.startswith("MLCC_Murata_") and f.endswith(".csv")]
METADATA_FILE = os.path.join(DATA_DIR, max(_candidates)) if _candidates else None
DC_BIAS_FILE = os.path.join(DATA_DIR, "Murata_Cap_DC_Bias_Characteristics.csv")
ESR_FILE = os.path.join(DATA_DIR, "Murata_ESR_Frequency_Characteristics.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "Murata_Unified_Library.csv")

def clean_tolerance(val):
    if pd.isna(val): return ""
    return re.sub(r'[^\d.]', '', str(val))

def clean_float(val):
    try:
        return float(val)
    except:
        return 0.0

def main():
    print("--- MURATA UNIFIED MERGER ---")
    
    # 1. LOAD METADATA
    print(f"Loading Metadata: {METADATA_FILE}")
    try:
        # Load specific columns to save memory if needed, but for 7MB it's fine
        with open(METADATA_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            meta_df = pd.read_csv(f, on_bad_lines='skip', low_memory=False)
    except Exception as e:
        print(f"Error loading metadata: {e}")
        return

    meta_df.columns = [c.strip() for c in meta_df.columns]
    # Create index for fast lookup
    meta_dict = meta_df.set_index('part_number').to_dict('index')
    
    # 2. LOAD DATA
    print(f"Loading DC Bias: {DC_BIAS_FILE}")
    dc_available = False
    if os.path.exists(DC_BIAS_FILE):
        df_dc = pd.read_csv(DC_BIAS_FILE)
        dc_cols = set(df_dc.columns)
        dc_available = True
        print(f"  -> Loaded {len(df_dc)} rows (DC Bias)")
    else:
        print("  -> DC Bias file not found.")

    print(f"Loading ESR: {ESR_FILE}")
    esr_available = False
    if os.path.exists(ESR_FILE):
        df_esr = pd.read_csv(ESR_FILE)
        esr_cols = set(df_esr.columns)
        esr_available = True
        print(f"  -> Loaded {len(df_esr)} rows (ESR)")
    else:
        print("  -> ESR file not found.")

    # Identify Candidates (Parts usually come from the data files)
    # We want parts that have AT LEAST one type of data
    candidates = set()
    if dc_available:
        candidates.update([c.replace("_V", "") for c in dc_cols if c.endswith("_V")])
    if esr_available:
        candidates.update([c.replace("_Freq", "") for c in esr_cols if c.endswith("_Freq")])
        
    print(f"Found {len(candidates)} unique parts with data availability.")

    # 3. BUILD LIBRARY
    rows = []
    
    print("Merging data...")
    count = 0
    for part in candidates:
        if part not in meta_dict: continue
        
        specs = meta_dict[part]
        
        # --- Dimensions (Explicit) ---
        l_mm = clean_float(specs.get('l_size_value', 0))
        w_mm = clean_float(specs.get('w_size_value', 0))
        t_mm = clean_float(specs.get('size_thickness_max', 0))
        
        vol_mm3 = l_mm * w_mm * t_mm

        # --- Package Code ---
        size_str = str(specs.get('LWSize_mm_inch', ''))
        if '/' in size_str:
            package_code = size_str.split('/')[-1].strip()
        else:
            package_code = size_str # Fallback
            
        # FIX: Pad standard EIA codes if they lost leading zero(s)
        # Dictionary handles specific mappings (e.g. 8004 -> 008004)
        PAD_MAP = {
            "201": "0201", "402": "0402", "603": "0603", "805": "0805",
            "704": "0704", "2404": "02404", "204": "0204", "1005": "01005",
            "15008": "015008", "8004": "008004", "102": "0102"
        }
        if package_code in PAD_MAP:
            package_code = PAD_MAP[package_code]
        
        # --- Specs ---
        r_vol = clean_float(specs.get('rvol', 0))
        
        # Capacitance
        # Try numeric first, else parse string? 
        # Usually metadata has capacitance_sort or similar.
        # User's previous script used 'capacitance_sort[pF]' or similar.
        # Let's check keys from Step 17 output: 'capacitance_p' seems likely or 'capacitance_sort'
        # Step 17 output had: capacitance_pu,capacitance_p,capacitance_u,capacitance_sort
        # Let's use capacitance_sort (likely in pF based on value magnitude in previous scripts)
        # or capacitance_p (pF).
        cap_val = clean_float(specs.get('capacitance_sort', 0)) 
        # If it's effectively 0, try capacitance_p
        tile_cap = clean_float(specs.get('capacitance_p', 0))
        if cap_val == 0: cap_val = tile_cap
            
        # Convert to Farads (assuming pF input if > 1e-6, but wait... 
        # 1uF = 1e6 pF. 
        # If value is like 330000000, it's definitely pF. 
        cap_f = cap_val * 1e-12
        
        temp_char = specs.get('tcc', '-')
        max_temp = specs.get('opetemp-max', '-')
        tol_clean = clean_tolerance(specs.get('tolerance', '-'))
        srf_val = clean_float(specs.get('SRF', 0))
        
        # --- DC Bias Data ---
        v_str, c_str = "[]", "[]"
        if dc_available:
            col_v, col_c = f"{part}_V", f"{part}_C"
            if col_v in dc_cols and col_c in dc_cols:
                # Extract non-na
                subset = df_dc[[col_v, col_c]].dropna()
                if not subset.empty:
                    # Sort just in case
                    subset = subset.sort_values(col_v)
                    v_arr = subset[col_v].values
                    c_arr = subset[col_c].values
                    # Format
                    v_str = "[" + " ".join([f"{x:.3g}" for x in v_arr]) + "]"
                    c_str = "[" + " ".join([f"{x:.3e}" for x in c_arr]) + "]"


        # --- ESR Data ---
        freq_str, esr_str = "[]", "[]"
        if esr_available:
            col_f, col_e = f"{part}_Freq", f"{part}_ESR"
            if col_f in esr_cols and col_e in esr_cols:
                subset_e = df_esr[[col_f, col_e]].dropna()
                if not subset_e.empty:
                    subset_e = subset_e.sort_values(col_f)
                    f_arr = subset_e[col_f].values
                    e_arr = subset_e[col_e].values
                    
                    # --- SRF-Aware Decimation ---
                    # Goal: Keep full fidelity near SRF (+/- 2 decades), flatten elsewhere
                    srf_hz = srf_val * 1e6
                    f_new, e_new = [], []
                    
                    for i, (freq, esr) in enumerate(zip(f_arr, e_arr)):
                        keep = False
                        
                        # 1. Check if inside High-Fidelity Window
                        if srf_hz > 0:
                            # TIGHTER: 0.5 Decades = /3 to *3 (approx)
                            if (srf_hz / 10.0) <= freq <= (srf_hz * 3.0):
                                keep = True
                        
                        # 2. Decimate Outside Window (or if no SRF)
                        if not keep:
                            if i % 10 == 0: # Keep every 10th
                                keep = True
                                
                        if keep:
                            f_new.append(freq)
                            e_new.append(esr)
                            
                    f_arr = f_new
                    e_arr = e_new

                    # Format - REDUCED PRECISION TO 3 SIG FIGS
                    freq_str = "[" + " ".join([f"{x:.3g}" for x in f_arr]) + "]"
                    esr_str = "[" + " ".join([f"{x:.3g}" for x in e_arr]) + "]"

        # Construct Row
        row = {
            "Manufacturer": "Murata",
            "MfrPartName": part,
            "TChar": temp_char,
            "MaxTemp": max_temp,
            "Tolerance": tol_clean,
            # Dimensions
            "Package": package_code,
            "Length_mm": f"{l_mm:.4g}",
            "Width_mm": f"{w_mm:.4g}",
            "MaxThickness_mm": f"{t_mm:.4g}",
            "Volume_mm3": f"{vol_mm3:.6g}", 
            
            "SRF_MHz": srf_val,
            
            "Capacitance": f"{cap_f:.5e}",
            "VoltageRatedDC": f"{r_vol:.5g}",
            
            # Data Vectors
            "C_Cv__V": v_str, # Voltage points
            "C_Cv__C": c_str, # Cap points
            "ESR__Freq": freq_str,
            "ESR__Ohm": esr_str
        }
        rows.append(row)
        
        count += 1
        if count % 2000 == 0: 
            print(f"\rMerging: {count}/{len(candidates)}", end="")

    # 4. EXPORT
    print("\nWriting final CSV...")
    df_out = pd.DataFrame(rows)
    
    if df_out.empty:
        print("No matches found!")
        return
        
    # Sort
    df_out.sort_values(by=['Volume_mm3', 'VoltageRatedDC', 'Capacitance'], 
                       ascending=[True, True, False], inplace=True)
    
    # Final Columns Order
    cols = [
        'Manufacturer', 'MfrPartName', 'TChar', 'MaxTemp', 'Tolerance', 
        'Package', 'Length_mm', 'Width_mm', 'MaxThickness_mm', 'Volume_mm3', 'SRF_MHz',
        'Capacitance', 'VoltageRatedDC', 
        'C_Cv__V', 'C_Cv__C', 
        'ESR__Freq', 'ESR__Ohm'
    ]
            
    df_out = df_out[cols] 
    df_out.to_csv(OUTPUT_FILE, index=False)
    
    print(f"DONE! Library generated: {OUTPUT_FILE}")
    print(f"Total Parts Merged: {len(df_out)}")

if __name__ == "__main__":
    main()
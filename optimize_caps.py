import pandas as pd
import numpy as np
import sys

# --- USER CONSTRAINTS ---
TARGET_CAP_F      = 1.52e-6  # Target: 150 uF
TOLERANCE_PCT     = 0.1     # +/- 1% (Range: 148.5uF to 151.5uF)
MIN_RATED_VOLTS   = 6.0    # Safety constraint
OPERATING_VOLTS   = 6.0     # DC Bias point for derating
SEARCH_DEPTH      = 50      # Look at top 50 density leaders for hybrid combos

LIBRARY_FILE = "Murata_Unified_Library.csv"

# --- HELPER: HIGH PRECISION PARSER ---
def parse_cv_curve(v_str, c_str):
    try:
        # Clean brackets and split
        v_clean = str(v_str).replace('[', '').replace(']', '').strip()
        c_clean = str(c_str).replace('[', '').replace(']', '').strip()
        
        if not v_clean or not c_clean: return None, None
        
        v_arr = np.fromstring(v_clean, sep=' ')
        c_arr = np.fromstring(c_clean, sep=' ')
        
        return v_arr, c_arr
    except:
        return None, None

def get_exact_derated_cap(row, bias_v):
    """
    Returns exact float64 capacitance at bias_v using linear interpolation.
    """
    v_arr, c_arr = parse_cv_curve(row['V_Cv'], row['C_Cv'])
    
    if v_arr is None or len(v_arr) == 0: return 0.0
    
    # 1. Zero Volt Case
    if bias_v <= 0: return c_arr[0]
    
    # 2. Extrapolation (Flat)
    if bias_v > v_arr.max(): return c_arr[-1]
    
    # 3. Interpolation
    return np.interp(bias_v, v_arr, c_arr)

def main():
    print(f"--- PRECISION CAPACITOR OPTIMIZER ---")
    
    # Calculate Window
    target_min = TARGET_CAP_F * (1 - TOLERANCE_PCT/100.0)
    target_max = TARGET_CAP_F * (1 + TOLERANCE_PCT/100.0)
    
    print(f"Target: {TARGET_CAP_F*1e6:.2f} uF")
    print(f"Window: {target_min*1e6:.3f} uF  <-->  {target_max*1e6:.3f} uF  (±{TOLERANCE_PCT}%)")
    print(f"Bias:   {OPERATING_VOLTS} V")
    
    # 1. Load Library
    try:
        df = pd.read_csv(LIBRARY_FILE)
    except:
        print("Library file missing.")
        return

    # Filter candidates
    candidates = df[df['VoltageRatedDC'] >= MIN_RATED_VOLTS].copy()
    print(f"Scanning {len(candidates)} valid voltage candidates...")
    
    # 2. Pre-Calculate Exact Derated C for ALL parts
    valid_parts = []
    
    for i, row in candidates.iterrows():
        c_eff = get_exact_derated_cap(row, OPERATING_VOLTS)
        if c_eff <= 0: continue
        
        try: vol = float(row['Volume_mm3'])
        except: continue
        
        # Calculate Density Score for sorting
        density = c_eff / vol if vol > 0 else 0
        
        valid_parts.append({
            'Part': row['MfrPartName'],
            'Pkg': row['Package'],
            'C_Eff': c_eff,
            'Vol': vol,
            'Density': density
        })
        
    df_parts = pd.DataFrame(valid_parts)
    if df_parts.empty:
        print("No valid parts found.")
        return

    # Sort by Density to prioritize search
    df_parts.sort_values(by='Density', ascending=False, inplace=True)
    
    # Limit search space for N^2 Hybrid loop
    search_space = df_parts.head(SEARCH_DEPTH)
    
    solutions = []
    
    # --- OPTIMIZATION ENGINE ---
    
    # STRATEGY 1: Single Type (N * A)
    for i, row in search_space.iterrows():
        c_single = row['C_Eff']
        
        # Min count to enter window
        n_min = int(np.ceil(target_min / c_single))
        # Max count to stay in window
        n_max = int(np.floor(target_max / c_single))
        
        # Check if any integer N lands INSIDE the window
        for n in range(n_min, n_max + 1):
            total_c = n * c_single
            if target_min <= total_c <= target_max:
                total_v = n * row['Vol']
                solutions.append({
                    'Type': 'Single',
                    'Config': f"{n}x {row['Part']}",
                    'Details': f"{n}x {row['Pkg']} ({c_single*1e6:.3f}uF ea)",
                    'Total_Vol': total_v,
                    'Total_Cap': total_c
                })

    # STRATEGY 2: Hybrid (N_a * A + N_b * B)
    # A = Bulk (High Density), B = Trim (Precision)
    
    # Convert search space to list for faster iteration
    parts_list = search_space.to_dict('records')
    
    for i, part_a in enumerate(parts_list):
        c_a = part_a['C_Eff']
        v_a = part_a['Vol']
        
        # Max A we can fit without exceeding target_max
        max_a = int(np.floor(target_max / c_a))
        
        # Iterate N_a downwards from Max (Greedy approach)
        # We stop if N_a gets too low to be useful (e.g., < 50% of target) to save time
        min_a = int(max_a * 0.1) 
        
        for n_a in range(max_a, min_a, -1):
            cap_a_total = n_a * c_a
            vol_a_total = n_a * v_a
            
            remainder_min = target_min - cap_a_total
            remainder_max = target_max - cap_a_total
            
            # If A alone is inside window, we already caught it in Strategy 1
            if remainder_min <= 0 and remainder_max >= 0: continue
            
            # Now find Part B to fill the gap [remainder_min, remainder_max]
            # We need n_b * c_b to land in that gap
            
            for part_b in parts_list:
                if part_b['Part'] == part_a['Part']: continue # Skip self
                
                c_b = part_b['C_Eff']
                
                # Calculate required N_b range
                # If remainder is negative (A overshot min but under max?), set 0
                req_b_min = int(np.ceil(max(0, remainder_min) / c_b))
                req_b_max = int(np.floor(max(0, remainder_max) / c_b))
                
                for n_b in range(req_b_min, req_b_max + 1):
                    if n_b == 0: continue
                    
                    total_c = cap_a_total + (n_b * c_b)
                    
                    # Double check window (floating point safety)
                    if target_min <= total_c <= target_max:
                        total_v = vol_a_total + (n_b * part_b['Vol'])
                        
                        solutions.append({
                            'Type': 'Hybrid',
                            'Config': f"{n_a}x {part_a['Part']} + {n_b}x {part_b['Part']}",
                            'Details': f"{n_a}x {part_a['Pkg']} + {n_b}x {part_b['Pkg']}",
                            'Total_Vol': total_v,
                            'Total_Cap': total_c
                        })

    # --- RESULTS ---
    sol_df = pd.DataFrame(solutions)
    
    if sol_df.empty:
        print("\nNo valid configurations found within strict tolerance window.")
        print("Try widening TOLERANCE_PCT or increasing SEARCH_DEPTH.")
        return

    # Sort by Volume (Ascending) -> Minimize Size
    sol_df.sort_values(by='Total_Vol', ascending=True, inplace=True)
    
    print("\n--- TOP 10 MINIMAL VOLUME SOLUTIONS ---")
    print(f"{'Type':<8} | {'Volume (mm3)':<12} | {'Total Cap':<12} | {'Config'}")
    print("-" * 100)
    
    unique_check = set()
    count = 0
    
    for i, r in sol_df.iterrows():
        # Dedup based on config string
        if r['Config'] in unique_check: continue
        unique_check.add(r['Config'])
        
        v = f"{r['Total_Vol']:.5f}"
        c = f"{r['Total_Cap']*1e6:.3f} uF"
        
        print(f"{r['Type']:<8} | {v:<12} | {c:<12} | {r['Config']}")
        print(f"{'':<8} | {'':<12} | {'':<12} | ({r['Details']})")
        print("-" * 100)
        
        count += 1
        if count >= 10: break

    winner = sol_df.iloc[0]
    err_pct = (winner['Total_Cap'] - TARGET_CAP_F) / TARGET_CAP_F * 100
    
    print(f"\nWINNER: {winner['Config']}")
    print(f"Actual Cap: {winner['Total_Cap']*1e6:.4f} uF (Error: {err_pct:+.2f}%)")
    print(f"Total Vol:  {winner['Total_Vol']:.6f} mm3")

if __name__ == "__main__":
    main()
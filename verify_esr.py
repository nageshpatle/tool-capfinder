
import sys
import os
import pandas as pd
sys.path.append('src')
from optimizer import OptimizerService

def test_esr_logic():
    print("--- Verifying ESR Logic ---")
    
    # Path to real data
    library_path = "data/Murata_Unified_Library.csv"
    if not os.path.exists(library_path):
        print("Data file not found, skipping specific verification.")
        return

    opt = OptimizerService(library_path)
    
    # constraint
    constraints = {
        'target_cap': 10,
        'tolerance': 20,
        'dc_bias': 5,
        'max_count': 10,
        'min_rated_volt': 6.3,
        'target_freq': 100000, # 100 kHz
        'max_esr': 0.1, # Tight ESR
        'packages': ['0805', '1206', '1210'],
        'conn_type': 1
    }
    
    print(f"Running solve with freq={constraints['target_freq']}Hz, max_esr={constraints['max_esr']} Ohm")
    
    # Test generator
    gen = opt.solve_generator(constraints)
    results = []
    for prog, res in gen:
        if res:
            results = res
            
    if not results:
        print("No results found. (Might be too strict or logic error)")
    else:
        print(f"Found {len(results)} results.")
        print("Top 3 results:")
        for r in results[:3]:
            print(f"  - {r['BOM']} | Cap: {r['Cap']*1e6:.2f}uF | ESR: {r.get('ESR', -1):.4f} Ohm")
            
    # Unit Test get_esr
    print("\n--- Unit Test get_esr ---")
    # Grab a row with ESR data
    df = opt.df_library
    row_with_esr = df[df['ESR__Freq'].str.len() > 10].iloc[0]
    print(f"Testing Part: {row_with_esr['MfrPartName']}")
    
    freqs = [100, 1000, 10000, 100000, 1000000]
    for f in freqs:
        esr = opt.get_esr(row_with_esr, f)
        print(f"  Freq: {f} Hz -> ESR: {esr:.5f} Ohm")

if __name__ == "__main__":
    test_esr_logic()

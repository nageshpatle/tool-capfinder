
import pandas as pd
import numpy as np
from src.optimizer import OptimizerService

class MockOptimizer(OptimizerService):
    def __init__(self):
        self.df_library = pd.DataFrame()
        self.package_areas = {}
    
    def get_esr(self, row, f): return 0.01
    def get_derated(self, row, b): return float(row['Capacitance']) # No derating for test

def verify_depth2():
    opt = MockOptimizer()
    
    # Target: 1.0uF
    # Part A: 0.3uF
    # Part B: 0.7uF
    # Solution: 1xA + 1xB = 1.0uF
    
    # We also add a "Distractor" Part C: 0.1uF (requires 10x to hit target)
    
    mock_search = [
        {'P': 'PartA', 'K': '0402', 'C': 0.3e-6, 'V': 0.3, 'E': 0.01, 'H': 0.1, 'L':1.0, 'W':0.5, 'Url': '', 'A': 0.5},
        {'P': 'PartB', 'K': '0402', 'C': 0.7e-6, 'V': 0.7, 'E': 0.01, 'H': 0.1, 'L':1.0, 'W':0.5, 'Url': '', 'A': 0.5},
        {'P': 'PartC', 'K': '0402', 'C': 0.1e-6, 'V': 0.1, 'E': 0.01, 'H': 0.1, 'L':1.0, 'W':0.5, 'Url': '', 'A': 0.5},
    ]
    
    search_space = mock_search
    
    constraints = {
        'min_cap': 0.99e-6,
        'max_cap': 1.01e-6,
        'dc_bias': 0,
        'max_count': 10,
        'conn_type': 2, # Depth 2
        'max_sys_esr': 1.0
    }
    
    print("Testing Depth 2 Logic with:")
    print(f"Target: {constraints['min_cap']} - {constraints['max_cap']} F")
    print("Parts: A(0.3u), B(0.7u), C(0.1u)")
    
    # Isolate the Depth 2 loop logic from optimizer.py
    # Copy-pasting the relevant logic block for testing
    
    win = (constraints['min_cap'], constraints['max_cap'])
    max_n = constraints['max_count']
    max_sys_esr = constraints['max_sys_esr']
    sols = []
    
    # --- DEPTH 2 LOGIC ---
    for i, pA in enumerate(search_space):
        for pB in search_space:
            if pA['P'] == pB['P']: continue
            
            for nA in range(1, max_n):
                rem_min = win[0] - nA*pA['C']
                rem_max = win[1] - nA*pA['C']
                
                if rem_min <= 0 and rem_max <= 0: break
                
                nB_min = max(1, int(np.ceil(max(0, rem_min) / pB['C'])))
                nB_max = int(np.floor(rem_max / pB['C']))
                
                for nB in range(nB_min, nB_max + 1):
                    if nA + nB <= max_n:
                        tot_c = nA*pA['C'] + nB*pB['C']
                        if win[0] <= tot_c <= win[1]:
                            # Simplified append
                            sols.append(f"{nA}x {pA['P']} + {nB}x {pB['P']} = {tot_c*1e6:.2f}uF")

    print("\nSolutions Found:")
    for s in sols:
        print(s)
        
    expected = "1x PartA + 1x PartB" # Order might vary
    
    found = any("1x PartA + 1x PartB" in s or "1x PartB + 1x PartA" in s for s in sols)
    
    if found:
        print("\nSUCCESS: Found optimal combination.")
    else:
        print("\nFAILURE: Did not find optimal combination.")
        
    # Test valid mix of 2x A + 1x A? No, logic skips same part.
    # Test 3x A (0.9u) + 1x C (0.1u) = 1.0u
    found_mix = any("3x PartA + 1x PartC" in s or "1x PartC + 3x PartA" in s for s in sols)
    if found_mix:
        print("SUCCESS: Found 3x A + 1x C combination.")
    else:
         print("FAILURE: Did not find 3x A + 1x C combination.")

if __name__ == "__main__":
    verify_depth2()

import pandas as pd
import numpy as np
import re
import os

class OptimizerService:
    def __init__(self, library_path):
        self.library_path = library_path
        self.df_library = None
        self.package_areas = {
            "008004": 0.03125, "01005": 0.08, "0201": 0.18, "0204": 0.50,
            "0402": 0.50, "0306": 1.28, "0603": 1.28, "0508": 2.50,
            "0805": 2.50, "1111": 7.84, "0612": 5.12, "1206": 5.12,
            "1210": 8.00, "1808": 9.00, "1812": 14.40, "2211": 15.96,
            "2220": 28.50
        }
        self.load_library()

    def get_area_sort_key(self, pkg_name):
        key = str(pkg_name).strip().zfill(4)
        return self.package_areas.get(key, 999.0)

    def load_library(self):
        try:
            if not os.path.exists(self.library_path):
                print(f"Library file not found: {self.library_path}")
                return

            self.df_library = pd.read_csv(self.library_path)
            # Pre-calc MaxTemp
            self.df_library['MaxTemp_Val'] = self.df_library['MaxTemp'].apply(
                lambda x: float(re.sub(r'[^\d.]', '', str(x))) if pd.notna(x) else 85.0
            )
            # Normalize Package
            self.df_library['Package'] = self.df_library['Package'].apply(
                lambda x: str(x).strip().zfill(4)
            )
        except Exception as e:
            print(f"Error loading library: {e}")

    def get_available_packages(self):
        if self.df_library is None: return []
        unique_pkgs = self.df_library['Package'].unique().tolist()
        return sorted(unique_pkgs, key=self.get_area_sort_key)

    def get_derated(self, row, bias):
        try:
            # Parse vectors
            v_str = str(row['V_Cv']).replace('[', '').replace(']', '').strip()
            c_str = str(row['C_Cv']).replace('[', '').replace(']', '').strip()
            
            if not v_str or not c_str: return 0.0
            
            v = np.fromstring(v_str, sep=' ')
            c = np.fromstring(c_str, sep=' ')
            
            if len(v) == 0: return 0.0
            
            # Interpolate
            if bias <= 0: return c[0]
            if bias > v.max(): return c[-1]
            return np.interp(bias, v, c)
        except: 
            return 0.0

    def solve(self, constraints):
        # Unpack constraints
        target_F = float(constraints.get('target_cap', 100)) * 1e-6
        tol = float(constraints.get('tolerance', 1.0)) / 100.0
        bias = float(constraints.get('dc_bias', 5.0))
        max_n = int(constraints.get('max_count', 25))
        min_rated_v = float(constraints.get('min_rated_volt', 10.0))
        min_temp = float(constraints.get('min_temp', 85))
        allowed_pkgs = set(constraints.get('packages', []))
        conn_type = int(constraints.get('conn_type', 2)) # 1, 2, or 3

        win = (target_F * (1-tol), target_F * (1+tol))

        if self.df_library is None:
            return [{'error': 'Library not loaded'}]

        # FILTER
        mask = (self.df_library['VoltageRatedDC'] >= min_rated_v) & \
               (self.df_library['MaxTemp_Val'] >= min_temp) & \
               (self.df_library['Package'].isin(allowed_pkgs))
        
        candidates = self.df_library[mask].copy()
        
        processed = []
        for _, r in candidates.iterrows():
            ce = self.get_derated(r, bias)
            if ce > 0:
                vol = float(r['Volume_mm3']) if pd.notna(r['Volume_mm3']) else 0.0
                processed.append({
                    'P': r['MfrPartName'], 
                    'K': r['Package'], 
                    'C': ce, 
                    'V': vol
                })
        
        if not processed:
            return []

        # CALCULATE DENSITY
        for p in processed:
            p['D'] = p['C'] / p['V'] if p['V'] > 0 else 0

        df_proc = pd.DataFrame(processed)

        # SORTING STRATEGY (The Fix)
        # 1. Top 500 by Density
        # 2. Top 100 by Capacitance
        top_dens = df_proc.sort_values(by='D', ascending=False).head(500)
        top_cap = df_proc.sort_values(by='C', ascending=False).head(100)

        combined = pd.concat([top_dens, top_cap]).drop_duplicates(subset=['P'])
        search = combined.to_dict('records')

        sols = []

        # 1p Logic
        for pA in search:
            n_min = max(1, int(np.ceil(win[0]/pA['C'])))
            n_max = min(max_n, int(np.floor(win[1]/pA['C'])))
            
            for n in range(n_min, n_max+1):
                sols.append({
                    'Vol': n*pA['V'],
                    'Cap': n*pA['C'],
                    'Type': '1p',
                    'BOM': f"{n}x {pA['K']}",
                    'Cfg': f"{n}x {pA['P']} ({pA['K']})",
                    'Parts': [ {'part': pA['P'], 'count': n} ]
                })

        # 2p Logic
        if conn_type >= 2:
            for pA in search:
                for pB in search:
                    if pA['P'] == pB['P']: continue
                    
                    # Optimization: Iterate nA and solve for nB directly
                    # nA * C_A + nB * C_B ~= Target
                    # nB ~= (Target - nA * C_A) / C_B
                    
                    for nA in range(1, max_n):
                        rem_min = win[0] - nA*pA['C']
                        rem_max = win[1] - nA*pA['C']
                        
                        # Optimization: if remainder is negative, increasing nA further will only make it worse? 
                        # Not necessarily if we want 2p, but usually yes. 
                        # Actually if rem < 0, we already have too much cap with just A.
                        if rem_min <= 0 and rem_max <= 0: break # Optim
                        
                        # We need nB * C_B to be in [rem_min, rem_max]
                        # nB_min = ceil(rem_min / C_B)
                        # nB_max = floor(rem_max / C_B)
                        
                        if rem_min <= 0: rem_min = 0 # Can't have neg cap
                        
                        nB_min = int(np.ceil(rem_min / pB['C']))
                        nB_max = int(np.floor(rem_max / pB['C']))
                        
                        if nB_min < 1: nB_min = 1
                        
                        for nB in range(nB_min, nB_max + 1):
                            if nA + nB <= max_n:
                                tot_c = nA*pA['C'] + nB*pB['C']
                                if win[0] <= tot_c <= win[1]:
                                    sols.append({
                                        'Vol': nA*pA['V'] + nB*pB['V'],
                                        'Cap': tot_c,
                                        'Type': '2p',
                                        'BOM': f"{nA}x {pA['K']} + {nB}x {pB['K']}",
                                        'Cfg': f"{nA}x {pA['P']} + {nB}x {pB['P']}",
                                        'Parts': [ {'part': pA['P'], 'count': nA}, {'part': pB['P'], 'count': nB} ]
                                    })

        # 3p Logic
        if conn_type >= 3:
            # Limit scope for N^3
            subset = search[:15]
            for pA in subset:
                for pB in subset:
                    if pA['P'] == pB['P']: continue
                    for pC in subset:
                        if pC['P'] in [pA['P'], pB['P']]: continue
                        
                        # Simplified greedy(ish) 1,1,X check or small loop
                        # To keep it fast, we can just fix nA=1, nB=1 (or small range) and find nC?
                        # The original code only checked nA=1, nB=1. Wait, let's check
                        # "nA, nB = 1, 1" -> Yes, original code hardcoded 1,1 for A and B.
                        # Let's keep that optimization for now as 3p searches are explosive.
                        
                        nA, nB = 1, 1
                        rem_min = win[0] - (nA*pA['C'] + nB*pB['C'])
                        
                        if rem_min > 0:
                            nC = int(np.ceil(rem_min / pC['C']))
                            if nA + nB + nC <= max_n:
                                tot = nA*pA['C'] + nB*pB['C'] + nC*pC['C']
                                if win[0] <= tot <= win[1]:
                                    sols.append({
                                        'Vol': nA*pA['V'] + nB*pB['V'] + nC*pC['V'],
                                        'Cap': tot,
                                        'Type': '3p',
                                        'BOM': f"{nA}x {pA['K']} + {nB}x {pB['K']} + {nC}x {pC['K']}",
                                        'Cfg': f"{nA}x {pA['P']} + {nB}x {pB['P']} + {nC}x {pC['P']}",
                                        'Parts': [ {'part': pA['P'], 'count': nA}, {'part': pB['P'], 'count': nB}, {'part': pC['P'], 'count': nC} ]
                                    })

        # Final Sort and Limit
        df_sol = pd.DataFrame(sols)
        if df_sol.empty: return []
        
        df_sol = df_sol.sort_values(by='Vol').head(50)
        return df_sol.to_dict('records')

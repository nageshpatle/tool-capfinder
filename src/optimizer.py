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

            self.df_library = pd.read_csv(self.library_path, dtype={'Package': str})
            # Pre-calc MaxTemp
            self.df_library['MaxTemp_Val'] = self.df_library['MaxTemp'].apply(
                lambda x: float(re.sub(r'[^\d.]', '', str(x))) if pd.notna(x) else 85.0
            )
            # Normalize Package
            self.df_library['Package'] = self.df_library['Package'].apply(
                lambda x: str(x).strip()
            )

            # Ensure Dimensions are numeric
            for col in ['Length_mm', 'Width_mm', 'MaxThickness_mm']:
                if col in self.df_library.columns:
                    self.df_library[col] = pd.to_numeric(self.df_library[col], errors='coerce').fillna(0.0)
            
            # Cache available packages
            unique_pkgs = self.df_library['Package'].unique().tolist()
            self.cached_packages = sorted(unique_pkgs, key=self.get_area_sort_key)
            
        except Exception as e:
            print(f"Error loading library: {e}")

    def get_available_packages(self):
        if self.df_library is None: return []
        return getattr(self, 'cached_packages', [])

    def get_esr(self, row, freq_hz):
        try:
            # Parse vectors
            f_str = str(row.get('ESR__Freq', '')).replace('[', '').replace(']', '').strip()
            e_str = str(row.get('ESR__Ohm', '')).replace('[', '').replace(']', '').strip()
            
            if not f_str or not e_str: return 0.0
            
            f_vec = np.fromstring(f_str, sep=' ')
            e_vec = np.fromstring(e_str, sep=' ')
            
            if len(f_vec) == 0 or len(e_vec) == 0: return 0.0
            
            # Interpolate (Log-Log preferred for Freq vs Z/ESR)
            if freq_hz <= f_vec[0]: return e_vec[0]
            if freq_hz >= f_vec[-1]: return e_vec[-1]
            
            # Safe Log
            # Ensure positive inputs for log
            valid = (f_vec > 0) & (e_vec > 0)
            if not valid.all():
                # Fallback to linear if data is weird
                return np.interp(freq_hz, f_vec, e_vec)

            x = np.log10(freq_hz)
            xp = np.log10(f_vec[valid])
            fp = np.log10(e_vec[valid])
            
            log_res = np.interp(x, xp, fp)
            return np.power(10, log_res)
        except: 
            return 0.0

    def get_derated(self, row, bias):
        try:
            # Parse vectors
            v_str = str(row.get('C_Cv__V', '')).replace('[', '').replace(']', '').strip()
            c_str = str(row.get('C_Cv__C', '')).replace('[', '').replace(']', '').strip()
            
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

    def solve_generator(self, constraints):
        # Unpack constraints
        # Support both new Range inputs and legacy Target/Tol
        if 'min_cap' in constraints and 'max_cap' in constraints:
            min_c = float(constraints['min_cap'])
            max_c = float(constraints['max_cap'])
            # Derive a "target" for sorting/scoring purposes (midpoint)
            target_F = (min_c + max_c) / 2.0
            tol = 0.0 # Not used in range mode
        else:
            # Legacy
            target_F = float(constraints.get('target_cap', 100)) * 1e-6
            tol = float(constraints.get('tolerance', 1.0)) / 100.0
            min_c = target_F * (1 - tol)
            max_c = target_F * (1 + tol)

        win = (min_c, max_c)

        bias = float(constraints.get('dc_bias', 5.0))
        max_n = int(constraints.get('max_count', 25))
        
        # New: Overrated logic
        # If 'overrate_pct' is in constraints, use it to calc min_rated_v
        # Else use explicit 'min_rated_volt'
        overrate = float(constraints.get('overrate_pct', 0.0))
        if overrate > 0:
            min_rated_v = bias * (1.0 + overrate/100.0)
        else:
            min_rated_v = float(constraints.get('min_rated_volt', bias))

        min_temp = float(constraints.get('min_temp', 85))
        allowed_pkgs = set(constraints.get('packages', []))
        conn_type = int(constraints.get('conn_type', 2)) # 1, 2, or 3
        
        # New: Frequency & ESR
        target_freq = float(constraints.get('target_freq', 100000)) # Default 100kHz
        max_sys_esr = float(constraints.get('max_esr', 1.0)) # Default 1 Ohm

        if self.df_library is None:
            yield (0, [{'error': 'Library not loaded'}])
            return

        # FILTER
        yield (5, [])
        # SRF Filter: SRF_MHz * 1e6 > target_freq
        # Ensure SRF_MHz is numeric first? It should be from load_library but let's be safe or just use it.
        # We assume SRF_MHz is float.
        
        mask = (self.df_library['VoltageRatedDC'] >= min_rated_v) & \
               (self.df_library['MaxTemp_Val'] >= min_temp) & \
               (self.df_library['Package'].isin(allowed_pkgs)) & \
               ((self.df_library['SRF_MHz'] * 1e6) > target_freq)
        
        candidates = self.df_library[mask].copy()
        yield (10, [])
        
        processed = []
        for _, r in candidates.iterrows():
            ce = self.get_derated(r, bias)
            esr_val = self.get_esr(r, target_freq)
            
            if ce > 0:
                vol = float(r['Volume_mm3']) if pd.notna(r['Volume_mm3']) else 0.0
                h_val = float(r['MaxThickness_mm'])
                # Calculate Area dynamically: L * W
                len_mm = float(r.get('Length_mm', 0.0))
                wid_mm = float(r.get('Width_mm', 0.0))
                area_val = len_mm * wid_mm
                
                processed.append({
                    'P': r['MfrPartName'], 
                    'K': r['Package'], 
                    'C': ce, 
                    'V': vol,
                    'E': esr_val, # Store component ESR
                    'H': h_val,
                    'A': area_val,
                    'L': len_mm,  # Length for layout
                    'W': wid_mm,  # Width for layout
                    'Url': f"https://www.digikey.com/en/products/result?keywords={r['MfrPartName']}"
                })
        
        if not processed:
            yield (100, [])
            return

        # CALCULATE DENSITY
        for p in processed:
            p['D'] = p['C'] / p['V'] if p['V'] > 0 else 0

        df_proc = pd.DataFrame(processed)

        # SORTING STRATEGY
        top_dens = df_proc.sort_values(by='D', ascending=False).head(500)
        top_cap = df_proc.sort_values(by='C', ascending=False).head(100)

        combined = pd.concat([top_dens, top_cap]).drop_duplicates(subset=['P'])
        search = combined.to_dict('records')

        sols = []
        
        # 1p Logic
        yield (15, [])
        for pA in search:
            n_min = max(1, int(np.ceil(win[0]/pA['C'])))
            n_max = min(max_n, int(np.floor(win[1]/pA['C'])))
            
            for n in range(n_min, n_max+1):
                # Calc System ESR for 1p: ESR / n
                sys_esr = pA['E'] / n if n > 0 else pA['E']
                if sys_esr <= max_sys_esr:
                    sols.append({
                        'Vol': n*pA['V'],
                        'Cap': n*pA['C'],
                        'ESR': sys_esr,
                        'Area': n*pA['A'],
                        'Height': pA['H'],
                        'Type': '1p',
                        'BOM': f"{n}x {pA['K']}",
                        'Cfg': f"{n}x {pA['P']} ({pA['K']})",
                        'Parts': [ {'part': pA['P'], 'count': n, 'L': pA['L'], 'W': pA['W'], 'H': pA['H']} ],
                        'Links': pA['Url']
                    })
        
        if sols: yield (30, sols)

        # 2p Logic
        if conn_type >= 2:
            total_search = len(search)
            for i, pA in enumerate(search):
                # Progress update for 2p loop (30% to 80%)
                prog = 30 + int(50 * (i / total_search))
                if i % 10 == 0: yield (prog, sols)

                for pB in search:
                    if pA['P'] == pB['P']: continue
                    
                    for nA in range(1, max_n):
                        rem_min = win[0] - nA*pA['C']
                        rem_max = win[1] - nA*pA['C']
                        
                        if rem_min <= 0 and rem_max <= 0: break
                        
                        if rem_min <= 0: rem_min = 0
                        
                        nB_min = int(np.ceil(rem_min / pB['C']))
                        nB_max = int(np.floor(rem_max / pB['C']))
                        
                        if nB_min < 1: nB_min = 1
                        
                        for nB in range(nB_min, nB_max + 1):
                            if nA + nB <= max_n:
                                tot_c = nA*pA['C'] + nB*pB['C']
                                if win[0] <= tot_c <= win[1]:
                                    # Calc 2p ESR: 1 / ( (nA/Ra) + (nB/Rb) )
                                    # Avoid div by zero if ESR is 0 (unlikely but safe)
                                    gA = (nA/pA['E']) if pA['E'] > 0 else 999999
                                    gB = (nB/pB['E']) if pB['E'] > 0 else 999999
                                    sys_esr = 1.0 / (gA + gB)
                                    
                                    if sys_esr <= max_sys_esr:
                                        sols.append({
                                            'Vol': nA*pA['V'] + nB*pB['V'],
                                            'Cap': tot_c,
                                            'ESR': sys_esr,
                                            'Area': nA*pA['A'] + nB*pB['A'],
                                            'Height': max(pA['H'], pB['H']),
                                            'Type': '2p',
                                            'BOM': f"{nA}x {pA['K']} + {nB}x {pB['K']}",
                                            'Cfg': f"{nA}x {pA['P']} + {nB}x {pB['P']}",
                                            'Parts': [ {'part': pA['P'], 'count': nA, 'L': pA['L'], 'W': pA['W'], 'H': pA['H']}, {'part': pB['P'], 'count': nB, 'L': pB['L'], 'W': pB['W'], 'H': pB['H']} ],
                                            'Links': pA['Url']
                                        })

        # 3p Logic
        if conn_type >= 3:
            subset = search[:15]
            for i, pA in enumerate(subset):
                # Progress 80% to 95%
                prog = 80 + int(15 * (i / len(subset)))
                yield (prog, sols)

                for pB in subset:
                    if pA['P'] == pB['P']: continue
                    for pC in subset:
                        if pC['P'] in [pA['P'], pB['P']]: continue
                        
                        nA, nB = 1, 1
                        rem_min = win[0] - (nA*pA['C'] + nB*pB['C'])
                        
                        if rem_min > 0:
                            nC = int(np.ceil(rem_min / pC['C']))
                            if nA + nB + nC <= max_n:
                                tot = nA*pA['C'] + nB*pB['C'] + nC*pC['C']
                                if win[0] <= tot <= win[1]:
                                    gA = (nA/pA['E']) if pA['E'] > 0 else 999999
                                    gB = (nB/pB['E']) if pB['E'] > 0 else 999999
                                    gC = (nC/pC['E']) if pC['E'] > 0 else 999999
                                    sys_esr = 1.0 / (gA + gB + gC)
                                    
                                    if sys_esr <= max_sys_esr:
                                        sols.append({
                                            'Vol': nA*pA['V'] + nB*pB['V'] + nC*pC['V'],
                                            'Cap': tot,
                                            'ESR': sys_esr,
                                            'Area': nA*pA['A'] + nB*pB['A'] + nC*pC['A'],
                                            'Height': max(pA['H'], pB['H'], pC['H']),
                                            'Type': '3p',
                                            'BOM': f"{nA}x {pA['K']} + {nB}x {pB['K']} + {nC}x {pC['K']}",
                                            'Cfg': f"{nA}x {pA['P']} + {nB}x {pB['P']} + {nC}x {pC['P']}",
                                            'Parts': [ {'part': pA['P'], 'count': nA, 'L': pA['L'], 'W': pA['W'], 'H': pA['H']}, {'part': pB['P'], 'count': nB, 'L': pB['L'], 'W': pB['W'], 'H': pB['H']}, {'part': pC['P'], 'count': nC, 'L': pC['L'], 'W': pC['W'], 'H': pC['H']} ],
                                            'Links': pA['Url']
                                        })

        # Final Sort and Limit
        df_sol = pd.DataFrame(sols)
        # Yield final result
        if df_sol.empty: 
            yield (100, [])
        else:
            df_sol = df_sol.sort_values(by='Vol').head(50)
            yield (100, df_sol.to_dict('records'))

    def solve(self, constraints):
        # Wrapper for backward compatibility (non-streaming)
        gen = self.solve_generator(constraints)
        last_val = []
        for prog, val in gen:
            last_val = val
        return last_val

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

            # Note: low_memory=False to avoid DtypeWarning
            self.df_library = pd.read_csv(self.library_path, dtype={'Package': str}, low_memory=False)
            
            # Pre-calc MaxTemp
            # Column mapping check (ensure these columns exist)
            if 'MaxTemp' in self.df_library.columns:
                self.df_library['MaxTemp_Val'] = self.df_library['MaxTemp'].apply(
                    lambda x: float(re.sub(r'[^\d.]', '', str(x))) if pd.notna(x) else 85.0
                )
            else:
                self.df_library['MaxTemp_Val'] = 85.0

            # Normalize Package
            self.df_library['Package'] = self.df_library['Package'].apply(
                lambda x: str(x).strip()
            )

            # Ensure Dimensions are numeric
            for col in ['Length_mm', 'Width_mm', 'MaxThickness_mm']:
                if col in self.df_library.columns:
                    self.df_library[col] = pd.to_numeric(self.df_library[col], errors='coerce').fillna(0.0)

            # Cache available packages
            if self.df_library is not None:
                unique_pkgs = self.df_library['Package'].dropna().unique().tolist()
                self.cached_packages = sorted(unique_pkgs, key=self.get_area_sort_key)
            else:
                self.cached_packages = []
            
        except Exception as e:
            print(f"Error loading library: {e}")

    def get_available_packages(self):
        if self.df_library is None: return []
        return getattr(self, 'cached_packages', [])

    def get_esr(self, row, freq_hz):
        try:
            f_str = str(row.get('ESR__Freq', '')).replace('[', '').replace(']', '').strip()
            e_str = str(row.get('ESR__Ohm', '')).replace('[', '').replace(']', '').strip()
            if not f_str or not e_str: return 0.0
            f_vec = np.fromstring(f_str, sep=' ')
            e_vec = np.fromstring(e_str, sep=' ')
            if len(f_vec) == 0 or len(e_vec) == 0: return 0.0
            if freq_hz <= f_vec[0]: return e_vec[0]
            if freq_hz >= f_vec[-1]: return e_vec[-1]
            valid = (f_vec > 0) & (e_vec > 0)
            if not valid.all(): return np.interp(freq_hz, f_vec, e_vec)
            x = np.log10(freq_hz)
            xp = np.log10(f_vec[valid])
            fp = np.log10(e_vec[valid])
            log_res = np.interp(x, xp, fp)
            return np.power(10, log_res)
        except: 
            return 0.0

    def get_derated(self, row, bias):
        try:
            v_str = str(row.get('C_Cv__V', '')).replace('[', '').replace(']', '').strip()
            c_str = str(row.get('C_Cv__C', '')).replace('[', '').replace(']', '').strip()
            if not v_str or not c_str: return 0.0
            v = np.fromstring(v_str, sep=' ')
            c = np.fromstring(c_str, sep=' ')
            if len(v) == 0: return 0.0
            if bias <= 0: return c[0]
            if bias > v.max(): return c[-1]
            return np.interp(bias, v, c)
        except: 
            return 0.0

    def solve_generator(self, constraints):
        if self.df_library is None:
            yield (100, [], "Error: Murata database is not loaded.")
            return

        yield (2, [], f"Querying {len(self.df_library)} Murata caps from database...")
        
        # Unpack constraints
        if 'min_cap' in constraints and 'max_cap' in constraints:
            min_c = float(constraints['min_cap'])
            max_c = float(constraints['max_cap'])
            target_F = (min_c + max_c) / 2.0
        else:
            target_F = float(constraints.get('target_cap', 100)) * 1e-6
            tol = float(constraints.get('tolerance', 1.0)) / 100.0
            min_c = target_F * (1 - tol)
            max_c = target_F * (1 + tol)

        win = (min_c, max_c)
        bias = float(constraints.get('dc_bias', 5.0))
        max_n = int(constraints.get('max_count', 25))
        
        overrate = float(constraints.get('overrate_pct', 0.0))
        if overrate > 0:
            min_rated_v = bias * (1.0 + overrate/100.0)
        else:
            min_rated_v = float(constraints.get('min_rated_volt', bias))

        min_temp = float(constraints.get('min_temp', 85))
        allowed_pkgs = set(constraints.get('packages', []))
        conn_type = int(constraints.get('conn_type', 2))
        target_freq = float(constraints.get('target_freq', 100000))
        max_sys_esr = float(constraints.get('max_esr', 1.0))

        # FILTER
        yield (5, [], "Pruning library with loose Nominal Capacitance (±2 OOM), SRF, and Package filters...")
        
        # Ensure ESR and Derating columns exist to prevent total failure
        required = ['VoltageRatedDC', 'MaxTemp_Val', 'Package', 'SRF_MHz']
        for r in required:
            if r not in self.df_library.columns:
                yield (100, [], f"Error: Optimization failed. Column '{r}' not found in library.")
                return

        # Three-Stage Pre-Filtering (Fast)
        mask = (self.df_library['VoltageRatedDC'] >= min_rated_v) & \
               (self.df_library['MaxTemp_Val'] >= min_temp) & \
               (self.df_library['Package'].isin(allowed_pkgs)) & \
               ((self.df_library['SRF_MHz'] * 1e6) > target_freq)
        
        # Numeric Capacitance Check
        # Since 'Capacitance' is clean and float (Farads), we can filter directly.
        # We use a loose 100x margin (1% to 10000%) as requested to allow for derating/parallel flexibility
        if 'Capacitance' in self.df_library.columns:
            min_cutoff = min_c / 100.0
            max_cutoff = max_c * 1000.0
            mask = mask & (self.df_library['Capacitance'] >= min_cutoff) & \
                          (self.df_library['Capacitance'] <= max_cutoff)
        
        candidates = self.df_library[mask].copy()
        yield (10, [], f"Filtering caps based on C and V ({len(candidates)} remaining)...")
        
        yield (11, [], f"Calculating DC Bias derating & ESR for {len(candidates)} candidates...")
        
        processed = []
        for _, r in candidates.iterrows():
            ce = self.get_derated(r, bias)
            esr_val = self.get_esr(r, target_freq)
            if ce > 0:
                p_data = {
                    'P': r['MfrPartName'], 
                    'K': r['Package'], 
                    'C': ce, 
                    'V': float(r['Volume_mm3']) if pd.notna(r['Volume_mm3']) else 0.0,
                    'E': esr_val,
                    'H': float(r['MaxThickness_mm']),
                    'L': float(r.get('Length_mm', 0.0)),
                    'W': float(r.get('Width_mm', 0.0)),
                    'Url': f"https://www.digikey.com/en/products/result?keywords={r['MfrPartName']}"
                }
                p_data['A'] = p_data['L'] * p_data['W']
                processed.append(p_data)
        
        if not processed:
            yield (100, [], "Optimization complete: 0 results (no parts found within constraints).")
            return

        # CALCULATE DENSITY
        yield (12, [], f"Sorting {len(processed)} candidates based on Volumetric Density (C/V) and Derated Capacitance...")
        for p in processed:
            p['D'] = p['C'] / p['V'] if p['V'] > 0 else 0

        df_proc = pd.DataFrame(processed)
        top_dens = df_proc.sort_values(by='D', ascending=False).head(500)
        top_cap = df_proc.sort_values(by='C', ascending=False).head(100)
        # Also include smallest Volume parts (fillers)
        top_vol_asc = df_proc.sort_values(by='V', ascending=True).head(50)
        
        combined = pd.concat([top_dens, top_cap, top_vol_asc]).drop_duplicates(subset=['P'])
        search = combined.to_dict('records')
        
        yield (14, [], "Constructing search set of high-performance candidates...")

        sols = []
        MAX_SOLS = 1000
        
        def prune_solutions(s_list):
            if len(s_list) > MAX_SOLS * 2:
                s_list.sort(key=lambda x: x['Vol'])
                return s_list[:MAX_SOLS]
            return s_list

        def deduplicate_solutions(s_list):
            """Group electrically identical stacks."""
            groups = {}
            for sol in s_list:
                # Key: (Rounded DeratedCap, Rounded Vol, Rounded ESR, Cfg String)
                # We round to avoid floating point noise from different permutations
                # Cfg string (e.g. "5x 0201") ensures we don't merge different stack topologies
                key = (
                    round(sol['Cap'], 9), 
                    round(sol['Vol'], 6), 
                    round(sol['ESR'], 6),
                    sol['Height'],
                    sol['Cfg']
                )
                
                if key not in groups:
                    # Initialize group with primary solution
                    sol['Alts'] = [] 
                    groups[key] = sol
                else:
                    # This is a duplicate (alternative parts). Add to the group.
                    # We store a summary string of the parts
                    # Construct a readable alt string like "2x GRM... + 3x GRM..."
                    parts_str = " + ".join([f"{p['count']}x {p['part']}" for p in sol['Parts']])
                    groups[key]['Alts'].append(parts_str)
                    
            return list(groups.values())

        # Pool Depth 1 Logic
        yield (15, [], "Implementing Knapsack heuristics to find best candidates...")
        for pA in search:
            n_min = max(1, int(np.ceil(win[0]/pA['C'])))
            n_max = min(max_n, int(np.floor(win[1]/pA['C'])))
            for n in range(n_min, n_max+1):
                sys_esr = pA['E'] / n if n > 0 else pA['E']
                if sys_esr <= max_sys_esr:
                    sols.append({
                        'Vol': n*pA['V'], 'Cap': n*pA['C'], 'ESR': sys_esr, 'Area': n*pA['A'], 'Height': pA['H'],
                        'Type': '1p', 'BOM': f"{n}x {pA['K']}", 'Cfg': f"{n}x {pA['P']} ({pA['K']})",
                        'Parts': [ {'part': pA['P'], 'count': n, 'L': pA['L'], 'W': pA['W'], 'H': pA['H']} ],
                        'Links': pA['Url']
                    })
            sols = prune_solutions(sols)
        
        if sols: yield (30, sols, "Parallel-1 configurations found. Expanding search...")

        # Pool Depth 2 Logic
        if conn_type >= 2:
            total_search = len(search)
            yield (30, sols, "Executing Pool Depth 2 permutations search with Volume pruning...")
            for i, pA in enumerate(search):
                prog = 30 + int(50 * (i / total_search))
                if i % 10 == 0: 
                    yield (prog, sols, "Scanning candidates for Pool Depth 2 configurations...")

                for pB in search:
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
                                    gA = (nA/pA['E']) if pA['E'] > 0 else 999999
                                    gB = (nB/pB['E']) if pB['E'] > 0 else 999999
                                    sys_esr = 1.0 / (gA + gB)
                                    if sys_esr <= max_sys_esr:
                                        sols.append({
                                            'Vol': nA*pA['V'] + nB*pB['V'], 'Cap': tot_c, 'ESR': sys_esr, 'Area': nA*pA['A'] + nB*pB['A'],
                                            'Height': max(pA['H'], pB['H']), 'Type': '2p', 'BOM': f"{nA}x {pA['K']} + {nB}x {pB['K']}",
                                            'Cfg': f"{nA}x {pA['P']} + {nB}x {pB['P']}",
                                            'Parts': [ {'part': pA['P'], 'count': nA, 'L': pA['L'], 'W': pA['W'], 'H': pA['H']}, {'part': pB['P'], 'count': nB, 'L': pB['L'], 'W': pB['W'], 'H': pB['H']} ],
                                            'Links': pA['Url']
                                        })
                sols = prune_solutions(sols)

        # Pool Depth 3 Logic
        if conn_type >= 3:
            # Fix: Expand search space for 3-pool permutations. Top 15 was too restrictive.
            # Using Top 40 candidates drawn from diverse categories to ensuring "ingredients" for a good stack.
            
            # Construct distinct subsets of 'ingredients'
            sub_d = df_proc.sort_values(by='D', ascending=False).head(20) # Top 20 High Density (Base parts)
            sub_c = df_proc.sort_values(by='C', ascending=False).head(10) # Top 10 High Cap (Efficient Base)
            sub_v = df_proc.sort_values(by='V', ascending=True).head(10)  # Top 10 Smallest Volume (Filler/Trimmer)
            
            subset_df = pd.concat([sub_d, sub_c, sub_v]).drop_duplicates(subset=['P'])
            subset = subset_df.to_dict('records')
            
            yield (80, sols, f"Deep searching Pool Depth 3 combinations ({len(subset)} diverse candidates)...")
            
            subset_len = len(subset)
            for i, pA in enumerate(subset):
                prog = 80 + int(15 * (i / subset_len))
                yield (prog, sols, f"Scanning permutations {i+1}/{subset_len} for Pool Depth 3...")
                
                # Iterate nA
                rem_min_A = win[0] - 1*pA['C'] # Minimal possible remainder
                n_max_A = min(max_n - 2, int(np.floor(win[1]/pA['C']))) # Leave room for at least 1 B and 1 C
                
                for nA in range(1, n_max_A + 1):
                    rem_after_A_min = win[0] - nA*pA['C']
                    rem_after_A_max = win[1] - nA*pA['C']
                    
                    if rem_after_A_max <= 0: break # Overshot target

                    for pB in subset:
                        if pA['P'] == pB['P']: continue
                        
                        # Iterate nB
                        n_max_B = min(max_n - nA - 1, int(np.floor(rem_after_A_max/pB['C'])))
                        
                        for nB in range(1, n_max_B + 1):
                            rem_after_B_min = rem_after_A_min - nB*pB['C']
                            rem_after_B_max = rem_after_A_max - nB*pB['C']
                            
                            if rem_after_B_max <= 0: break

                            for pC in subset:
                                if pC['P'] in [pA['P'], pB['P']]: continue
                                
                                # Solve for nC directly
                                # We need: rem_after_B_min <= nC*pC['C'] <= rem_after_B_max
                                nC_min = max(1, int(np.ceil(rem_after_B_min / pC['C'])))
                                nC_max = int(np.floor(rem_after_B_max / pC['C']))
                                
                                if nC_min > nC_max: continue
                                
                                # nC_min is our candidate count
                                nC = nC_min
                                
                                # Check total count constraint
                                if nA + nB + nC <= max_n:
                                    tot = nA*pA['C'] + nB*pB['C'] + nC*pC['C']
                                    
                                    # Since we calculated nC based on win, tot should be in range, but check float precision
                                    if win[0] <= tot <= win[1]:
                                        gA = (nA/pA['E']) if pA['E'] > 0 else 999999
                                        gB = (nB/pB['E']) if pB['E'] > 0 else 999999
                                        gC = (nC/pC['E']) if pC['E'] > 0 else 999999
                                        
                                        sys_esr = 1.0 / (gA + gB + gC)
                                        if sys_esr <= max_sys_esr:
                                            sols.append({
                                                'Vol': nA*pA['V'] + nB*pB['V'] + nC*pC['V'], 'Cap': tot, 
                                                'ESR': sys_esr, 'Area': nA*pA['A'] + nB*pB['A'] + nC*pC['A'],
                                                'Height': max(pA['H'], pB['H'], pC['H']), 'Type': '3p', 
                                                'BOM': f"{nA}x {pA['K']} + {nB}x {pB['K']} + {nC}x {pC['K']}",
                                                'Cfg': f"{nA}x {pA['P']} + {nB}x {pB['P']} + {nC}x {pC['P']}",
                                                'Parts': [ 
                                                    {'part': pA['P'], 'count': nA, 'L': pA['L'], 'W': pA['W'], 'H': pA['H']}, 
                                                    {'part': pB['P'], 'count': nB, 'L': pB['L'], 'W': pB['W'], 'H': pB['H']}, 
                                                    {'part': pC['P'], 'count': nC, 'L': pC['L'], 'W': pC['W'], 'H': pC['H']} 
                                                ],
                                                'Links': pA['Url']
                                            })
                            # Prune inner loop occasionally
                            if len(sols) > MAX_SOLS * 3:
                                sols = prune_solutions(sols)
                    
                    # Mid-loop prune
                    if len(sols) > MAX_SOLS * 2:
                        sols = prune_solutions(sols)

        # Final Sort and Limit
        yield (95, sols, f"Consolidating identical configurations from {len(sols)} raw results...")
        sols = deduplicate_solutions(sols)
        
        yield (98, sols, f"Optimization complete. Ranking {len(sols)} unique valid stacks...")
        df_sol = pd.DataFrame(sols)
        if df_sol.empty: 
            yield (100, [], "Optimization complete: 0 results.")
            return

        df_sol = df_sol.sort_values(by='Vol').head(50)
        yield (100, df_sol.to_dict('records'), f"Running Bin Packing algorithm to optimize layout for solution stacks...")

    def solve(self, constraints):
        gen = self.solve_generator(constraints)
        last_val = []
        for prog, val, status in gen:
            last_val = val
        return last_val

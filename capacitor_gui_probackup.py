import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import numpy as np
import threading
import re

# --- CONFIGURATION ---
LIBRARY_FILE = "Murata_Unified_Library.csv"

# --- HELPER: SORTING LOGIC ---
PACKAGE_AREAS = {
    "008004": 0.03125,
    "01005":  0.08,
    "0201":   0.18,
    "0204":   0.50,
    "0402":   0.50,
    "0306":   1.28,
    "0603":   1.28,
    "0508":   2.50,
    "0805":   2.50,
    "1111":   7.84,
    "0612":   5.12,
    "1206":   5.12,
    "1210":   8.00,
    "1808":   9.00,
    "1812":   14.40,
    "2211":   15.96,
    "2220":   28.50
}

def get_area_sort_key(pkg_name):
    key = str(pkg_name).strip()
    if key in PACKAGE_AREAS: return PACKAGE_AREAS[key]
    if "0"+key in PACKAGE_AREAS: return PACKAGE_AREAS["0"+key]
    return 999.0

class CapOptimizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Murata Capacitor Bank Architect V3")
        self.root.geometry("1350x900")
        
        # Data
        self.df_library = None
        self.all_packages = []
        self.package_vars = {}
        
        self.load_library()
        
        # --- UI LAYOUT ---
        main_pane = tk.PanedWindow(root, orient="horizontal")
        main_pane.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Left Panel
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, width=380)
        
        # Inputs
        input_frame = ttk.LabelFrame(left_frame, text="Design Constraints", padding=10)
        input_frame.pack(side="top", fill="x", padx=5, pady=5)
        self.create_inputs(input_frame)
        
        # Filters
        filter_frame = ttk.LabelFrame(left_frame, text="Allowed Packages (Sorted by Size)", padding=10)
        filter_frame.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        self.create_package_filter(filter_frame)
        
        # Right Panel
        result_frame = ttk.LabelFrame(main_pane, text="Optimization Results (Minimize Volume)", padding=10)
        main_pane.add(result_frame)
        self.create_results_table(result_frame)

    def load_library(self):
        try:
            self.df_library = pd.read_csv(LIBRARY_FILE)
            def clean_temp(x):
                try: return float(str(x).replace('C','').strip())
                except: return 85.0
            self.df_library['MaxTemp_Val'] = self.df_library['MaxTemp'].apply(clean_temp)
            self.df_library['Package'] = self.df_library['Package'].astype(str)
            unique_pkgs = self.df_library['Package'].unique().tolist()
            self.all_packages = sorted(unique_pkgs, key=get_area_sort_key)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load library: {e}")
            self.root.destroy()

    def create_inputs(self, parent):
        parent.columnconfigure(1, weight=1)
        
        ttk.Label(parent, text="Target Cap (uF):").grid(row=0, column=0, sticky="w", pady=2)
        self.ent_cap = ttk.Entry(parent); self.ent_cap.insert(0, "100")
        self.ent_cap.grid(row=0, column=1, sticky="ew", pady=2)
        
        ttk.Label(parent, text="Tolerance (+/- %):").grid(row=1, column=0, sticky="w", pady=2)
        self.ent_tol = ttk.Entry(parent); self.ent_tol.insert(0, "1.0")
        self.ent_tol.grid(row=1, column=1, sticky="ew", pady=2)
        
        ttk.Label(parent, text="DC Bias (V):").grid(row=2, column=0, sticky="w", pady=2)
        self.ent_bias = ttk.Entry(parent); self.ent_bias.insert(0, "5.0")
        self.ent_bias.grid(row=2, column=1, sticky="ew", pady=2)
        
        ttk.Label(parent, text="Min Rated Volts:").grid(row=3, column=0, sticky="w", pady=2)
        self.ent_rated = ttk.Entry(parent); self.ent_rated.insert(0, "10.0")
        self.ent_rated.grid(row=3, column=1, sticky="ew", pady=2)
        
        ttk.Label(parent, text="Min Temp (C):").grid(row=4, column=0, sticky="w", pady=2)
        self.combo_temp = ttk.Combobox(parent, values=["85", "105", "125", "150"], state="readonly")
        self.combo_temp.current(0)
        self.combo_temp.grid(row=4, column=1, sticky="ew", pady=2)
        
        ttk.Separator(parent, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)
        
        ttk.Label(parent, text="Max Component Types:").grid(row=6, column=0, sticky="nw", pady=2)
        
        # Updated Logic: "Max Limit" instead of "Mode"
        self.var_max_types = tk.IntVar(value=2)
        frame_radio = ttk.Frame(parent)
        frame_radio.grid(row=6, column=1, sticky="ew")
        
        ttk.Radiobutton(frame_radio, text="1 (Single)", variable=self.var_max_types, value=1).pack(anchor="w")
        ttk.Radiobutton(frame_radio, text="Up to 2 (Dual)", variable=self.var_max_types, value=2).pack(anchor="w")
        ttk.Radiobutton(frame_radio, text="Up to 3 (Triple)", variable=self.var_max_types, value=3).pack(anchor="w")
        
        ttk.Separator(parent, orient="horizontal").grid(row=7, column=0, columnspan=2, sticky="ew", pady=10)
        
        self.btn_run = ttk.Button(parent, text="RUN OPTIMIZER", command=self.run_optimization)
        self.btn_run.grid(row=8, column=0, columnspan=2, sticky="ew", pady=5)

    def create_package_filter(self, parent):
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Select All", command=lambda: self.toggle_pkgs(True)).pack(side="left", fill="x", expand=True)
        ttk.Button(btn_frame, text="Select None", command=lambda: self.toggle_pkgs(False)).pack(side="right", fill="x", expand=True)

        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)
        
        self.scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, pady=5)
        scrollbar.pack(side="right", fill="y", pady=5)
        
        for pkg in self.all_packages:
            var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(self.scroll_frame, text=pkg, variable=var)
            chk.pack(anchor="w", padx=5)
            self.package_vars[pkg] = var

    def toggle_pkgs(self, state):
        for var in self.package_vars.values(): var.set(state)

    def create_results_table(self, parent):
        # Added "Type" Column
        cols = ("Rank", "Type", "Volume (mm3)", "Actual Cap (uF)", "Configuration", "Details")
        self.tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse")
        
        for col in cols: self.tree.heading(col, text=col)
        
        self.tree.column("Rank", width=40, anchor="center")
        self.tree.column("Type", width=60, anchor="center") # New
        self.tree.column("Volume (mm3)", width=90, anchor="center")
        self.tree.column("Actual Cap (uF)", width=100, anchor="center")
        self.tree.column("Configuration", width=300, anchor="w")
        self.tree.column("Details", width=300, anchor="w")
        
        ysb = ttk.Scrollbar(parent, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(parent, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        parent.rowconfigure(0, weight=1); parent.columnconfigure(0, weight=1)

    def get_derated_cap(self, row, bias):
        try:
            v_str = str(row['V_Cv']).replace('[','').replace(']','').strip()
            c_str = str(row['C_Cv']).replace('[','').replace(']','').strip()
            if not v_str: return 0.0
            v_arr = np.fromstring(v_str, sep=' ')
            c_arr = np.fromstring(c_str, sep=' ')
            if bias <= 0: return c_arr[0]
            if bias >= v_arr.max(): return c_arr[-1]
            return np.interp(bias, v_arr, c_arr)
        except: return 0.0

    def run_optimization(self):
        self.btn_run.config(state="disabled", text="Calculating...")
        threading.Thread(target=self.solve_backend, daemon=True).start()

    def solve_backend(self):
        try:
            target_uF = float(self.ent_cap.get())
            tol_pct = float(self.ent_tol.get())
            bias_v = float(self.ent_bias.get())
            min_rated_v = float(self.ent_rated.get())
            min_temp = float(self.combo_temp.get())
            max_types = self.var_max_types.get() # 1, 2, or 3
            
            target_F = target_uF * 1e-6
            win_min = target_F * (1 - tol_pct/100.0)
            win_max = target_F * (1 + tol_pct/100.0)
            
            valid_pkgs = [p for p, v in self.package_vars.items() if v.get()]
            mask = (
                (self.df_library['VoltageRatedDC'] >= min_rated_v) &
                (self.df_library['MaxTemp_Val'] >= min_temp) &
                (self.df_library['Package'].astype(str).isin(valid_pkgs))
            )
            candidates = self.df_library[mask].copy()
            
            if len(candidates) == 0:
                self.post_results([])
                return

            # Pre-calc
            processed = []
            for _, row in candidates.iterrows():
                c_eff = self.get_derated_cap(row, bias_v)
                if c_eff <= 0: continue
                try: vol = float(row['Volume_mm3'])
                except: continue
                processed.append({
                    'Part': row['MfrPartName'], 'Pkg': str(row['Package']),
                    'C_Eff': c_eff, 'Vol': vol,
                    'Density': c_eff/vol if vol > 0 else 0
                })
            
            df_parts = pd.DataFrame(processed)
            df_parts.sort_values(by='Density', ascending=False, inplace=True)
            search_space = df_parts.head(40).to_dict('records')
            
            solutions = []
            
            # 1. ALWAYS RUN SINGLE (Logic: Max Types >= 1)
            for p in search_space:
                n_min = int(np.ceil(win_min / p['C_Eff']))
                n_max = int(np.floor(win_max / p['C_Eff']))
                for n in range(n_min, n_max + 1):
                    c = n * p['C_Eff']
                    if win_min <= c <= win_max:
                        solutions.append({
                            'Type': 'Single', 'Vol': n*p['Vol'], 'Cap': c,
                            'Cfg': f"{n}x {p['Part']}", 'Det': f"{n}x {p['Pkg']}"
                        })

            # 2. RUN HYBRID 2 (Logic: Max Types >= 2)
            if max_types >= 2:
                for pA in search_space:
                    max_nA = int(np.floor(win_max / pA['C_Eff']))
                    start_nA = int(max_nA * 0.1)
                    
                    for nA in range(max_nA, start_nA, -1):
                        rem_min = win_min - (nA * pA['C_Eff'])
                        rem_max = win_max - (nA * pA['C_Eff'])
                        if rem_max < 0: continue
                        if rem_min <= 0: continue 
                        
                        for pB in search_space:
                            if pB['Part'] == pA['Part']: continue
                            nB_min = int(np.ceil(rem_min / pB['C_Eff']))
                            nB_max = int(np.floor(rem_max / pB['C_Eff']))
                            for nB in range(nB_min, nB_max + 1):
                                if nB == 0: continue
                                c = (nA*pA['C_Eff']) + (nB*pB['C_Eff'])
                                if win_min <= c <= win_max:
                                    solutions.append({
                                        'Type': 'Dual',
                                        'Vol': (nA*pA['Vol']) + (nB*pB['Vol']), 'Cap': c,
                                        'Cfg': f"{nA}x {pA['Part']} + {nB}x {pB['Part']}",
                                        'Det': f"{nA}x {pA['Pkg']} + {nB}x {pB['Pkg']}"
                                    })

            # 3. RUN HYBRID 3 (Logic: Max Types >= 3)
            if max_types >= 3:
                top_20 = search_space[:20]
                for pA in top_20:
                    max_nA = int(np.floor(win_max / pA['C_Eff']))
                    for nA in range(max_nA, 0, -1):
                        curr = nA * pA['C_Eff']
                        rem_max1 = win_max - curr
                        if rem_max1 <= 0: continue
                        
                        for pB in top_20:
                            if pB['Part'] == pA['Part']: continue
                            max_nB = int(np.floor(rem_max1 / pB['C_Eff']))
                            for nB in range(max_nB, 0, -1):
                                curr2 = curr + (nB*pB['C_Eff'])
                                rem_min2 = win_min - curr2
                                rem_max2 = win_max - curr2
                                if rem_max2 < 0: continue
                                if rem_min2 <= 0: continue
                                
                                for pC in top_20:
                                    if pC['Part'] in [pA['Part'], pB['Part']]: continue
                                    nC_min = int(np.ceil(rem_min2 / pC['C_Eff']))
                                    nC_max = int(np.floor(rem_max2 / pC['C_Eff']))
                                    for nC in range(nC_min, nC_max + 1):
                                        if nC == 0: continue
                                        c = curr2 + (nC*pC['C_Eff'])
                                        if win_min <= c <= win_max:
                                            solutions.append({
                                                'Type': 'Triple',
                                                'Vol': (nA*pA['Vol']) + (nB*pB['Vol']) + (nC*pC['Vol']),
                                                'Cap': c,
                                                'Cfg': f"{nA}x {pA['Part']} + {nB}x {pB['Part']} + {nC}x {pC['Part']}",
                                                'Det': f"{nA}x {pA['Pkg']} + {nB}x {pB['Pkg']} + {nC}x {pC['Pkg']}"
                                            })
            
            self.post_results(solutions)
            
        except Exception as e:
            print(f"Backend Error: {e}")
            self.post_results([])

    def post_results(self, solutions):
        def _update():
            for i in self.tree.get_children(): self.tree.delete(i)
            if not solutions:
                messagebox.showinfo("Optimization", "No solutions found.")
            else:
                df = pd.DataFrame(solutions)
                # Global Sort by Volume
                df.sort_values(by='Vol', ascending=True, inplace=True)
                
                for rnk, (i, r) in enumerate(df.head(100).iterrows(), 1):
                    self.tree.insert("", "end", values=(
                        rnk,
                        r['Type'], # Explicit Type Column
                        f"{r['Vol']:.5f}",
                        f"{r['Cap']*1e6:.3f}",
                        r['Cfg'],
                        r['Det']
                    ))
            self.btn_run.config(state="normal", text="RUN OPTIMIZER")
        self.root.after(0, _update)

if __name__ == "__main__":
    root = tk.Tk()
    app = CapOptimizerApp(root)
    root.mainloop()
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import numpy as np
import threading
import webbrowser
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
    key = str(pkg_name).strip().zfill(4)
    return PACKAGE_AREAS.get(key, 999.0)

class CapOptimizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Murata Capacitor Bank Architect V4.3")
        self.root.geometry("1500x950")
        
        self.df_library = None
        self.all_packages = []
        self.package_vars = {}
        
        self.load_library()
        
        # UI Layout
        main_pane = tk.PanedWindow(root, orient="horizontal")
        main_pane.pack(fill="both", expand=True, padx=5, pady=5)
        
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, width=420)
        
        input_frame = ttk.LabelFrame(left_frame, text="Design Constraints", padding=10)
        input_frame.pack(side="top", fill="x", padx=5, pady=5)
        self.create_inputs(input_frame)
        
        filter_frame = ttk.LabelFrame(left_frame, text="Allowed Packages (Sorted by Area)", padding=10)
        filter_frame.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        self.create_package_filter(filter_frame)
        
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame)
        
        result_label_frame = ttk.LabelFrame(right_frame, text="Results (Double-Click Row to Open Digi-Key Search)", padding=10)
        result_label_frame.pack(fill="both", expand=True)
        self.create_results_table(result_label_frame)

        # Credits Footer
        footer = tk.Label(root, text="Made with Meraki by Nagesh Patle ✨🧘🏽‍♂️", 
                          font=("Segoe Script", 13, "italic"), fg="#5D3FD3")
        footer.pack(side="bottom", pady=15)

    def load_library(self):
        try:
            self.df_library = pd.read_csv(LIBRARY_FILE)
            self.df_library['MaxTemp_Val'] = self.df_library['MaxTemp'].apply(lambda x: float(re.sub(r'[^\d.]', '', str(x))) if pd.notna(x) else 85.0)
            self.df_library['Package'] = self.df_library['Package'].apply(lambda x: str(x).strip().zfill(4))
            unique_pkgs = self.df_library['Package'].unique().tolist()
            self.all_packages = sorted(unique_pkgs, key=get_area_sort_key)
        except Exception as e:
            messagebox.showerror("Error", f"Library Load Failed: {e}")
            self.root.destroy()

    def create_inputs(self, parent):
        parent.columnconfigure(1, weight=1)
        
        ttk.Label(parent, text="Target Cap (uF):").grid(row=0, column=0, sticky="w")
        self.ent_cap = ttk.Entry(parent); self.ent_cap.insert(0, "100"); self.ent_cap.grid(row=0, column=1, sticky="ew")
        
        ttk.Label(parent, text="Tol (+/- %):").grid(row=1, column=0, sticky="w")
        self.ent_tol = ttk.Entry(parent); self.ent_tol.insert(0, "1.0"); self.ent_tol.grid(row=1, column=1, sticky="ew")
        
        ttk.Label(parent, text="DC Bias (V):").grid(row=2, column=0, sticky="w")
        self.ent_bias = ttk.Entry(parent); self.ent_bias.insert(0, "5.0"); self.ent_bias.grid(row=2, column=1, sticky="ew")
        
        ttk.Label(parent, text="Max Total Count:").grid(row=3, column=0, sticky="w")
        self.ent_max_n = ttk.Entry(parent); self.ent_max_n.insert(0, "25"); self.ent_max_n.grid(row=3, column=1, sticky="ew")
        
        ttk.Separator(parent, orient="horizontal").grid(row=4, column=0, columnspan=2, sticky="ew", pady=10)
        
        ttk.Label(parent, text="Min Rated (V):").grid(row=5, column=0, sticky="w")
        self.ent_rated = ttk.Entry(parent); self.ent_rated.insert(0, "10.0"); self.ent_rated.grid(row=5, column=1, sticky="ew")
        
        ttk.Label(parent, text="Min Temp (C):").grid(row=6, column=0, sticky="w")
        self.combo_temp = ttk.Combobox(parent, values=["85", "105", "125"], state="readonly"); self.combo_temp.current(0); self.combo_temp.grid(row=6, column=1, sticky="ew")
        
        ttk.Label(parent, text="Connection Type:").grid(row=7, column=0, sticky="nw", pady=5)
        self.var_types = tk.IntVar(value=2)
        f_radio = ttk.Frame(parent)
        f_radio.grid(row=7, column=1, sticky="ew")
        ttk.Radiobutton(f_radio, text="1p (Single Type)", variable=self.var_types, value=1).pack(anchor="w")
        ttk.Radiobutton(f_radio, text="2p (Dual Parallel)", variable=self.var_types, value=2).pack(anchor="w")
        ttk.Radiobutton(f_radio, text="3p (Triple Parallel)", variable=self.var_types, value=3).pack(anchor="w")
        
        self.btn_run = ttk.Button(parent, text="OPTIMIZE BANK", command=self.run_optimization)
        self.btn_run.grid(row=8, column=0, columnspan=2, sticky="ew", pady=10)
        
        self.progress = ttk.Progressbar(parent, orient="horizontal", mode="determinate", length=200)
        # We don't grid it yet; we'll swap it with the button when running

    def create_package_filter(self, parent):
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        sf = ttk.Frame(canvas)
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=sf, anchor="nw")
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for pkg in self.all_packages:
            var = tk.BooleanVar(value=True)
            ttk.Checkbutton(sf, text=f"{pkg}", variable=var).pack(anchor="w")
            self.package_vars[pkg] = var

    def create_results_table(self, parent):
        cols = ("Rank", "Type", "Vol (mm3)", "Cap (uF)", "BOM Breakdown", "Full Configuration")
        self.tree = ttk.Treeview(parent, columns=cols, show="headings")
        for c in cols: self.tree.heading(c, text=c)
        self.tree.column("Rank", width=40, anchor="center")
        self.tree.column("Type", width=50, anchor="center")
        self.tree.column("Vol (mm3)", width=90, anchor="center")
        self.tree.column("Cap (uF)", width=90, anchor="center")
        self.tree.column("BOM Breakdown", width=200, anchor="w")
        self.tree.column("Full Configuration", width=650, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self.open_digikey)

    def open_digikey(self, event):
        item = self.tree.selection()[0]
        config_str = self.tree.item(item, "values")[5]
        parts = re.findall(r'GR[M|J|A|Q]\w+', config_str)
        for p in parts:
            webbrowser.open(f"https://www.digikey.com/en/products/result?keywords={p}")

    def get_derated(self, row, bias):
        try:
            v = np.fromstring(row['V_Cv'].strip('[]'), sep=' ')
            c = np.fromstring(row['C_Cv'].strip('[]'), sep=' ')
            return np.interp(bias, v, c) if bias < v.max() else c[-1]
        except: return 0.0

    def run_optimization(self):
        self.btn_run.grid_remove()
        self.progress.grid(row=8, column=0, columnspan=2, sticky="ew", pady=10)
        self.progress['value'] = 0
        self.root.update_idletasks()
        threading.Thread(target=self.solve, daemon=True).start()

    def solve(self):
        try:
            target_F = float(self.ent_cap.get()) * 1e-6
            tol = float(self.ent_tol.get()) / 100.0
            bias = float(self.ent_bias.get())
            max_n_limit = int(self.ent_max_n.get())
            win = (target_F * (1-tol), target_F * (1+tol))
            
            pkgs = [p for p,v in self.package_vars.items() if v.get()]
            mask = (self.df_library['VoltageRatedDC'] >= float(self.ent_rated.get())) & \
                   (self.df_library['MaxTemp_Val'] >= float(self.combo_temp.get())) & \
                   (self.df_library['Package'].isin(pkgs))
            
            lib = self.df_library[mask].copy()
            processed = []
            for _, r in lib.iterrows():
                ce = self.get_derated(r, bias)
                if ce > 0: processed.append({'P': r['MfrPartName'], 'K': r['Package'], 'C': ce, 'V': r['Volume_mm3']})
            
            # Calculate Density for sorting
            for p in processed:
                p['D'] = p['C'] / p['V'] if p['V'] > 0 else 0

            df = pd.DataFrame(processed)
            
            # STRATEGY: Select candidates from both Density (efficiency) and Capacitance (bulk)
            # 1. Top 500 by Density (Best for volume)
            # 2. Top 100 by Capacitance (Best for reducing count)
            
            top_density = df.sort_values(by='D', ascending=False).head(500)
            top_cap     = df.sort_values(by='C', ascending=False).head(100)
            
            # Combine and dedup
            combined = pd.concat([top_density, top_cap]).drop_duplicates(subset=['P'])
            
            search = combined.to_dict('records')
            sols = []
            
            # --- PROGRESS TRACKING ---
            total_ops = len(search) # 1p
            if self.var_types.get() >= 2: total_ops += len(search) # 2p (outer loop)
            if self.var_types.get() >= 3: total_ops += 15 # 3p (outer loop limited to 15)
            
            current_op = 0
            def report_progress():
                p = (current_op / max(1, total_ops)) * 100
                self.root.after(0, lambda: self.progress.configure(value=p))
            
            # 1p logic
            for pA in search:
                n_min = max(1, int(np.ceil(win[0]/pA['C'])))
                n_max = min(max_n_limit, int(np.floor(win[1]/pA['C'])))
                for n in range(n_min, n_max+1):
                    sols.append({'Vol': n*pA['V'], 'Cap': n*pA['C'], 'Type': '1p', 'BOM': f"{n}x {pA['K']}", 'Cfg': f"{n}x {pA['P']} ({pA['K']})"})
                
                current_op += 1
                if current_op % 10 == 0: report_progress()

            # 2p logic
            if self.var_types.get() >= 2:
                for pA in search:
                    current_op += 1
                    if current_op % 5 == 0: report_progress()
                    
                    for pB in search:
                        if pA['P'] == pB['P']: continue
                        for nA in range(1, max_n_limit):
                            rem = win[0] - nA*pA['C']
                            if rem <= 0: continue
                            nB = int(np.ceil(rem / pB['C']))
                            if nA + nB <= max_n_limit:
                                tot_c = nA*pA['C'] + nB*pB['C']
                                if win[0] <= tot_c <= win[1]:
                                    sols.append({'Vol': nA*pA['V']+nB*pB['V'], 'Cap': tot_c, 'Type': '2p', 'BOM': f"{nA}x {pA['K']} + {nB}x {pB['K']}", 'Cfg': f"{nA}x {pA['P']} + {nB}x {pB['P']}"})

            # 3p logic
            if self.var_types.get() >= 3:
                # Limit outer loops for 3p to keep it sane (N^3 is huge)
                # We only check the very top density candidates for 3p hybrids
                subset = search[:15] 
                
                for pA in subset:
                    current_op += 1
                    report_progress()
                    
                    for pB in subset:
                        if pA['P'] == pB['P']: continue
                        for pC in subset:
                            if pC['P'] in [pA['P'], pB['P']]: continue
                            nA, nB = 1, 1 
                            rem = win[0] - (nA*pA['C'] + nB*pB['C'])
                            if rem > 0:
                                nC = int(np.ceil(rem / pC['C']))
                                if nA+nB+nC <= max_n_limit:
                                    tc = nA*pA['C'] + nB*pB['C'] + nC*pC['C']
                                    if win[0] <= tc <= win[1]:
                                        sols.append({'Vol': nA*pA['V']+nB*pB['V']+nC*pC['V'], 'Cap': tc, 'Type': '3p', 'BOM': f"{nA}x {pA['K']} + {nB}x {pB['K']} + {nC}x {pC['K']}", 'Cfg': f"{nA}x {pA['P']} + {nB}x {pB['P']} + {nC}x {pC['P']}"})

            self.update_ui(sols)
        except Exception as e:
            print(f"Error: {e}")
            self.root.after(0, lambda: self.btn_run.config(state="normal", text="OPTIMIZE BANK"))
            self.root.after(0, lambda: self.progress.grid_remove())  
            self.root.after(0, lambda: self.btn_run.grid())

    def update_ui(self, sols):
        def _upd():
            self.progress.grid_remove()
            self.btn_run.grid()
            
            for i in self.tree.get_children(): self.tree.delete(i)
            if sols:
                df = pd.DataFrame(sols).sort_values(by='Vol').head(50)
                for i, r in enumerate(df.to_dict('records'), 1):
                    self.tree.insert("", "end", values=(i, r['Type'], f"{r['Vol']:.4f}", f"{r['Cap']*1e6:.2f}", r['BOM'], r['Cfg']))
            self.btn_run.config(state="normal", text="OPTIMIZE BANK")
        self.root.after(0, _upd)

if __name__ == "__main__":
    root = tk.Tk()
    app = CapOptimizerApp(root)
    root.mainloop()
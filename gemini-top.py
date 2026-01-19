import pandas as pd
import requests
import json
import io
import time
import os
import datetime
import concurrent.futures
import threading

# --- CONFIGURATION ---
INPUT_FILE = "MurataProdList-MLCCs_InProduction.csv"
CACHE_FILE = "temp_vertical_cache.csv"
FINAL_OUTPUT = "Murata_SideBySide_Master.csv"
FAILURE_REPORT = "FINAL_FAILURES.txt"

BATCH_SIZE = 25
TEST_LIMIT = 0
MAX_WORKERS = 8  # Parallel threads

BASE_URL = "https://ds.murata.com/simserve/characsvdownload"

headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.9',
    'cookie': 'YOUR_FRESH_COOKIES_HERE', # <--- UPDATE THIS
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'referer': 'https://ds.murata.com/simsurfing/mlcc.html?lcid=en-us'
}

# --- GLOBALS ---
file_lock = threading.Lock()
session = requests.Session()
session.headers.update(headers)

def format_time(seconds):
    return str(datetime.timedelta(seconds=int(seconds)))

# --- 1. UNIVERSAL EXTRACTOR (UPGRADED) ---
def extract_flexible_data(csv_text):
    try:
        df = pd.read_csv(io.StringIO(csv_text), header=None, on_bad_lines='skip', low_memory=False)
    except:
        return []

    if df.empty or df.shape[0] < 1: return []

    valid_blocks = []
    part_indices = {}
    row0 = df.iloc[0].astype(str)
    
    # [UPGRADE] Full 54-Type Prefix List so nothing gets ignored
    VALID_PREFIXES = [
        "GRM", "GR3", "GRJ", "GR4", "GR7", "GJM", "GQM", "GJ4", "GMA", "GMD", "GXT", "GRT",
        "GCM", "GC3", "GCJ", "GCQ", "GCD", "GCE", "GCG", "GCH", "GGD",
        "KRM", "KR3", "KR9", "KRT", "KCM", "KC3", "KC9", "KCA",
        "GA2", "GA3", "DK1", "EA1", "EVA", "DE1", "DE2", "DE6", 
        "LLL", "LLF", "LLA", "LLG", "LLC", "NFM", "ZRA", "ZRB", "GGM", "GNM",
        "RDE", "RCE", "RHE", "RHS", "ECAS"
    ]
    IGNORE = ["#In Production", "#c_dcbias", "#capacitance", "#error", "#Specified", "#Obsolete"]
    
    for c in range(df.shape[1]):
        val = row0[c]
        if isinstance(val, str) and val.startswith("#"):
            if any(x in val for x in IGNORE): continue
            if "/" in val and any(char.isdigit() for char in val): continue 
            clean_pn = val.replace("#", "").strip()
            if any(clean_pn.startswith(p) for p in VALID_PREFIXES) or (len(clean_pn)>6 and clean_pn.isalnum()):
                part_indices[c] = clean_pn
            
    sorted_cols = sorted(part_indices.keys())
    for i, start_col in enumerate(sorted_cols):
        part_name = part_indices[start_col]
        end_col = sorted_cols[i+1] if i < len(sorted_cols) - 1 else df.shape[1]
        island = df.iloc[:, start_col:end_col]
        
        # Deep Scan (30 rows)
        dc_coords = None
        for r in range(min(30, len(island))):
            for c_local in range(island.shape[1]):
                cell = str(island.iat[r, c_local])
                if "DC Bias" in cell and "Capacitance" not in cell:
                    dc_coords = (r, c_local)
                    break
            if dc_coords: break
            
        if dc_coords:
            r_st, c_v = dc_coords
            c_c = c_v + 1
            if c_c < island.shape[1]:
                v_data = pd.to_numeric(island.iloc[r_st+1:, c_v], errors='coerce')
                c_data = pd.to_numeric(island.iloc[r_st+1:, c_c], errors='coerce')
                mask = v_data.notna() & c_data.notna()
                if mask.sum() > 2:
                    valid_blocks.append(pd.DataFrame({
                        'Part_Number': part_name, 'DC_Bias_V': v_data[mask], 'Capacitance_F': c_data[mask]
                    }))
    return valid_blocks

# --- 2. WORKER FUNCTION (UPGRADED) ---
def process_batch_task(batch, config):
    # [UPGRADE] Support 'status' parameter (default to 'B')
    status = config.get('status', 'B')
    
    req_list = [{
         "partnumber": p, 
         "chara_type": "c_dcbias_capacitance",
         "parameter": {"supply_status": status, "graph_set_y_name": "", "dc": "0", "tc": config['tc'], "ac": config['ac']}
    } for p in batch]

    try:
        params = { 'ReqType': 'characsv', 'MIMEType': 'application/octet-stream', 'ReqChara': json.dumps(req_list) }
        # Slightly longer timeout for stability
        response = session.get(BASE_URL, params=params, timeout=20) 
        blocks = extract_flexible_data(response.text)
        
        if blocks:
            df_batch = pd.concat(blocks, ignore_index=True)
            with file_lock:
                need_header = not os.path.exists(CACHE_FILE)
                df_batch.to_csv(CACHE_FILE, mode='a', header=need_header, index=False)
            
            succeeded = df_batch['Part_Number'].unique().tolist()
            return [p for p in batch if p not in succeeded]
        else:
            return batch 
    except:
        return batch

# --- 3. PASS MANAGER ---
def run_pass(pass_name, queue, config):
    if not queue: return []
    print(f"\n--- {pass_name} ({len(queue)} parts) ---")
    
    batches = [queue[i:i + BATCH_SIZE] for i in range(0, len(queue), BATCH_SIZE)]
    failures = []
    
    start_time = time.time()
    total = len(batches)
    completed = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_batch = {executor.submit(process_batch_task, b, config): b for b in batches}
        
        for future in concurrent.futures.as_completed(future_to_batch):
            failures.extend(future.result())
            completed += 1
            if completed % 5 == 0 or completed == total:
                elapsed = time.time() - start_time
                rate = (completed * BATCH_SIZE) / elapsed
                print(f"\rProgress: {completed}/{total} batches | Rate: {rate:.1f} parts/sec", end="")
    
    print(f"\nPass Complete. {len(failures)} failures.")
    return failures

# --- 4. MAIN (UPGRADED SNIPER) ---
def main():
    if os.path.exists(CACHE_FILE): os.remove(CACHE_FILE)
    if os.path.exists(FAILURE_REPORT): os.remove(FAILURE_REPORT)

    print("Loading part list...")
    df_input = pd.read_csv(INPUT_FILE)
    all_parts = df_input['part_number'].unique().tolist()
    if TEST_LIMIT: all_parts = all_parts[:TEST_LIMIT]
    
    total_start = time.time()

    # Pass 1: High Volt (Fast)
    fails = run_pass("PASS 1 (25C/1.0V)", all_parts, {"tc": "25", "ac": "1.0"})
    
    # Pass 2: Safety (Fast)
    if fails: fails = run_pass("PASS 2 (20C/1.0V)", fails, {"tc": "20", "ac": "1.0"})
        
    # Pass 3: Low Volt (Fast)
    if fails: fails = run_pass("PASS 3 (25C/0.5V)", fails, {"tc": "25", "ac": "0.5"})

    # Pass 4: NUCLEAR SNIPER MODE [UPGRADED]
    if fails:
        print(f"\n--- PASS 4: Nuclear Sniper ({len(fails)} parts) ---")
        print("Cycling Status A/B/C and Voltages 0.05V - 1.0V...")
        
        final_losers = []
        
        # [UPGRADE] The "God List" of configs
        nuclear_configs = [
            {"status": "B", "tc": "25", "ac": "0.1"},  # High Cap (330uF) fix
            {"status": "B", "tc": "25", "ac": "0.05"}, # Extreme Cap fix
            {"status": "C", "tc": "20", "ac": "0.5"},  # Legacy Status "C" fix
            {"status": "C", "tc": "25", "ac": "0.5"},
            {"status": "A", "tc": "25", "ac": "1.0"},  # Legacy Status "A" fix
            {"status": "B", "tc": "25", "ac": "1.0"},  # Standard Retry
        ]
        
        # Sequential Processing for stability on hard parts
        for p in fails:
            found = False
            for cfg in nuclear_configs:
                # Reuse worker logic for single item list
                res = process_batch_task([p], cfg)
                if not res: # Empty list = Success
                    found = True
                    print(".", end="", flush=True)
                    break
            
            if not found:
                print("x", end="", flush=True)
                final_losers.append(p)

        if final_losers:
            print(f"\n\n[!] {len(final_losers)} parts are genuinely dead.")
            with open(FAILURE_REPORT, "w") as f:
                f.write("\n".join(final_losers))
        else:
            print("\n\n[+] 100% Recovery!")

    # Finalize
    print("\n--- Finalizing: Side-by-Side Matrix ---")
    if os.path.exists(CACHE_FILE):
        print("Reading cache...")
        df_long = pd.read_csv(CACHE_FILE)
        
        print("Pivoting...")
        part_dfs = []
        grouped = df_long.groupby('Part_Number')
        
        for part, data in grouped:
            clean_part = data[['DC_Bias_V', 'Capacitance_F']].reset_index(drop=True)
            clean_part.columns = [f"{part}_V", f"{part}_C"]
            part_dfs.append(clean_part)
        
        if part_dfs:
            df_final = pd.concat(part_dfs, axis=1)
            df_final.to_csv(FINAL_OUTPUT, index=False)
            print(f"SUCCESS! Total Time: {format_time(time.time() - total_start)}")
            print(f"File: {FINAL_OUTPUT}")
            print(f"Total Caps Saved: {df_final.shape[1]//2}")
        else:
            print("Error: Cache existed but contained no valid data?")
    else:
        print("No data downloaded.")

if __name__ == "__main__":
    main()
import pandas as pd
import requests
import json
import io
import time
import os
import re
import datetime
import concurrent.futures
import threading

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(BASE_DIR, "..", "..")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# INPUTS
_candidates = [f for f in os.listdir(DATA_DIR) if f.startswith("MLCC_Murata_") and f.endswith(".csv")]
INPUT_FILE = os.path.join(DATA_DIR, max(_candidates)) if _candidates else None

# OUTPUTS
CACHE_FILE = os.path.join(DATA_DIR, "cache", "temp_cache_Murata_Cap_DC_Bias_Characteristics.csv")
FINAL_OUTPUT = os.path.join(DATA_DIR, "Murata_Cap_DC_Bias_Characteristics.csv")
FAILURE_REPORT = os.path.join(DATA_DIR, "logs", "FAILURES_Murata_Cap_DC_Bias_Characteristics.txt")

# TUNING
BATCH_SIZE = 25 
MAX_WORKERS = 8  

# API ENDPOINT
BASE_URL = "https://ds.murata.com/simserve/characsvdownload"

headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.9',
    # --- UPDATE COOKIE HERE ---
    'cookie': 'YOUR_FRESH_COOKIES_HERE', 
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'referer': 'https://ds.murata.com/simsurfing/mlcc.html?lcid=en-us'
}

# --- GLOBALS ---
file_lock = threading.Lock()
session = requests.Session()
session.headers.update(headers)

def format_time(seconds):
    return str(datetime.timedelta(seconds=int(seconds)))

# --- 1. DATA PARSING LOGIC ---
def parse_ac_voltage(condition_str):
    if pd.isna(condition_str): return "1.0"
    match = re.search(r'([\d\.]+)\s*Vrms', str(condition_str), re.IGNORECASE)
    if match: return match.group(1)
    match_simple = re.search(r'([\d\.]+)\s*V', str(condition_str), re.IGNORECASE)
    if match_simple: return match_simple.group(1)
    return "1.0"

def clean_temp(val):
    if pd.isna(val): return "25"
    try:
        return str(int(float(val)))
    except:
        return "25"

# --- 2. UNIVERSAL EXTRACTOR (FIXED: No Prefixes) ---
def extract_flexible_data(csv_text):
    try:
        # Check for HTML response (Cookie Expired)
        if "<!DOCTYPE html" in csv_text[:100] or "<html" in csv_text[:100]:
            return "COOKIE_ERROR"

        df = pd.read_csv(io.StringIO(csv_text), header=None, on_bad_lines='skip', low_memory=False)
    except:
        return []

    if df.empty or df.shape[0] < 1: return []

    valid_blocks = []
    part_indices = {}
    row0 = df.iloc[0].astype(str)
    
    # [FIX] No more "VALID_PREFIXES". We trust the API.
    # We just look for the "#" marker that Murata uses for headers.
    for c in range(df.shape[1]):
        val = row0[c]
        if isinstance(val, str) and val.startswith("#"):
            clean_pn = val.replace("#", "").strip()
            # If it's not a known junk header, assume it's a part number
            if clean_pn not in ["In Production", "c_dcbias", "capacitance", "error", "Specified", "Obsolete"]:
                part_indices[c] = clean_pn
            
    sorted_cols = sorted(part_indices.keys())
    for i, start_col in enumerate(sorted_cols):
        part_name = part_indices[start_col]
        end_col = sorted_cols[i+1] if i < len(sorted_cols) - 1 else df.shape[1]
        island = df.iloc[:, start_col:end_col]
        
        # Scan for Data Header (DC Bias)
        dc_coords = None
        for r in range(min(30, len(island))):
            for c_local in range(island.shape[1]):
                cell = str(island.iat[r, c_local])
                # We look for Voltage data
                if "DC Bias" in cell and "Capacitance" not in cell:
                    dc_coords = (r, c_local)
                    break
            if dc_coords: break
            
        if dc_coords:
            r_st, c_v = dc_coords
            c_c = c_v + 1
            if c_c < island.shape[1]:
                # Extract Data Columns
                v_data = pd.to_numeric(island.iloc[r_st+1:, c_v], errors='coerce')
                c_data = pd.to_numeric(island.iloc[r_st+1:, c_c], errors='coerce')
                
                # Only keep rows where both exist
                mask = v_data.notna() & c_data.notna()
                if mask.sum() > 2:
                    valid_blocks.append(pd.DataFrame({
                        'Part_Number': part_name, 
                        'DC_Bias_V': v_data[mask], 
                        'Capacitance_F': c_data[mask]
                    }))
    return valid_blocks

# --- 3. WORKER FUNCTION ---
def process_smart_batch(task_batch):
    req_list = []
    for t in task_batch:
        req_list.append({
             "partnumber": t['pn'], 
             "chara_type": "c_dcbias_capacitance",
             "parameter": {
                 "supply_status": t['status'], 
                 "graph_set_y_name": "", 
                 "dc": "0", 
                 "tc": t['tc'], 
                 "ac": t['ac']
             }
        })

    try:
        params = { 
            'ReqType': 'characsv', 
            'MIMEType': 'application/octet-stream', 
            'ReqChara': json.dumps(req_list) 
        }
        
        response = session.get(BASE_URL, params=params, timeout=25) 
        blocks = extract_flexible_data(response.text)
        
        # [FIX] Explicit Cookie Check
        if blocks == "COOKIE_ERROR":
            print("\n[!] CRITICAL: Your Cookie has expired. Murata is redirecting to login.")
            os._exit(1) # Stop script immediately

        if blocks:
            df_batch = pd.concat(blocks, ignore_index=True)
            with file_lock:
                need_header = not os.path.exists(CACHE_FILE)
                df_batch.to_csv(CACHE_FILE, mode='a', header=need_header, index=False)
            
            succeeded_parts = df_batch['Part_Number'].unique().tolist()
            return [t['pn'] for t in task_batch if t['pn'] not in succeeded_parts]
        else:
            return [t['pn'] for t in task_batch]
    except Exception as e:
        return [t['pn'] for t in task_batch]

# --- 4. MAIN ---
def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: Input file not found: {INPUT_FILE}")
        return

    # Clean previous run
    if os.path.exists(CACHE_FILE): os.remove(CACHE_FILE)
    if os.path.exists(FAILURE_REPORT): os.remove(FAILURE_REPORT)

    print(f"📂 Loading Input: {INPUT_FILE}")
    # [FIX] Added low_memory=False to silence warning
    df_input = pd.read_csv(INPUT_FILE, low_memory=False)
    
    print("🧠 Analyzing Part Metadata...")
    tasks = []
    
    for _, row in df_input.iterrows():
        status_raw = str(row.get('production_status_en-us', 'B')).strip().upper()
        # [FIX] As requested: Ignore N and C
        if status_raw == 'C' or status_raw == 'N': continue
            
        tc_val = clean_temp(row.get('base-temp', '25'))
        ac_val = parse_ac_voltage(row.get('Condition', ''))
        part_num = str(row.get('part_number', ''))
        
        if not part_num or part_num == 'nan': continue

        tasks.append({
            "pn": part_num,
            "status": status_raw if status_raw in ['B'] else 'B',
            "tc": tc_val,
            "ac": ac_val
        })

    print(f"🎯 identified {len(tasks)} valid parts for scraping.")
    
    batches = [tasks[i:i + BATCH_SIZE] for i in range(0, len(tasks), BATCH_SIZE)]
    failures = []
    
    print(f"🚀 Starting Scraper with {MAX_WORKERS} threads...")
    start_time = time.time()
    total_batches = len(batches)
    completed_batches = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_batch = {executor.submit(process_smart_batch, b): b for b in batches}
        
        for future in concurrent.futures.as_completed(future_to_batch):
            failures.extend(future.result())
            completed_batches += 1
            
            elapsed = time.time() - start_time
            rate = (completed_batches * BATCH_SIZE) / elapsed
            print(f"\rProgress: {completed_batches}/{total_batches} batches | Rate: {rate:.1f} parts/sec", end="")

    total_duration = time.time() - start_time
    print(f"\n\n🏁 Scrape Complete in {format_time(total_duration)}.")
    
    if failures:
        print(f"⚠️ {len(failures)} parts failed to download.")
        with open(FAILURE_REPORT, "w") as f:
            f.write("\n".join(failures))
            
    # --- PIVOT & SAVE ---
    if os.path.exists(CACHE_FILE):
        print("pandas pivoting... (this may take a moment)")
        df_long = pd.read_csv(CACHE_FILE)
        
        part_dfs = []
        grouped = df_long.groupby('Part_Number')
        
        for part, data in grouped:
            clean_part = data[['DC_Bias_V', 'Capacitance_F']].reset_index(drop=True)
            clean_part.columns = [f"{part}_V", f"{part}_C"]
            part_dfs.append(clean_part)
        
        if part_dfs:
            df_final = pd.concat(part_dfs, axis=1)
            df_final.to_csv(FINAL_OUTPUT, index=False)
            print(f"✅ Success! Master Database Saved: {FINAL_OUTPUT}")
            print(f"📊 Total Capacitors: {len(part_dfs)}")
    else:
        print("❌ No data was downloaded.")

if __name__ == "__main__":
    main()
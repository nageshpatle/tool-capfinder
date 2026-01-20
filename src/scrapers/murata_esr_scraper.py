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
CACHE_FILE = os.path.join(DATA_DIR, "cache", "temp_cache_Murata_ESR_Frequency_Characteristics.csv")
FINAL_OUTPUT = os.path.join(DATA_DIR, "Murata_ESR_Frequency_Characteristics.csv")
FAILURE_REPORT = os.path.join(DATA_DIR, "logs", "FAILURES_Murata_ESR_Frequency_Characteristics.txt")

# TUNING
BATCH_SIZE = 20 
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

def clean_temp(val):
    if pd.isna(val): return "25"
    try:
        return str(int(float(val)))
    except:
        return "25"

# --- 1. DATA EXTRACTION LOGIC ---
def extract_flexible_data(csv_text):
    try:
        # Check for HTML (Cookie Expired)
        if "<!DOCTYPE html" in csv_text[:100] or "<html" in csv_text[:100]:
            return "COOKIE_ERROR"
        
        # Check for API Error Messages
        if "No Data" in csv_text or "Error" in csv_text[:50]:
            return []

        df = pd.read_csv(io.StringIO(csv_text), header=None, on_bad_lines='skip', low_memory=False)
    except:
        return []

    if df.empty or df.shape[0] < 1: return []

    valid_blocks = []
    part_indices = {}
    row0 = df.iloc[0].astype(str)
    
    # Identify Parts by Header "#"
    for c in range(df.shape[1]):
        val = row0[c]
        if isinstance(val, str) and val.startswith("#"):
            clean_pn = val.replace("#", "").strip()
            # Ignore standard Murata headers
            if clean_pn not in ["In Production", "r", "capacitance", "error", "Specified", "Obsolete", "Frequency"]:
                part_indices[c] = clean_pn
            
    sorted_cols = sorted(part_indices.keys())
    for i, start_col in enumerate(sorted_cols):
        part_name = part_indices[start_col]
        end_col = sorted_cols[i+1] if i < len(sorted_cols) - 1 else df.shape[1]
        island = df.iloc[:, start_col:end_col]
        
        # Scan for "Frequency" header
        freq_coords = None
        for r in range(min(30, len(island))):
            for c_local in range(island.shape[1]):
                cell = str(island.iat[r, c_local])
                if "Frequency" in cell:
                    freq_coords = (r, c_local)
                    break
            if freq_coords: break
            
        if freq_coords:
            r_st, c_freq = freq_coords
            
            # Find Resistance Column (ESR)
            # Usually: Freq | Impedance | Resistance | ...
            # We look specifically for "Resistance" to map it correctly
            c_res = -1
            for c_scan in range(island.shape[1]):
                 if "Resistance" in str(island.iat[r_st, c_scan]):
                     c_res = c_scan
                     break
            
            # Fallback: Column Index + 2 is standard for Murata Series Mode
            if c_res == -1 and (c_freq + 2) < island.shape[1]:
                c_res = c_freq + 2

            if c_res != -1:
                f_data = pd.to_numeric(island.iloc[r_st+1:, c_freq], errors='coerce')
                r_data = pd.to_numeric(island.iloc[r_st+1:, c_res], errors='coerce')
                
                # Keep rows where both Frequency and ESR exist
                mask = f_data.notna() & r_data.notna()
                if mask.sum() > 2:
                    df_part = pd.DataFrame({
                        'Part_Number': part_name, 
                        'Frequency_Hz': f_data[mask], 
                        'ESR_Ohm': r_data[mask]
                    })
                    # [OPTIMIZATION] Decimate by 2 (User Request: < 100MB)
                    valid_blocks.append(df_part.iloc[::2])
    return valid_blocks

# --- 2. WORKER FUNCTION (EXACT MATCH TO YOUR URL) ---
DEBUG_ONCE = False
def process_esr_batch(task_batch):
    global DEBUG_ONCE
    req_list = []
    for t in task_batch:
        req_list.append({
             "partnumber": t['pn'], 
             "chara_type": "r", 
             "parameter": {
                 "form": "series",       # Matches your URL
                 "modeltype": "precise", # Matches your URL
                 "supply_status": t['status'], 
                 "graph_set_y_name": "", # Matches your URL (Empty String)
                 "dc": "0", 
                 "tc": t['tc'], 
                 "ac": "0.01"            # Matches your URL
             }
        })

    try:
        # [FIX] Minify JSON (no spaces) to match verified URL
        json_payload = json.dumps(req_list, separators=(',', ':'))
        
        params = { 
            'ReqType': 'characsv', 
            'MIMEType': 'application/octet-stream', 
            'ReqChara': json_payload 
        }
        
        response = session.get(BASE_URL, params=params, timeout=30) 
        blocks = extract_flexible_data(response.text)
        
        if blocks == "COOKIE_ERROR":
            print("\n[!] CRITICAL: Your Cookie has expired.")
            os._exit(1)

        if blocks:
            df_batch = pd.concat(blocks, ignore_index=True)
            with file_lock:
                need_header = not os.path.exists(CACHE_FILE)
                df_batch.to_csv(CACHE_FILE, mode='a', header=need_header, index=False, float_format='%.5g')
            
            succeeded_parts = df_batch['Part_Number'].unique().tolist()
            return [t['pn'] for t in task_batch if t['pn'] not in succeeded_parts]
        else:
            # [DEBUG] Print rejection reason once
            if not DEBUG_ONCE:
                print(f"\n[DEBUG] First Failure Response (Code {response.status_code}, Reason: {response.reason}):")
                print(f"[DEBUG] Response Bytes: {len(response.content)}")
                print(f"[DEBUG] Sent Payload: {json_payload[:200]}...")
                DEBUG_ONCE = True
            return [t['pn'] for t in task_batch]
    except Exception as e:
        if not DEBUG_ONCE:
             print(f"\n[DEBUG] Exception: {e}")
             DEBUG_ONCE = True
        return [t['pn'] for t in task_batch]

# --- 3. MAIN ---
def main():
    if not INPUT_FILE or not os.path.exists(INPUT_FILE):
        print(f"❌ Error: Input file not found in {DATA_DIR}")
        return

    # Clean previous run
    if os.path.exists(CACHE_FILE): os.remove(CACHE_FILE)
    if os.path.exists(FAILURE_REPORT): os.remove(FAILURE_REPORT)

    print(f"📂 Loading Input: {INPUT_FILE}")
    df_input = pd.read_csv(INPUT_FILE, low_memory=False)
    
    print("🧠 Analyzing Part Metadata for ESR...")
    tasks = []
    
    for _, row in df_input.iterrows():
        status_raw = str(row.get('production_status_en-us', 'B')).strip().upper()
        # Exclude 'C' and 'N' as requested
        if status_raw == 'C' or status_raw == 'N': continue
            
        tc_val = clean_temp(row.get('base-temp', '25'))
        part_num = str(row.get('part_number', ''))
        
        if not part_num or part_num == 'nan': continue

        tasks.append({
            "pn": part_num,
            "status": status_raw if status_raw in ['B'] else 'B',
            "tc": tc_val
        })

    print(f"🎯 identified {len(tasks)} valid parts for ESR scraping.")
    
    batches = [tasks[i:i + BATCH_SIZE] for i in range(0, len(tasks), BATCH_SIZE)]
    failures = []
    
    print(f"🚀 Starting ESR Scraper with {MAX_WORKERS} threads...")
    start_time = time.time()
    total_batches = len(batches)
    completed_batches = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_batch = {executor.submit(process_esr_batch, b): b for b in batches}
        
        for future in concurrent.futures.as_completed(future_to_batch):
            failures.extend(future.result())
            completed_batches += 1
            
            elapsed = time.time() - start_time
            if elapsed > 0:
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
            # Sort by frequency and remove duplicates
            data = data.drop_duplicates(subset=['Frequency_Hz']).sort_values('Frequency_Hz')
            clean_part = data[['Frequency_Hz', 'ESR_Ohm']].reset_index(drop=True)
            clean_part.columns = [f"{part}_Freq", f"{part}_ESR"]
            part_dfs.append(clean_part)
        
        if part_dfs:
            df_final = pd.concat(part_dfs, axis=1)
            df_final.to_csv(FINAL_OUTPUT, index=False, float_format='%.5g')
            print(f"✅ Success! Master ESR Database Saved: {FINAL_OUTPUT}")
            print(f"📊 Total Capacitors: {len(part_dfs)}")
    else:
        print("❌ No data was downloaded.")

if __name__ == "__main__":
    main()
import time
import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
TARGET_URL = "https://ds.murata.co.jp/simsurfing/mlcc.html"
OUTPUT_FOLDER = "data"
OUTPUT_FILENAME = f"MLCC_Murata_{time.strftime('%Y%m%d')}.csv"

# UPDATED ORDER: Added esl, esr, impedance, effective_capacitance
DESIRED_ORDER = [
    "dataindex", "part_number", "spec_application", "temprise", "temperature_compensating",
    "high_permittivity", "production_status_ja", "production_status_en-us", "production_status_zh-cn",
    "capacitance_pu", "capacitance_p", "capacitance_u", "capacitance_sort", "rvol",
    "rvol_ac_list", "tcc", "LWSize_mm_inch", "size_thickness_max", "tolerance", "Type",
    "caution", "publicstandard", "SRF", "esr", "esl", "impedance", "effective_capacitance", # <--- MOVED HERE
    "deltaX", "Gdx", "base-temp", "opetemp-min", "opetemp-max", 
    "flag_cdcbais_button", "flag_ctemp_button", "flag_temprise_button", "flag_cac_vlotage_button", 
    "A1", "B1", "C1", "E1", "Condition", "TC_Condition",
    "list_cdc_bias_ac_vrms", "list_ctemp_ac_vrms", "CCR_Gdx", "Category", "file_information",
    "use_application", "flag_rated_vol_reduction", "l_size_value", "w_size_value",
    "supplystatus", "supplystatus_sort", "boundindex", "uniqueid", "visibleindex"
]

def get_murata_data():
    print("🚀 Launching Robot Browser...")
    
    options = webdriver.ChromeOptions()
    options.add_argument("--headless") # Keep off for debugging
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        print(f"🔗 Navigating to {TARGET_URL}...")
        driver.get(TARGET_URL)

        # --- STEP 1: LICENSE CHECK ---
        try:
            # Short wait - click if visible, skip if not
            agree_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'AGREE') or contains(text(), 'Agree')]"))
            )
            agree_btn.click()
            print("✅ Clicked 'AGREE'.")
            time.sleep(2) 
        except:
            pass

        # --- STEP 2: FRAME SCANNER ---
        print("🔎 Scanning frames for the data grid...")
        
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        search_contexts = [None] + list(range(len(frames)))
        extracted_data = None

        for context in search_contexts:
            try:
                driver.switch_to.default_content()
                if context is not None:
                    driver.switch_to.frame(frames[context])
                    frame_name = f"Iframe #{context}"
                else:
                    frame_name = "Main Page"

                # Check for Grid
                check_script = """
                if (typeof jQuery !== 'undefined' && $('.jqx-grid').length > 0) {
                    return "FOUND";
                }
                return "NOPE";
                """
                try:
                    result = driver.execute_script(check_script)
                except:
                    result = "ERROR"

                if result == "FOUND":
                    print(f"🎉 JACKPOT! Data found in {frame_name}. Extracting...")
                    
                    # EXTRACT ROWS
                    extraction_script = """
                    var rows = $('.jqx-grid').first().jqxGrid('getrows');
                    return rows;
                    """
                    extracted_data = driver.execute_script(extraction_script)
                    break 
                else:
                    pass

            except Exception:
                pass

        # --- STEP 3: PROCESS & SAVE ---
        if extracted_data:
            print(f"✅ Extracted {len(extracted_data)} parts. Processing...")
            
            df = pd.DataFrame(extracted_data)
            
            # 1. Clean System Columns
            clean_cols = [c for c in df.columns if not str(c).startswith('uid') and not str(c).startswith('_')]
            df = df[clean_cols]

            # 2. STRICT REORDERING
            # Sort columns according to your DESIRED_ORDER list
            final_columns = [col for col in DESIRED_ORDER if col in df.columns]
            
            # Catch any new/unknown columns and append them to the end
            existing_cols_set = set(final_columns)
            extra_cols = [col for col in df.columns if col not in existing_cols_set]
            
            # Combine
            df = df[final_columns + extra_cols]
            
            print(f"✨ Organized columns: Found {len(final_columns)} matches from your list.")

            # 3. Save
            os.makedirs(OUTPUT_FOLDER, exist_ok=True)
            output_path = os.path.join(OUTPUT_FOLDER, OUTPUT_FILENAME)
            
            df.to_csv(output_path, index=False)
            print(f"💾 SUCCESS: Data saved to '{output_path}'")
            
        else:
            print("❌ Failed to find the data grid.")

    except Exception as e:
        print(f"❌ Global Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    get_murata_data()
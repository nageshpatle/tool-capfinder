
import pandas as pd
import numpy as np
import re
import os

# Create a dummy large CSV with tricky values
data = {
    'MfrPartName': [f'Part_{i}' for i in range(5000)],
    'Capacitance': ['10uF', '100nF', '10µF', '100pF', 'NaN', 'garbage', ''] * 714 + ['1uF'] * 2,
    'VoltageRatedDC': [25, 50, 6.3, 10, 100] * 1000,
    'MaxTemp_Val': [85, 125] * 2500,
    'Package': ['0402', '0603'] * 2500,
    'SRF_MHz': [100.0] * 5000,
    'Volume_mm3': [1.0] * 5000,
    'MaxThickness_mm': [1.0] * 5000
}
df = pd.DataFrame(data)

def parse_cap(x):
    s = str(x).lower().strip()
    if 'µ' in s or 'u' in s: mult = 1e-6
    elif 'n' in s: mult = 1e-9
    elif 'p' in s: mult = 1e-12
    elif 'm' in s: mult = 1e-3
    else: mult = 1.0 
    val = re.sub(r'[^\d.]', '', s)
    if not val: return 0.0
    try: return float(val) * mult
    except: return 0.0

print(f"Initial rows: {len(df)}")
df['Capacitance_F'] = df['Capacitance'].apply(parse_cap)
print("Parsing done.")
print(df[['Capacitance', 'Capacitance_F']].head(10))
print(f"Empty/Zero count: {len(df[df['Capacitance_F'] == 0])}")

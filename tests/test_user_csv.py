import sys
import os
import numpy as np
import pandas as pd

src_dir = os.path.join(r"c:\Users\berna\Documents\Coding-Projects\Python\Calcium Imageing APP", "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from calcium_peak_analyzer.core.calcium_processor import CalciumSignalProcessor

# Test improved parse_csv logic
def improved_parse_csv(filepath_or_buffer):
    try:
        df = pd.read_csv(filepath_or_buffer, sep=None, engine='python')
    except Exception:
        if hasattr(filepath_or_buffer, 'seek'):
            filepath_or_buffer.seek(0)
        df = pd.read_csv(filepath_or_buffer)
        
    df.columns = [str(c).strip() for c in df.columns]
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_cols:
        raise ValueError("No numeric data columns found in the CSV file.")
        
    time_keywords = ['time', 'frame', 'slice', 'sec', 'second', 'timestamp', 'index', 't_ms', 't_s']
    time_col = None
    for col in numeric_cols:
        c_clean = col.lower().replace('_', ' ').replace('-', ' ').strip()
        words = c_clean.split()
        if any(kw in c_clean for kw in time_keywords) or (len(words) == 1 and words[0] == 't'):
            time_col = col
            break
            
    signal_cols = [c for c in numeric_cols if c != time_col]
    if not signal_cols:
        if len(numeric_cols) > 1:
            time_col = numeric_cols[0]
            signal_cols = numeric_cols[1:]
        else:
            signal_cols = numeric_cols
            time_col = None
            
    return df, time_col, signal_cols

temp_csv_path = r"c:\Users\berna\Documents\Coding-Projects\Python\Calcium Imageing APP\scratch\test_user_data.csv"
df, time_col, signal_cols = improved_parse_csv(temp_csv_path)

print(f"Detected Time Column: '{time_col}'")
print(f"Detected Signal Columns: {signal_cols}")

y_raw = df[signal_cols[0]].values.astype(float)
b = CalciumSignalProcessor.compute_baseline(y_raw, method="Rolling Percentile", window_pts=100)
dff0 = CalciumSignalProcessor.compute_dff0(y_raw, b)

res_dff = CalciumSignalProcessor.detect_peaks(dff0, 1.0, method="Hybrid (Smooth + Refine)", prominence=0.03, min_distance_pts=30)
metrics = CalciumSignalProcessor.extract_peak_metrics(res_dff["t"], y_raw, res_dff["y_smooth"], b, dff0, res_dff["peaks"], 1.0)
stats = CalciumSignalProcessor.compute_global_statistics(metrics, len(y_raw), 1.0)

print(f"\n--- Results on '{signal_cols[0]}' ---")
print(f"Total Peaks Detected: {stats['Total Peaks']}")
print(f"Mean Amplitude (dF/F0): {stats['Mean Amplitude (dF/F0)']}")
print(f"Mean Rise Time T10-90 (ms): {stats['Mean Rise Time T10-90 (ms)']}")
print(f"Mean Decay Tau (ms): {stats['Mean Decay Tau (ms)']}")
print("First 5 Peaks:")
print(metrics[["Peak_ID", "Time (ms)", "Peak Raw Intensity", "Baseline F0", "dF/F0 Peak"]].head(5))

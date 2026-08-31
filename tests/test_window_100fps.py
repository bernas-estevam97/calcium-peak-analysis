import sys
import os
import numpy as np
import pandas as pd

src_dir = os.path.join(r"c:\Users\berna\Documents\Coding-Projects\Python\Calcium Imageing APP", "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from calcium_peak_analyzer.core.calcium_processor import CalciumSignalProcessor

temp_csv_path = r"c:\Users\berna\Documents\Coding-Projects\Python\Calcium Imageing APP\scratch\test_user_data.csv"
df = pd.read_csv(temp_csv_path, sep=";")

y_raw = df["Average_Intensity"].values.astype(float)
dt = 10.0 # 100 FPS = 10 ms per frame

print("--- Testing Baseline Windows for 100 FPS (10 ms/frame) ---")
for win in [100, 200, 300, 500]:
    b = CalciumSignalProcessor.compute_baseline(y_raw, method="Rolling Percentile", window_pts=win)
    dff0 = CalciumSignalProcessor.compute_dff0(y_raw, b)
    res = CalciumSignalProcessor.detect_peaks(dff0, dt, method="Hybrid (Smooth + Refine)", prominence=0.03, min_distance_pts=50)
    metrics = CalciumSignalProcessor.extract_peak_metrics(res["t"], y_raw, res["y_smooth"], b, dff0, res["peaks"], dt)
    stats = CalciumSignalProcessor.compute_global_statistics(metrics, len(y_raw), dt)
    
    print(f"\nWindow = {win} frames ({win*dt/1000:.1f} s):")
    print(f"  Total Peaks Detected: {stats['Total Peaks']}")
    print(f"  Mean Amplitude (dF/F0): {stats['Mean Amplitude (dF/F0)']:.4f}")
    print(f"  Mean Rise Time T10-90 (ms): {stats['Mean Rise Time T10-90 (ms)']:.2f} ms")
    print(f"  Mean Decay Tau (ms): {stats['Mean Decay Tau (ms)']:.2f} ms")

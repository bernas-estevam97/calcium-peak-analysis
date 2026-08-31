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
dt = 10.0 # 100 FPS

print("=== SENSITIVITY TEST: Prominence = 0.10 at 100 FPS ===")
for win in [100, 200, 300, 400, 500, 600, 800, 1000]:
    b = CalciumSignalProcessor.compute_baseline(y_raw, method="Rolling Percentile", window_pts=win)
    dff0 = CalciumSignalProcessor.compute_dff0(y_raw, b)
    res = CalciumSignalProcessor.detect_peaks(dff0, dt, method="Hybrid (Smooth + Refine)", prominence=0.10, min_distance_pts=50)
    metrics = CalciumSignalProcessor.extract_peak_metrics(res["t"], y_raw, res["y_smooth"], b, dff0, res["peaks"], dt)
    stats = CalciumSignalProcessor.compute_global_statistics(metrics, len(y_raw), dt)
    
    peak_times = list(np.round(metrics["Time (ms)"].values / 1000.0, 1)) if len(metrics) > 0 else []
    print(f"\nWindow = {win:4d} frames ({win*dt/1000:4.1f} s):")
    print(f"  Total Peaks: {stats['Total Peaks']}")
    print(f"  Peak Times (s): {peak_times}")
    print(f"  Mean Amp (dF/F0): {stats['Mean Amplitude (dF/F0)']:.4f}")
    print(f"  Mean Rise T10-90 (ms): {stats['Mean Rise Time T10-90 (ms)']:.1f}")
    print(f"  Mean Decay Tau (ms): {stats['Mean Decay Tau (ms)']:.1f}")
    print(f"  Mean IEI (ms): {stats['Mean Inter-Event Interval (ms)']:.1f}")
    print(f"  Rhythmicity CV: {stats['Rhythmicity Index (CV of IEI)']:.4f}")

import sys
import os
import numpy as np
import pandas as pd

# Add src dir to path
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from calcium_peak_analyzer.core.calcium_processor import CalciumSignalProcessor

def test_processor():
    dt = 10.0
    n_pts = 1000
    t = np.arange(n_pts) * dt
    
    baseline_true = 100.0
    y_raw = np.full(n_pts, baseline_true)
    
    np.random.seed(42)
    y_raw += np.random.normal(0, 0.5, n_pts)
    
    def add_peak(center_idx, amp=50.0):
        for i in range(-10, 100):
            idx = center_idx + i
            if 0 <= idx < n_pts:
                if i < 0:
                    y_raw[idx] += amp * (1.0 + i / 10.0)
                else:
                    y_raw[idx] += amp * np.exp(- (i * dt) / 150.0)

    add_peak(200, amp=50.0)
    add_peak(500, amp=40.0)
    add_peak(800, amp=60.0)
    
    b = CalciumSignalProcessor.compute_baseline(y_raw, method="Rolling Percentile", window_pts=100, quantile=0.15)
    dff0 = CalciumSignalProcessor.compute_dff0(y_raw, b)
    results = CalciumSignalProcessor.detect_peaks(y_raw, dt, method="Hybrid (Smooth + Refine)",
                                                   prominence=10.0, min_distance_pts=100, smooth_window_pts=11)
    peaks = results["peaks"]
    
    df_metrics = CalciumSignalProcessor.extract_peak_metrics(t, y_raw, results["y_smooth"], b, dff0, peaks, dt)
    print("\n--- Per-Peak Metrics Dataframe ---")
    print(df_metrics[["Peak_ID", "Time (ms)", "Peak Raw Intensity", "dF/F0 Peak", "Rise Time T10-90 (ms)", "Decay Time T50 (ms)", "Decay Tau (ms)", "AUC (dF/F0 * s)"]])
    
    for idx, row in df_metrics.iterrows():
        print(f"Peak {row['Peak_ID']}: Rise T10-90={row['Rise Time T10-90 (ms)']:.2f}ms, Decay T50={row['Decay Time T50 (ms)']:.2f}ms, Decay Tau={row['Decay Tau (ms)']:.2f}ms")
        assert pd.notna(row["Rise Time T10-90 (ms)"]), f"Rise time NaN for peak {idx}"

    global_stats = CalciumSignalProcessor.compute_global_statistics(df_metrics, len(y_raw), dt)
    print("\n--- Global Statistics ---")
    for k, v in global_stats.items():
        print(f"  {k}: {v}")
        
    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_processor()

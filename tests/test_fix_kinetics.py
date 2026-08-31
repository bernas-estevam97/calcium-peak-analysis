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
t_frames = df["Time_(Frames)"].values.astype(float)
dt = 1.0 # 1 ms per frame (or frame time)

b = CalciumSignalProcessor.compute_baseline(y_raw, method="Rolling Percentile", window_pts=100)
dff0 = CalciumSignalProcessor.compute_dff0(y_raw, b)

res_dff = CalciumSignalProcessor.detect_peaks(dff0, dt, method="Hybrid (Smooth + Refine)", prominence=0.03, min_distance_pts=30)
peaks = res_dff["peaks"]

def extract_peak_metrics_robust(t, y_raw, baseline, dff0, peaks, dt):
    metrics = []
    n = len(dff0)
    
    for idx, p_idx in enumerate(peaks):
        peak_time = t[p_idx]
        peak_raw_val = y_raw[p_idx]
        peak_dff0_val = dff0[p_idx]
        f0_val = baseline[p_idx]
        
        # Use dff0 for kinetic calculations
        y_kinetic = dff0
        
        # 1. Local onset search before peak
        search_back = max(5, int(2000.0 / dt))
        if idx > 0:
            search_back = min(search_back, p_idx - peaks[idx-1])
        search_start = max(0, p_idx - search_back)
        
        local_onset_idx = search_start + np.argmin(y_kinetic[search_start:p_idx+1])
        local_base_dff0 = y_kinetic[local_onset_idx]
        
        amp_dff0 = peak_dff0_val - local_base_dff0
        if amp_dff0 <= 0:
            amp_dff0 = max(1e-4, peak_dff0_val)
            local_base_dff0 = 0.0

        # 2. Rise Time T10-90
        amp_10 = local_base_dff0 + 0.10 * amp_dff0
        amp_90 = local_base_dff0 + 0.90 * amp_dff0
        
        pre_seg_t = t[local_onset_idx:p_idx+1]
        pre_seg_y = y_kinetic[local_onset_idx:p_idx+1]
        
        t_10 = np.nan
        t_90 = np.nan
        rise_time = np.nan
        max_rise_rate = np.nan
        
        if len(pre_seg_y) >= 2:
            dy_dt = np.diff(pre_seg_y) / (dt / 1000.0)
            max_rise_rate = np.max(dy_dt) if len(dy_dt) > 0 else np.nan
            
            idx_10 = np.where(pre_seg_y >= amp_10)[0]
            if len(idx_10) > 0:
                i = idx_10[0]
                if i > 0:
                    y1, y2 = pre_seg_y[i-1], pre_seg_y[i]
                    t1, t2 = pre_seg_t[i-1], pre_seg_t[i]
                    t_10 = t1 + (amp_10 - y1) * (t2 - t1) / (y2 - y1) if y2 != y1 else t1
                else:
                    t_10 = pre_seg_t[0]
                    
            idx_90 = np.where(pre_seg_y >= amp_90)[0]
            if len(idx_90) > 0:
                i = idx_90[0]
                if i > 0:
                    y1, y2 = pre_seg_y[i-1], pre_seg_y[i]
                    t1, t2 = pre_seg_t[i-1], pre_seg_t[i]
                    t_90 = t1 + (amp_90 - y1) * (t2 - t1) / (y2 - y1) if y2 != y1 else t1
                else:
                    t_90 = pre_seg_t[0]
                    
            if pd.notna(t_10) and pd.notna(t_90) and t_90 >= t_10:
                rise_time = t_90 - t_10

        # 3. Decay Time T50 & Decay Tau
        search_forward = max(10, int(3000.0 / dt))
        if idx < len(peaks) - 1:
            search_forward = min(search_forward, peaks[idx+1] - p_idx)
        search_end = min(n, p_idx + search_forward)
        
        post_seg_t = t[p_idx:search_end]
        post_seg_y = y_kinetic[p_idx:search_end]
        
        amp_50 = local_base_dff0 + 0.50 * amp_dff0
        decay_50_time = np.nan
        tau_decay = np.nan
        
        if len(post_seg_y) >= 2:
            idx_50 = np.where(post_seg_y <= amp_50)[0]
            if len(idx_50) > 0:
                i = idx_50[0]
                if i > 0:
                    y1, y2 = post_seg_y[i-1], post_seg_y[i]
                    t1, t2 = post_seg_t[i-1], post_seg_t[i]
                    t_50 = t1 + (amp_50 - y1) * (t2 - t1) / (y2 - y1) if y2 != y1 else t1
                else:
                    t_50 = post_seg_t[0]
                decay_50_time = t_50 - peak_time

            # Fit single exponential curve
            from scipy.optimize import curve_fit
            try:
                rel_t_sec = (post_seg_t - peak_time) / 1000.0
                def exp_decay(t_sec, A, tau, C):
                    return A * np.exp(-t_sec / np.maximum(tau, 1e-4)) + C
                
                p0 = [amp_dff0, 0.2, local_base_dff0]
                bounds = ([0.01 * amp_dff0, 0.001, -1.0], [3.0 * amp_dff0, 5.0, 1.0])
                popt, _ = curve_fit(exp_decay, rel_t_sec, post_seg_y, p0=p0, bounds=bounds, maxfev=300)
                tau_fit_ms = popt[1] * 1000.0
                # Check if tau fit is valid and within range
                if 1.0 <= tau_fit_ms <= 4900.0:
                    tau_decay = tau_fit_ms
            except Exception:
                pass
                
            # If curve fit failed or was out of bounds, use neurophysiology gold-standard tau = T50 / ln(2)
            if pd.isna(tau_decay) and pd.notna(decay_50_time) and decay_50_time > 0:
                tau_decay = decay_50_time / np.log(2.0)

        # 4. FWHM
        from scipy.signal import peak_widths
        fwhm = np.nan
        try:
            w = peak_widths(y_kinetic, [p_idx], rel_height=0.5)
            if len(w[0]) > 0:
                fwhm = w[0][0] * dt
        except Exception:
            pass

        # 5. AUC
        if local_onset_idx < search_end:
            t_auc = t[local_onset_idx:search_end]
            y_auc = y_kinetic[local_onset_idx:search_end] - local_base_dff0
            y_auc = np.maximum(0, y_auc)
            auc = np.trapezoid(y_auc, t_auc / 1000.0) if hasattr(np, 'trapezoid') else np.trapz(y_auc, t_auc / 1000.0)
        else:
            auc = np.nan

        metrics.append({
            "Peak_ID": idx + 1,
            "Peak Index": p_idx,
            "Time (ms)": peak_time,
            "Time (s)": peak_time / 1000.0,
            "Peak Raw Intensity": peak_raw_val,
            "Baseline F0": f0_val,
            "dF/F0 Peak": peak_dff0_val,
            "Amplitude (dF/F0)": amp_dff0,
            "Rise Time T10-90 (ms)": rise_time,
            "Max Rise Rate (dF/dt)": max_rise_rate,
            "Decay Time T50 (ms)": decay_50_time,
            "Decay Tau (ms)": tau_decay,
            "FWHM (ms)": fwhm,
            "AUC (dF/F0 * s)": auc
        })
        
    return pd.DataFrame(metrics)

m_df = extract_peak_metrics_robust(res_dff["t"], y_raw, b, dff0, peaks, dt)

print(f"\n--- Robust Metrics Result (Total Peaks = {len(m_df)}) ---")
print(f"Rise Time T10-90: mean={m_df['Rise Time T10-90 (ms)'].mean():.3f} ms, non-null count={m_df['Rise Time T10-90 (ms)'].count()}")
print(f"Decay Time T50:   mean={m_df['Decay Time T50 (ms)'].mean():.3f} ms, non-null count={m_df['Decay Time T50 (ms)'].count()}")
print(f"Decay Tau (ms):   mean={m_df['Decay Tau (ms)'].mean():.3f} ms, non-null count={m_df['Decay Tau (ms)'].count()}")
print(f"AUC (dF/F0 * s):  mean={m_df['AUC (dF/F0 * s)'].mean():.4f}, non-null count={m_df['AUC (dF/F0 * s)'].count()}")

print("\nFirst 10 Peaks Metrics:")
print(m_df[["Peak_ID", "Time (ms)", "dF/F0 Peak", "Rise Time T10-90 (ms)", "Decay Time T50 (ms)", "Decay Tau (ms)", "FWHM (ms)", "AUC (dF/F0 * s)"]].head(10))

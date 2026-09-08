"""
Calcium Signal Processing Engine
--------------------------------
Implements literature-standard algorithms for calcium transient analysis:
- Dynamic Baseline Estimation: Local Minimum, Rolling Percentile, Constant Minimum
- Signal Normalization: Delta F / F0 (dF/F0)
- Peak Detection: Direct (Raw) & Hybrid (Savitzky-Golay filter + raw refinement)
- Transient Kinetics: Sub-sample interpolated T10-90 rise time, T50 decay time, 
  single-exponential decay time constant (tau), max rise slope (dF/dt_max), 
  Area Under Curve (AUC), and FWHM duration.
- Global Rhythmicity: Frequency (Hz, min^-1), Inter-Event Intervals (IEI statistics), CV of IEI.
"""

import numpy as np
import pandas as pd
from scipy.signal import find_peaks, savgol_filter, peak_widths
from scipy.optimize import curve_fit
import warnings
import logging

logger = logging.getLogger(__name__)

# Trapezoidal integration compatible across NumPy 1.x and 2.x
if hasattr(np, 'trapezoid'):
    trapz_func = np.trapezoid
elif hasattr(np, 'trapz'):
    trapz_func = np.trapz
else:
    from scipy.integrate import trapezoid as trapz_func

class CalciumSignalProcessor:
    """Core scientific engine for calcium signal processing and kinetic analysis."""
    
    @staticmethod
    def parse_csv(filepath_or_buffer):
        """
        Parses a CSV file or buffer and identifies potential Time and ROI (signal) columns.
        Returns:
            df (pd.DataFrame): Parsed dataframe
            time_col (str or None): Column name identified as time, if any
            signal_cols (list): List of column names representing ROI signals
        """
        try:
            df = pd.read_csv(filepath_or_buffer, sep=None, engine='python')
        except Exception:
            if hasattr(filepath_or_buffer, 'seek'):
                filepath_or_buffer.seek(0)
            df = pd.read_csv(filepath_or_buffer)
            
        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]
        
        # Check for numeric columns only
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

    @staticmethod
    def estimate_signal_noise(y_signal):
        """
        Estimates the high-frequency white noise standard deviation (sigma) of a signal
        using the Median Absolute Deviation (MAD) of successive frame differences:
            sigma = median(|diff - median(diff)|) / (0.6745 * sqrt(2))
        This robust estimator is resistant to large transient peaks and slow baseline drift.
        """
        if len(y_signal) < 2:
            return 0.01
        diffs = np.diff(y_signal)
        mad = float(np.median(np.abs(diffs - np.median(diffs))))
        if mad > 0:
            sigma = mad / (0.6745 * np.sqrt(2.0))
        else:
            sigma = float(np.std(y_signal) / 5.0)
        return max(float(sigma), 1e-5)

    @staticmethod
    def estimate_noise_std(y_raw):
        """Estimate baseline noise standard deviation using median absolute deviation of diffs."""
        return CalciumSignalProcessor.estimate_signal_noise(y_raw)

    @classmethod
    def auto_tune_parameters(cls, y_raw, fps=100.0, profile="Cardiomyocytes", trace_mode="Delta F / F0"):
        """
        Automatically tunes and estimates peak detection parameters based on camera acquisition 
        rate (FPS), biological cell profile, and empirical signal noise floor.
        
        Profiles:
        - "Cardiomyocytes": Fast, rhythmic cardiac contractions (~0.5-1.5s transients, ~350ms refractory)
        - "Neurons (Fast Transients)": Fast somatic action potential calcium spikes (~150-400ms transients)
        - "Astrocytes (Slow Waves)": Long multi-second propagating calcium waves (~3-10s duration)
        - "Auto-Detect (General)": Balanced detection parameters scaled to acquisition frame rate
        
        Returns:
            dict: Recommended parameter settings {base_method, base_window, trace_mode, method, 
                  prominence, min_distance, smooth_window, dt, noise_sigma, profile}
        """
        n = len(y_raw)
        fps = float(fps) if fps and fps > 0 else 100.0
        dt = 1000.0 / fps

        profile_key = profile.lower()
        if "neuron" in profile_key:
            target_base_sec = 2.0
            target_refr_sec = 0.15
            target_sg_ms = 70.0
            prom_multiplier = 3.5
            min_prom = 0.08
        elif "astrocyte" in profile_key or "slow" in profile_key:
            target_base_sec = 8.0
            target_refr_sec = 1.2
            target_sg_ms = 250.0
            prom_multiplier = 2.5
            min_prom = 0.04
        else:
            # Cardiomyocytes and Default Auto-Detect
            target_base_sec = 3.5
            target_refr_sec = 0.35
            target_sg_ms = 110.0
            prom_multiplier = 3.0
            min_prom = 0.08

        # 1. Compute Base Window (frames, rounded to nearest 10 for slider compatibility)
        base_window = int(round(target_base_sec * fps))
        base_window = int(round(base_window / 10.0) * 10)
        max_win = max(20, min(1000, (n // 20) * 10)) if n > 40 else 50
        base_window = max(20, min(base_window, max_win))

        # 2. Compute Preliminary Baseline to assess dF/F0 noise
        baseline = cls.compute_baseline(y_raw, method="Rolling Percentile", window_pts=base_window)
        dff0 = cls.compute_dff0(y_raw, baseline)

        # 3. Estimate Noise Floor
        if trace_mode == "Delta F / F0":
            sigma = cls.estimate_signal_noise(dff0)
            prominence = max(min_prom, round(prom_multiplier * sigma, 3))
        else:
            sigma = cls.estimate_signal_noise(y_raw)
            med_f0 = float(np.median(baseline)) if len(baseline) > 0 else 100.0
            prominence = max(min_prom * med_f0, round(prom_multiplier * sigma, 3))

        # 4. Compute Min Distance (frames)
        min_distance = int(round(target_refr_sec * fps))
        min_distance = max(5, min(min_distance, max(10, n // 4)))

        # 5. Compute Savitzky-Golay Window (odd integer)
        sg_raw = int(round((target_sg_ms / 1000.0) * fps))
        if sg_raw % 2 == 0:
            sg_raw += 1
        smooth_window = max(5, min(51, sg_raw))

        return {
            "fps": round(fps, 1),
            "dt": round(dt, 2),
            "base_method": "Rolling Percentile",
            "base_window": int(base_window),
            "trace_mode": trace_mode,
            "method": "Hybrid (Smooth + Refine)",
            "prominence": float(prominence),
            "min_distance": int(min_distance),
            "smooth_window": int(smooth_window),
            "noise_sigma": round(sigma, 4),
            "profile": profile,
        }

    @staticmethod
    def compute_baseline(y_raw, method="Rolling Percentile", window_pts=100, quantile=0.15):
        """
        Computes dynamic baseline F0(t) across the signal trace.
        Methods:
        - "Rolling Percentile": Moving percentile (quantile) over window_pts
        - "Local Minimum": Rolling minimum followed by light smoothing
        - "Constant Minimum": Global minimum of signal
        """
        n = len(y_raw)
        if n == 0:
            return np.array([])
            
        window_pts = max(5, int(window_pts))
        
        if method == "Rolling Percentile":
            s = pd.Series(y_raw)
            b = s.rolling(window=window_pts, center=True, min_periods=1).quantile(quantile).values
            sg_win = min(window_pts if window_pts % 2 != 0 else window_pts - 1, len(b))
            if sg_win >= 5:
                b = savgol_filter(b, sg_win, polyorder=2)
            return b
            
        elif method == "Local Minimum":
            s = pd.Series(y_raw)
            b = s.rolling(window=window_pts, center=True, min_periods=1).min().values
            sg_win = min(window_pts if window_pts % 2 != 0 else window_pts - 1, len(b))
            if sg_win >= 5:
                b = savgol_filter(b, sg_win, polyorder=2)
            return b
            
        else: # "Constant Minimum" or fallback
            return np.full(n, np.min(y_raw))

    @staticmethod
    def compute_dff0(y_raw, baseline):
        """Computes Delta F / F0 trace: (F - F0) / F0."""
        safe_b = np.where(baseline <= 1e-6, 1e-6, baseline)
        return (y_raw - safe_b) / safe_b

    @classmethod
    def detect_peaks(cls, y_signal, dt, method="Hybrid (Smooth + Refine)", 
                     prominence=0.1, min_distance_pts=50, smooth_window_pts=11):
        """
        Detects peaks in signal trace.
        Returns dictionary with processed arrays and detected peak indices.
        """
        n = len(y_signal)
        t = np.arange(n) * dt
        
        min_distance_pts = max(1, int(min_distance_pts))
        prominence = float(prominence)
        
        y_smooth = None
        peaks = []
        peak_pairs = []
        
        if method == "Direct (Raw)":
            peaks, _ = find_peaks(y_signal, distance=min_distance_pts, prominence=prominence)
        else:
            win_len = int(smooth_window_pts)
            if win_len % 2 == 0:
                win_len += 1
            win_len = max(5, min(win_len, n if n % 2 != 0 else n - 1))
            
            y_smooth = savgol_filter(y_signal, window_length=win_len, polyorder=3)
            peaks_smooth, _ = find_peaks(y_smooth, distance=min_distance_pts, prominence=prominence)
            
            search_radius = max(5, int(win_len * 1.5))
            for p_sm in peaks_smooth:
                start = max(0, p_sm - search_radius)
                end = min(n, p_sm + search_radius + 1)
                local_max_rel = np.argmax(y_signal[start:end])
                p_ref = start + local_max_rel
                peaks.append(p_ref)
                peak_pairs.append((p_ref, p_sm))
                
            peaks = np.array(peaks, dtype=int)
            
        return {
            "t": t,
            "y_signal": y_signal,
            "y_smooth": y_smooth if y_smooth is not None else y_signal,
            "peaks": peaks,
            "peak_pairs": peak_pairs,
            "dt": dt
        }

    @classmethod
    def extract_peak_metrics(cls, t, y_raw, y_smooth, baseline, dff0, peaks, dt):
        """
        Extracts scientific metrics for each peak with sub-sample precision.
        Calculations are performed on normalized dF/F0 space for robust, unit-consistent kinetics.
        """
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

            # 2. Rise Time (T10-T90)
            amp_10 = local_base_dff0 + 0.10 * amp_dff0
            amp_90 = local_base_dff0 + 0.90 * amp_dff0
            
            pre_seg_t = t[local_onset_idx:p_idx+1]
            pre_seg_y = y_kinetic[local_onset_idx:p_idx+1]
            
            t_10 = np.nan
            t_90 = np.nan
            rise_time = np.nan
            max_rise_rate = np.nan
            
            if len(pre_seg_y) >= 2:
                dy_dt = np.diff(pre_seg_y) / (dt / 1000.0) if dt > 0 else np.diff(pre_seg_y)
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

            # 3. Decay Time (T50) & Exponential Decay Constant (Tau)
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

                try:
                    rel_t_sec = (post_seg_t - peak_time) / 1000.0
                    def exp_decay(t_sec, A, tau, C):
                        return A * np.exp(-t_sec / np.maximum(tau, 1e-4)) + C
                    
                    p0 = [amp_dff0, 0.2, local_base_dff0]
                    bounds = ([0.01 * amp_dff0, 0.001, -1.0], [3.0 * amp_dff0, 5.0, 1.0])
                    popt, _ = curve_fit(exp_decay, rel_t_sec, post_seg_y, p0=p0, bounds=bounds, maxfev=300)
                    tau_fit_ms = popt[1] * 1000.0
                    if 1.0 <= tau_fit_ms <= 4900.0:
                        tau_decay = tau_fit_ms
                except Exception:
                    pass
                    
                if pd.isna(tau_decay) and pd.notna(decay_50_time) and decay_50_time > 0:
                    tau_decay = decay_50_time / np.log(2.0)

            # 4. FWHM
            fwhm = np.nan
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    w = peak_widths(y_kinetic, [p_idx], rel_height=0.5)
                    if len(w[0]) > 0:
                        fwhm = w[0][0] * dt
            except Exception:
                pass

            # 5. Area Under Curve (AUC)
            if local_onset_idx < search_end:
                t_auc = t[local_onset_idx:search_end]
                y_auc = y_kinetic[local_onset_idx:search_end] - local_base_dff0
                y_auc = np.maximum(0, y_auc)
                auc = trapz_func(y_auc, t_auc / 1000.0)
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

    @classmethod
    def compute_global_statistics(cls, metrics_df, total_points, dt):
        """Computes summary KPI statistics for a set of peak metrics."""
        total_duration_ms = total_points * dt
        total_duration_sec = total_duration_ms / 1000.0
        n_peaks = len(metrics_df)
        
        freq_hz = n_peaks / total_duration_sec if total_duration_sec > 0 else 0.0
        freq_bpm = freq_hz * 60.0
        
        if n_peaks > 1:
            iei = np.diff(metrics_df["Time (ms)"])
            mean_iei = float(np.mean(iei))
            median_iei = float(np.median(iei))
            std_iei = float(np.std(iei))
            cv_iei = std_iei / mean_iei if mean_iei > 0 else 0.0
        else:
            mean_iei = median_iei = std_iei = cv_iei = 0.0
            
        return {
            "Total Peaks": int(n_peaks),
            "Total Duration (s)": round(total_duration_sec, 3),
            "Frequency (Hz)": round(freq_hz, 3),
            "Frequency (events/min)": round(freq_bpm, 2),
            "Mean Amplitude (dF/F0)": round(float(metrics_df["dF/F0 Peak"].mean()), 4) if n_peaks > 0 else 0.0,
            "Mean Rise Time T10-90 (ms)": round(float(metrics_df["Rise Time T10-90 (ms)"].mean()), 2) if n_peaks > 0 else 0.0,
            "Mean Decay T50 (ms)": round(float(metrics_df["Decay Time T50 (ms)"].mean()), 2) if n_peaks > 0 else 0.0,
            "Mean Decay Tau (ms)": round(float(metrics_df["Decay Tau (ms)"].mean()), 2) if n_peaks > 0 else 0.0,
            "Mean Inter-Event Interval (ms)": round(mean_iei, 2),
            "Median Inter-Event Interval (ms)": round(median_iei, 2),
            "Rhythmicity (SD of IEI ms)": round(std_iei, 2),
            "Rhythmicity Index (CV of IEI)": round(cv_iei, 4)
        }

    @staticmethod
    def get_glossary():
        """Returns dataframe explaining all metrics."""
        return pd.DataFrame({
            "Metric": [
                "Peak Raw Intensity", "Baseline F0", "dF/F0 Peak", "Amplitude (dF/F0)",
                "Rise Time T10-90 (ms)", "Max Rise Rate (dF/dt)", "Decay Time T50 (ms)",
                "Decay Tau (ms)", "FWHM (ms)", "AUC (dF/F0 * s)",
                "Frequency (Hz)", "Inter-Event Interval (IEI)", "Rhythmicity Index (CV)"
            ],
            "Description": [
                "Absolute raw fluorescence intensity at the peak max.",
                "Estimated resting baseline fluorescence level at or prior to transient onset.",
                "Normalized change in fluorescence relative to baseline: (F_peak - F0) / F0.",
                "Net amplitude above preceding local baseline in dF/F0 units.",
                "Time taken for fluorescence to rise from 10% to 90% of maximum amplitude (sub-sample interpolated).",
                "Maximum slope of signal during rising phase.",
                "Time taken for peak to decay to 50% of its max amplitude (sub-sample interpolated).",
                "Single-exponential decay time constant (fitted curve tau).",
                "Full Width at Half Maximum: transient duration at 50% max height.",
                "Area Under Curve: integrated total calcium transient influx across duration (dF/F0 * s).",
                "Transient event rate per second.",
                "Time interval between consecutive peak times.",
                "Coefficient of variation of IEI (SD / Mean). Lower values indicate regular rhythmic activity."
            ]
        })

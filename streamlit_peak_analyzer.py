# peak_analyzer_streamlit.py
import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter, peak_widths
from io import BytesIO

# ──────────────────────────────────────────────
# Page Config
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Calcium Signal Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# Custom CSS for professional look
# ──────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .stButton > button[kind="primary"] {
        background-color: #059669;
        border-color: #059669;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #047857;
        border-color: #047857;
    }
    .section-divider {
        border-top: 1px solid #e5e7eb;
        margin: 1.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Core Analysis Functions (pure, no UI)
# ──────────────────────────────────────────────
def detect_peaks(y_raw, dt, method, prominence, min_distance, smooth_window):
    """Run peak detection and return results dict."""
    t = np.arange(len(y_raw)) * dt
    peaks = []
    peak_pairs = []
    y_smooth = None

    if method == "Direct (Raw)":
        peaks, _ = find_peaks(y_raw, distance=min_distance, prominence=prominence, width=2)
    else:
        # Hybrid: smooth -> detect -> refine on raw
        win_len = smooth_window
        if win_len % 2 == 0:
            win_len += 1
        y_smooth = savgol_filter(y_raw, window_length=win_len, polyorder=3)
        peaks_smooth, _ = find_peaks(y_smooth, distance=min_distance, prominence=prominence, width=5)
        search_window = 100
        for p_smooth in peaks_smooth:
            start = max(0, p_smooth - search_window)
            end = min(len(y_raw), p_smooth + search_window)
            local_max_idx = np.argmax(y_raw[start:end])
            p_refined = start + local_max_idx
            peaks.append(p_refined)
            peak_pairs.append((p_refined, p_smooth))
        peaks = np.array(peaks)

    return {
        "t": t,
        "y_raw": y_raw,
        "y_smooth": y_smooth,
        "peaks": peaks,
        "peak_pairs": peak_pairs,
    }

def compute_metrics(results, method):
    """Compute per-peak and global metrics from detection results."""
    t = results["t"]
    y_raw = results["y_raw"]
    y_smooth = results["y_smooth"]
    peaks = results["peaks"]
    peak_pairs = results["peak_pairs"]

    metrics_list = []
    for i, p_idx in enumerate(peaks):
        peak_val = y_raw[p_idx]

        if method == "Hybrid (Smooth + Refine)" and y_smooth is not None:
            p_smooth = peak_pairs[i][1]
            search_back = 200
            search_start = max(0, p_smooth - search_back)
            f0_idx = np.argmin(y_smooth[search_start:p_smooth]) + search_start
            f0_val = y_smooth[f0_idx]

            amplitude = peak_val - f0_val
            dff = (peak_val - f0_val) / f0_val if f0_val != 0 else 0

            amp_10 = f0_val + 0.1 * amplitude
            amp_90 = f0_val + 0.9 * amplitude
            amp_50 = f0_val + 0.5 * amplitude

            pre_seg = y_smooth[f0_idx:p_smooth]
            t_10_idx = np.where(pre_seg >= amp_10)[0]
            t_90_idx = np.where(pre_seg >= amp_90)[0]
            rise_time = (
                t[f0_idx + t_90_idx[0]] - t[f0_idx + t_10_idx[0]]
                if len(t_10_idx) > 0 and len(t_90_idx) > 0 and t_90_idx[0] > t_10_idx[0]
                else np.nan
            )

            post_seg = y_smooth[p_smooth : min(len(y_smooth), p_smooth + 400)]
            try:
                t_50_local = np.where(post_seg <= amp_50)[0][0]
                decay_time = t[p_smooth + int(t_50_local)] - t[p_smooth]
            except IndexError:
                decay_time = np.nan

            try:
                w = peak_widths(y_smooth, [p_smooth], rel_height=0.5)
                fwhm = w[0][0] * (t[1] - t[0]) if len(t) > 1 else np.nan
            except Exception:
                fwhm = np.nan
        else:
            f0_val = dff = rise_time = decay_time = fwhm = np.nan

        metrics_list.append({
            "Peak_ID": i + 1,
            "Time (ms)": t[p_idx],
            "Peak Intensity": peak_val,
            "F0 Baseline": f0_val,
            "dF/F0": dff,
            "Rise Time (ms)": rise_time,
            "Decay Time (ms)": decay_time,
            "FWHM (ms)": fwhm,
        })

    df_metrics = pd.DataFrame(metrics_list)

    # Global stats
    total_duration_sec = len(y_raw) * (t[1] - t[0]) / 1000.0 if len(t) > 1 else 0
    freq_hz = len(peaks) / total_duration_sec if total_duration_sec > 0 else 0
    iei = np.diff(df_metrics["Time (ms)"]) if len(df_metrics) > 1 else np.array([])

    global_stats = {
        "Total Peaks": len(peaks),
        "Total Duration (s)": round(total_duration_sec, 3),
        "Frequency (Hz)": round(freq_hz, 3),
        "Avg Inter-Event Interval (ms)": round(np.mean(iei), 3) if len(iei) > 0 else 0,
        "Rhythmicity (Std Dev IEI)": round(np.std(iei), 3) if len(iei) > 0 else 0,
    }

    # Glossary
    glossary = pd.DataFrame({
        "Metric": [
            "Peak Intensity", "F0 Baseline", "dF/F0", "Rise Time (ms)",
            "Decay Time (ms)", "FWHM (ms)", "Avg Inter-Event Interval (ms)", "Rhythmicity"
        ],
        "Description": [
            "The absolute maximum raw intensity value of the peak.",
            "The minimum smoothed intensity found in the local window prior to the peak.",
            "Fractional change in fluorescence: (Peak - Baseline) / Baseline.",
            "Time taken to go from 10% to 90% of the peak amplitude.",
            "Time taken to drop from the peak to 50% of the peak amplitude.",
            "Full Width at Half Maximum. The duration of the peak at 50% of its max amplitude.",
            "The average time (in milliseconds) between consecutive peaks.",
            "The standard deviation of the inter-event intervals (lower means more rhythmic)."
        ]
    })

    return df_metrics, global_stats, glossary

def create_excel_download(df_metrics, global_stats, glossary):
    """Create Excel file in memory for download."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([global_stats]).to_excel(writer, sheet_name="Global Stats", index=False)
        df_metrics.to_excel(writer, sheet_name="Metrics per Peak", index=False)
        glossary.to_excel(writer, sheet_name="Metrics Glossary", index=False)
    return output.getvalue()

def plot_results(results, method, theme):
    """Create matplotlib figure matching original styling."""
    t = results["t"]
    y_raw = results["y_raw"]
    y_smooth = results["y_smooth"]
    peaks = results["peaks"]

    # Theme colors
    if theme == "Dark":
        bg_color = "#2b2b2b"
        text_color = "white"
        spine_color = "#555555"
        grid_color = "white"
        legend_bg = "#333333"
        raw_color = "gray"
        smooth_color = "#2ecc71"
        peak_color_hybrid = "#e74c3c"
        peak_color_raw = "#3498db"
    else:
        bg_color = "#ffffff"
        text_color = "black"
        spine_color = "#cccccc"
        grid_color = "gray"
        legend_bg = "#ffffff"
        raw_color = "gray"
        smooth_color = "#2ecc71"
        peak_color_hybrid = "#e74c3c"
        peak_color_raw = "#3498db"

    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)

    # Raw signal
    ax.plot(t, y_raw, color=raw_color, alpha=0.5, label="Raw Signal", linewidth=0.8)

    # Smoothed + peaks
    if method == "Hybrid (Smooth + Refine)" and y_smooth is not None:
        ax.plot(t, y_smooth, color=smooth_color, linewidth=1.2, alpha=0.9, label="Smoothed")
        if len(peaks) > 0:
            ax.plot(t[peaks], y_raw[peaks], "x", color=peak_color_hybrid,
                    markersize=9, markeredgewidth=2, label="Hybrid Peaks")
    else:
        if len(peaks) > 0:
            ax.plot(t[peaks], y_raw[peaks], "x", color=peak_color_raw,
                    markersize=9, markeredgewidth=2, label="Raw Peaks")

    freq_hz = len(peaks) / (len(y_raw) * (t[1] - t[0]) / 1000.0) if len(y_raw) > 1 and len(t) > 1 else 0

    ax.set_title(f"Peak Detection  |  Frequency: {freq_hz:.2f} Hz", color=text_color, fontsize=13, pad=12)
    ax.set_xlabel("Time (ms)", color=text_color, fontsize=11)
    ax.set_ylabel("Intensity", color=text_color, fontsize=11)
    ax.tick_params(colors=text_color, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color(spine_color)
    ax.grid(True, alpha=0.15, color=grid_color)
    ax.legend(loc="upper right", facecolor=legend_bg, edgecolor=text_color,
              labelcolor=text_color, fontsize=9, framealpha=0.9)
    fig.tight_layout()
    return fig

# ──────────────────────────────────────────────
# Session State Initialization
# ──────────────────────────────────────────────
def reset_analysis_state():
    """Clear uploaded data and any derived analysis results."""
    st.session_state.y_raw = None
    st.session_state.df_raw = None
    st.session_state.filename = None
    st.session_state.results = None
    st.session_state.metrics_df = None
    st.session_state.global_stats = None
    st.session_state.glossary_df = None


defaults = {
    "y_raw": None,
    "df_raw": None,
    "filename": None,
    "results": None,
    "metrics_df": None,
    "global_stats": None,
    "glossary_df": None,
    "theme": "Light",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ──────────────────────────────────────────────
# Sidebar Controls
# ──────────────────────────────────────────────


with st.sidebar:
    st.markdown('<div class="main-header">📊 Calcium Peak Analyser</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Signal peak detection & metrics</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # 1. File Upload
    st.markdown("### 1. Load Data")
    uploaded_file = st.file_uploader(
        "Upload CSV file",
        type=["csv"],
        help="The last column will be used as the signal intensity.",
        label_visibility="collapsed"
    )

    if uploaded_file is None:
        if st.session_state.filename is not None or st.session_state.y_raw is not None:
            reset_analysis_state()
            st.session_state.theme = st.session_state.get("theme", "Light")
            st.info("Upload cleared. No file is currently loaded.")
    elif uploaded_file.name != st.session_state.filename:
        try:
            df = pd.read_csv(uploaded_file, sep=None, engine="python")
            y_raw = df.iloc[:, -1].values.astype(float)
            st.session_state.y_raw = y_raw
            st.session_state.df_raw = df
            st.session_state.filename = uploaded_file.name
            st.session_state.results = None
            st.session_state.metrics_df = None
            st.session_state.global_stats = None
            st.session_state.glossary_df = None
            st.success(f"Loaded: {uploaded_file.name} ({len(y_raw)} samples)")
        except Exception as e:
            st.error(f"Failed to load file: {e}")

    if st.session_state.y_raw is not None:
        st.caption(f"Current file: **{st.session_state.filename}**  |  Samples: **{len(st.session_state.y_raw):,}**")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # 2. Method Selection
    st.markdown("### 2. Detection Method")
    method = st.selectbox(
        "Method",
        ["Hybrid (Smooth + Refine)", "Direct (Raw)"],
        index=0,
        label_visibility="collapsed"
    )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # 3. Parameters
    st.markdown("### 3. Parameters")

    col1, col2 = st.columns(2)
    with col1:
        prominence = st.slider("Prominence", 1, 100, 15, help="Minimum peak prominence")
    with col2:
        min_distance = st.slider("Min Distance (frames)", 10, 500, 100, help="Minimum horizontal distance between peaks")

    if method == "Hybrid (Smooth + Refine)":
        smooth_window = st.slider("Smooth Window (odd)", 5, 51, 11, step=2, help="Savitzky-Golay window length (must be odd)")
    else:
        smooth_window = 11  # unused but kept for function signature

    dt = st.number_input("Time step (ms/frame)", min_value=0.1, max_value=1000.0, value=10.0, step=0.1, format="%.1f")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # 4. Theme
    st.markdown("### 4. Appearance")
    theme = st.radio("Theme", ["Light", "Dark"], horizontal=True, label_visibility="collapsed")
    st.session_state.theme = theme

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # Run Analysis Button
    run_analysis = st.button("🔄 Run Analysis", type="primary", width='stretch',
                             disabled=st.session_state.y_raw is None)

    if run_analysis and st.session_state.y_raw is not None:
        with st.spinner("Analyzing..."):
            results = detect_peaks(
                st.session_state.y_raw, dt, method, prominence, min_distance, smooth_window
            )
            st.session_state.results = results
            df_metrics, global_stats, glossary = compute_metrics(results, method)
            st.session_state.metrics_df = df_metrics
            st.session_state.global_stats = global_stats
            st.session_state.glossary_df = glossary
        st.success("Analysis complete!")

    st.markdown('<div class="sub-header" style="text-align: justify;">❗Make sure to click "Run Analysis" every time you change parameters above.</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # 5. Export
    st.markdown("### 5. Export Results")
    if st.session_state.metrics_df is not None:
        excel_bytes = create_excel_download(
            st.session_state.metrics_df,
            st.session_state.global_stats,
            st.session_state.glossary_df
        )
        st.download_button(
            label="📥 Download Excel Report",
            data=excel_bytes,
            file_name="Peak_Metrics.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width='stretch'
        )
    else:
        st.button("📥 Download Excel Report", disabled=True, width='stretch',
                  help="Run analysis first to enable export")
    

    

# ──────────────────────────────────────────────
# Main Area - Plot & Results
# ──────────────────────────────────────────────

# Header
st.markdown('<div class="main-header">Calcium signalling analysis</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Interactive peak detection with Savitzky-Golay smoothing and automated metric extraction</div>', unsafe_allow_html=True)

if st.session_state.y_raw is None:
    # Empty state
    st.info("👈 Upload a CSV file from the sidebar to begin analysis.")
    st.markdown("""
    **Expected CSV format:**
    - Any number of columns
    - **Last column** = signal intensity values
    - No header required (auto-detected)

    **Methods:**
    - **Hybrid (Smooth + Refine)**: Smooths signal → detects peaks → refines positions on raw data. Computes full metrics (dF/F0, rise/decay times, FWHM).
    - **Direct (Raw)**: Detects peaks directly on raw signal. Faster, no smoothing artifacts, but limited metrics.
    """)
else:
    # Show plot if analysis has run
    if st.session_state.results is not None:
        fig = plot_results(st.session_state.results, method, theme)
        st.pyplot(fig, width='stretch')
        plt.close(fig)

        # Global Stats Cards
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("### 📈 Global Statistics")
        gs = st.session_state.global_stats
        cols = st.columns(len(gs))
        for i, (key, val) in enumerate(gs.items()):
            with cols[i]:
                st.metric(key, f"{val:,}" if isinstance(val, (int, np.integer)) else f"{val:.3f}")

        # Metrics Table
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("### 📋 Per-Peak Metrics")
        df_show = st.session_state.metrics_df.copy()
        # Format for display
        for col in ["Time (ms)", "Peak Intensity", "F0 Baseline", "dF/F0", "Rise Time (ms)", "Decay Time (ms)", "FWHM (ms)"]:
            if col in df_show.columns:
                df_show[col] = df_show[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
        st.dataframe(df_show, width='stretch', hide_index=True)

        # Glossary Expander
        with st.expander("📖 Metrics Glossary"):
            st.dataframe(st.session_state.glossary_df, width='stretch', hide_index=True)

    else:
        # File loaded but no analysis run yet
        st.info("Configure parameters in the sidebar and click **Run Analysis** to detect peaks.")
        # Show raw signal preview
        fig, ax = plt.subplots(figsize=(10, 3.5), dpi=120)
        t_preview = np.arange(len(st.session_state.y_raw)) * dt
        ax.plot(t_preview = ax.plot(t_preview, st.session_state.y_raw, color="#6b7280", alpha=0.7, linewidth=0.6))
        ax.set_xlabel("Time (ms)")
        ax.set_ylabel("Intensity")
        ax.set_title("Raw Signal Preview")
        ax.grid(True, alpha=0.2)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
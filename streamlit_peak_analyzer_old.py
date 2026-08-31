# streamlit_peak_analyzer.py
import sys
import os
import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

# Add src folder to python path if needed
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from calcium_peak_analyzer.core.calcium_processor import CalciumSignalProcessor

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
        margin-bottom: 1.5rem;
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
# Session State Initialization
# ──────────────────────────────────────────────
def reset_analysis_state():
    """Clear uploaded data and any derived analysis results."""
    st.session_state.df_raw = None
    st.session_state.time_col = None
    st.session_state.signal_cols = []
    st.session_state.current_roi = None
    st.session_state.filename = None
    st.session_state.results = None
    st.session_state.metrics_df = None
    st.session_state.global_stats = None

defaults = {
    "df_raw": None,
    "time_col": None,
    "signal_cols": [],
    "current_roi": None,
    "filename": None,
    "results": None,
    "metrics_df": None,
    "global_stats": None,
    "theme": "Light",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ──────────────────────────────────────────────
# Sidebar Controls
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="main-header">🔬 Calcium Signal Analyser</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Peak kinetics & rhythmicity analysis</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # 1. File Upload
    st.markdown("### 1. Load Data")
    uploaded_file = st.file_uploader(
        "Upload CSV file",
        type=["csv"],
        help="Upload single or multi-column calcium imaging data",
        label_visibility="collapsed"
    )

    if uploaded_file is None:
        if st.session_state.filename is not None:
            reset_analysis_state()
            st.info("Upload cleared. No file is currently loaded.")
    elif uploaded_file.name != st.session_state.filename:
        try:
            df, time_col, signal_cols = CalciumSignalProcessor.parse_csv(uploaded_file)
            st.session_state.df_raw = df
            st.session_state.time_col = time_col
            st.session_state.signal_cols = signal_cols
            st.session_state.current_roi = signal_cols[0] if signal_cols else None
            st.session_state.filename = uploaded_file.name
            st.session_state.results = None
            st.session_state.metrics_df = None
            st.session_state.global_stats = None
            st.success(f"Loaded: {uploaded_file.name} ({len(df):,} samples)")
        except Exception as e:
            st.error(f"Failed to load file: {e}")

    if st.session_state.df_raw is not None:
        st.caption(f"Current file: **{st.session_state.filename}**  |  Samples: **{len(st.session_state.df_raw):,}**")

        if len(st.session_state.signal_cols) > 1:
            st.session_state.current_roi = st.selectbox(
                "Select Signal / ROI",
                st.session_state.signal_cols,
                index=0
            )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # 2. Baseline & Method Selection
    st.markdown("### 2. Baseline & Method")
    base_method = st.selectbox(
        "Baseline F0 Method",
        ["Rolling Percentile", "Local Minimum", "Constant Minimum"],
        index=0
    )
    
    trace_mode = st.radio("Display Trace Mode", ["Delta F / F0", "Raw Intensity F(t)"], horizontal=True)

    method = st.selectbox(
        "Detection Method",
        ["Hybrid (Smooth + Refine)", "Direct (Raw)"],
        index=0
    )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # 3. Parameters
    st.markdown("### 3. Parameters")

    col1, col2 = st.columns(2)
    with col1:
        prominence = st.number_input("Prominence", min_value=0.001, max_value=1000.0, value=0.03, step=0.005, format="%.3f")
    with col2:
        min_distance = st.number_input("Min Distance (frames)", min_value=1, max_value=2000, value=50, step=5)

    if method == "Hybrid (Smooth + Refine)":
        smooth_window = st.slider("Smooth Window (odd)", 5, 51, 11, step=2, help="Savitzky-Golay window length")
    else:
        smooth_window = 11

    base_window = st.slider("Baseline Window (frames)", 10, 500, 100, step=10)

    default_dt = 10.0
    if st.session_state.time_col is not None and st.session_state.df_raw is not None:
        t_vals = st.session_state.df_raw[st.session_state.time_col].values
        if len(t_vals) > 1:
            dt_calc = float(np.mean(np.diff(t_vals)))
            if dt_calc > 0:
                default_dt = dt_calc
                
    dt = st.number_input("Time step Δt (ms/frame)", min_value=0.1, max_value=5000.0, value=float(default_dt), step=1.0, format="%.2f")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # 4. Appearance
    st.markdown("### 4. Appearance")
    theme = st.radio("Theme", ["Light", "Dark"], horizontal=True, label_visibility="collapsed")
    st.session_state.theme = theme

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # Run Analysis Button
    run_analysis = st.button("🔄 Run Analysis", type="primary", width="stretch",
                             disabled=st.session_state.df_raw is None)

    if run_analysis and st.session_state.df_raw is not None and st.session_state.current_roi is not None:
        with st.spinner("Analyzing transient kinetics..."):
            y_raw = st.session_state.df_raw[st.session_state.current_roi].values.astype(float)
            baseline = CalciumSignalProcessor.compute_baseline(y_raw, method=base_method, window_pts=base_window)
            dff0 = CalciumSignalProcessor.compute_dff0(y_raw, baseline)
            
            y_analysis = dff0 if trace_mode == "Delta F / F0" else y_raw
            results = CalciumSignalProcessor.detect_peaks(
                y_analysis, dt, method=method, prominence=prominence, min_distance_pts=min_distance, smooth_window_pts=smooth_window
            )
            
            metrics_df = CalciumSignalProcessor.extract_peak_metrics(
                results["t"], y_raw, results["y_smooth"], baseline, dff0, results["peaks"], dt
            )
            global_stats = CalciumSignalProcessor.compute_global_statistics(metrics_df, len(y_raw), dt)

            st.session_state.y_raw = y_raw
            st.session_state.baseline = baseline
            st.session_state.dff0 = dff0
            st.session_state.results = results
            st.session_state.metrics_df = metrics_df
            st.session_state.global_stats = global_stats
            st.session_state.trace_mode = trace_mode
            
        st.success("Analysis complete!")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # 5. Export
    st.markdown("### 5. Export Results")
    if st.session_state.metrics_df is not None:
        excel_bytes = BytesIO()
        df_global = pd.DataFrame([st.session_state.global_stats])
        df_glossary = CalciumSignalProcessor.get_glossary()
        df_trace = pd.DataFrame({
            "Time (ms)": st.session_state.results["t"],
            "Raw Intensity F(t)": st.session_state.y_raw,
            "Baseline F0(t)": st.session_state.baseline,
            "Delta F / F0": st.session_state.dff0
        })
        with pd.ExcelWriter(excel_bytes, engine="openpyxl") as writer:
            df_global.to_excel(writer, sheet_name="Global Statistics", index=False)
            st.session_state.metrics_df.to_excel(writer, sheet_name="Per-Peak Metrics", index=False)
            df_trace.to_excel(writer, sheet_name="Signal Traces", index=False)
            df_glossary.to_excel(writer, sheet_name="Metrics Glossary", index=False)

        st.download_button(
            label="📥 Download Excel Report",
            data=excel_bytes.getvalue(),
            file_name="Calcium_Peak_Metrics_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch"
        )
    else:
        st.button("📥 Download Excel Report", disabled=True, width="stretch")

# ──────────────────────────────────────────────
# Main Area - Plot & Results
# ──────────────────────────────────────────────
st.markdown('<div class="main-header">Calcium signalling analysis</div>', unsafe_allow_html=True)
st.markdown(r'<div class="sub-header">Interactive peak kinetics (T10-90 rise time, T50 decay, tau, AUC) with \Delta F/F0 normalization</div>', unsafe_allow_html=True)

if st.session_state.df_raw is None:
    st.info("👈 Upload a CSV file from the sidebar to begin analysis.")
    st.markdown(r"""
    **Expected CSV format:**
    - Any number of columns (Auto-detects Time and ROI signal columns)
    - **Methods:**
      - **Hybrid (Smooth + Refine)**: Smooths signal → detects peaks → refines positions on raw data.
      - **Direct (Raw)**: Detects peaks directly on raw signal.
    - **Advanced Metrics:** $T_{10-90}$ rise time, $T_{50}$ decay time, single-exponential decay constant $\tau$, AUC, and rhythmicity index ($CV_{\text{IEI}}$).
    """)
else:
    if st.session_state.results is not None:
        t = st.session_state.results["t"]
        mode = st.session_state.trace_mode
        peaks = st.session_state.results["peaks"]

        bg_color = "#2b2b2b" if theme == "Dark" else "#ffffff"
        text_color = "white" if theme == "Dark" else "black"
        spine_color = "#555555" if theme == "Dark" else "#cccccc"
        grid_color = "white" if theme == "Dark" else "gray"
        legend_bg = "#333333" if theme == "Dark" else "#ffffff"

        fig, ax = plt.subplots(figsize=(10, 4.5), dpi=120)
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)

        if mode == "Delta F / F0":
            ax.plot(t, st.session_state.dff0, color="#3498db", alpha=0.8, linewidth=0.9, label="ΔF / F0")
            if st.session_state.results["y_smooth"] is not None:
                ax.plot(t, st.session_state.results["y_smooth"], color="#2ecc71", linewidth=1.1, label="Smoothed")
            if len(peaks) > 0:
                ax.plot(t[peaks], st.session_state.dff0[peaks], "x", color="#e74c3c", markersize=8, markeredgewidth=2, label="Peaks")
            ax.set_ylabel("ΔF / F0", color=text_color)
        else:
            ax.plot(t, st.session_state.y_raw, color="gray", alpha=0.7, linewidth=0.8, label="Raw Intensity")
            ax.plot(t, st.session_state.baseline, color="#f1c40f", linestyle="--", label="Baseline F0")
            if len(peaks) > 0:
                ax.plot(t[peaks], st.session_state.y_raw[peaks], "x", color="#e74c3c", markersize=8, markeredgewidth=2, label="Peaks")
            ax.set_ylabel("Intensity", color=text_color)

        freq_hz = st.session_state.global_stats["Frequency (Hz)"]
        ax.set_title(f"Peak Detection — ROI: {st.session_state.current_roi}  |  Frequency: {freq_hz:.2f} Hz", color=text_color)
        ax.set_xlabel("Time (ms)", color=text_color)
        ax.tick_params(colors=text_color)
        for spine in ax.spines.values():
            spine.set_color(spine_color)
        ax.grid(True, alpha=0.15, color=grid_color)
        ax.legend(loc="upper right", facecolor=legend_bg, edgecolor=text_color, labelcolor=text_color)
        fig.tight_layout()
        st.pyplot(fig, width="stretch")
        plt.close(fig)

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("### 📈 Global Statistics")
        gs = st.session_state.global_stats
        cols = st.columns(len(gs))
        for i, (key, val) in enumerate(gs.items()):
            with cols[i]:
                st.metric(key, f"{val:,}" if isinstance(val, (int, np.integer)) else f"{val}")

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("### 📋 Per-Peak Kinetics Table")
        df_show = st.session_state.metrics_df.copy()
        for col in df_show.columns:
            if df_show[col].dtype == float:
                df_show[col] = df_show[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
        st.dataframe(df_show, width="stretch", hide_index=True)

        with st.expander("📖 Metrics Glossary"):
            st.dataframe(CalciumSignalProcessor.get_glossary(), width="stretch", hide_index=True)

    else:
        st.info("Configure parameters in the sidebar and click **Run Analysis** to detect peaks.")
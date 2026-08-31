# streamlit_peak_analyzer_vibe.py
"""
Calcium Signal Peak Analyzer (Vibe Edition Pro)
Professional, interactive Streamlit application for calcium transient signal analysis,
peak detection, dynamic baseline estimation, metric extraction, and single-peak inspection.

Uses Streamlit native components (st.container with border, st.metric, native theme engine)
and integrates the core CalciumSignalProcessor literature-standard analysis engine.
"""

import sys
import os
import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import altair as alt

# Add src folder to python path if needed
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from calcium_peak_analyzer.core.calcium_processor import CalciumSignalProcessor

# ──────────────────────────────────────────────
# Page Configuration
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Calcium Signal Analyzer Pro",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# Sample Data Generator
# ──────────────────────────────────────────────
def generate_sample_data(num_samples=2500, dt=10.0, num_peaks=10, noise_level=4.0, seed=42):
    """Generate realistic synthetic calcium transients with baseline drift and noise."""
    np.random.seed(seed)
    t = np.arange(num_samples) * dt
    y_baseline = 100 + 15 * np.sin(2 * np.pi * t / (num_samples * dt * 0.8))
    y = y_baseline.copy()
    
    # Place transient calcium peaks
    peak_indices = np.sort(np.random.choice(np.arange(150, num_samples - 200), size=num_peaks, replace=False))
    valid_peaks = []
    last_p = -300
    for p in peak_indices:
        if p - last_p > 150:
            valid_peaks.append(p)
            last_p = p

    for p in valid_peaks:
        amp = np.random.uniform(40, 90)
        tau_rise = np.random.uniform(4, 8)
        tau_decay = np.random.uniform(25, 45)
        
        t_local = np.arange(0, 300)
        transient = amp * (1 - np.exp(-t_local / tau_rise)) * np.exp(-t_local / tau_decay)
        end_idx = min(num_samples, p + len(transient))
        y[p:end_idx] += transient[:end_idx - p]

    noise = np.random.normal(0, noise_level, size=num_samples)
    y_raw = y + noise
    
    df = pd.DataFrame({"Time_ms": t, "Calcium_Signal": y_raw})
    return df, y_raw

def create_excel_download(df_metrics, global_stats, glossary, df_trace=None):
    """Create multi-sheet Excel file in memory."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([global_stats]).to_excel(writer, sheet_name="Global Statistics", index=False)
        df_metrics.to_excel(writer, sheet_name="Per-Peak Metrics", index=False)
        if df_trace is not None:
            df_trace.to_excel(writer, sheet_name="Signal Traces", index=False)
        glossary.to_excel(writer, sheet_name="Metrics Glossary", index=False)
    return output.getvalue()

# ──────────────────────────────────────────────
# Visualization Engines (Matplotlib & Altair)
# ──────────────────────────────────────────────
def plot_matplotlib(results, dff0, baseline, mode, method, theme, current_roi="ROI"):
    """Generate high-DPI scientific Matplotlib figure adapting to theme selection."""
    t = results["t"]
    y_raw = results["y_signal"]
    y_smooth = results["y_smooth"]
    peaks = results["peaks"]

    if theme == "Dark":
        bg_color = "#0e1117"
        card_color = "#161b22"
        text_color = "#fafafa"
        spine_color = "#30363d"
        grid_color = "#30363d"
        raw_color = "#8b949e"
        smooth_color = "#2dd4bf"
        peak_color = "#f43f5e"
    else:
        bg_color = "#ffffff"
        card_color = "#f8fafc"
        text_color = "#0f172a"
        spine_color = "#cbd5e1"
        grid_color = "#e2e8f0"
        raw_color = "#64748b"
        smooth_color = "#0d9488"
        peak_color = "#e11d48"

    fig, ax = plt.subplots(figsize=(12, 5.2), dpi=140)
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(card_color)

    if mode == "Delta F / F0":
        ax.plot(t, dff0, color=raw_color, alpha=0.8, label="ΔF / F0", linewidth=0.9)
        if method.startswith("Hybrid") and y_smooth is not None:
            ax.plot(t, y_smooth, color=smooth_color, linewidth=1.6, alpha=0.95, label="SG Smoothed Signal")
        if len(peaks) > 0:
            ax.plot(t[peaks], dff0[peaks], "v", color=peak_color,
                    markersize=9, markeredgewidth=1.5, markeredgecolor="white", label=f"Detected Peaks (n={len(peaks)})")
        ax.set_ylabel("ΔF / F0", color=text_color, fontsize=11, fontweight=400)
    else:
        ax.plot(t, y_raw, color=raw_color, alpha=0.5, label="Raw Signal F(t)", linewidth=0.9)
        ax.plot(t, baseline, color="#f59e0b", linestyle="--", linewidth=1.5, label="Baseline F0(t)")
        if len(peaks) > 0:
            ax.plot(t[peaks], y_raw[peaks], "v", color=peak_color,
                    markersize=9, markeredgewidth=1.5, markeredgecolor="white", label=f"Detected Peaks (n={len(peaks)})")
        ax.set_ylabel("Fluorescence Intensity", color=text_color, fontsize=11, fontweight=400)

    freq_hz = len(peaks) / (len(y_raw) * (t[1] - t[0]) / 1000.0) if len(y_raw) > 1 and len(t) > 1 else 0

    ax.set_title(f"Calcium Signal Peak Detection — ROI: {current_roi}  |  Frequency: {freq_hz:.2f} Hz  |  Total Peaks: {len(peaks)}",
                 color=text_color, fontsize=13, fontweight="bold", pad=14)
    ax.set_xlabel("Time (ms)", color=text_color, fontsize=11, fontweight=400)
    ax.tick_params(colors=text_color, labelsize=9.5)
    for spine in ax.spines.values():
        spine.set_color(spine_color)
        spine.set_linewidth(1.0)
    ax.grid(True, alpha=0.35, color=grid_color, linestyle="--")
    ax.legend(loc="upper right", facecolor=bg_color, edgecolor=spine_color,
              labelcolor=text_color, fontsize=9.5, framealpha=0.9, shadow=False)
    fig.tight_layout()
    return fig

def plot_altair(results, dff0, mode, method):
    """Generate interactive Altair line chart with pan/zoom and hover capabilities."""
    t = results["t"]
    y_raw = results["y_signal"]
    y_smooth = results["y_smooth"]
    peaks = results["peaks"]

    y_plot = dff0 if mode == "Delta F / F0" else y_raw

    df_plot = pd.DataFrame({"Time_ms": t, "Signal": y_plot})
    if y_smooth is not None and mode == "Delta F / F0":
        df_plot["Smoothed_Signal"] = y_smooth

    base = alt.Chart(df_plot).encode(x=alt.X("Time_ms:Q", title="Time (ms)"))
    raw_line = base.mark_line(color="#94a3b8", opacity=0.6, strokeWidth=1).encode(
        y=alt.Y("Signal:Q", title="Signal Amplitude"),
        tooltip=["Time_ms:Q", "Signal:Q"]
    )

    layers = [raw_line]

    if method.startswith("Hybrid") and y_smooth is not None and mode == "Delta F / F0":
        smooth_line = base.mark_line(color="#0d9488", strokeWidth=2).encode(
            y="Smoothed_Signal:Q",
            tooltip=["Time_ms:Q", "Smoothed_Signal:Q"]
        )
        layers.append(smooth_line)

    if len(peaks) > 0:
        df_peaks = pd.DataFrame({"Time_ms": t[peaks], "Intensity": y_plot[peaks], "Peak_ID": np.arange(1, len(peaks)+1)})
        peak_marks = alt.Chart(df_peaks).mark_point(
            color="#e11d48", size=100, shape="triangle-down", fill="#e11d48"
        ).encode(
            x="Time_ms:Q",
            y="Intensity:Q",
            tooltip=["Peak_ID:N", "Time_ms:Q", "Intensity:Q"]
        )
        layers.append(peak_marks)

    chart = alt.layer(*layers).interactive().properties(
        width="container", height=420, title="Interactive Calcium Transient Plot (Zoom & Pan Enabled)"
    )
    return chart

def plot_single_peak_inspector(results, dff0, baseline, metrics_df, peak_id, theme):
    """Generate detailed single-peak deep-dive diagram showing F0, rise time, decay time, tau, and FWHM."""
    if metrics_df is None or len(metrics_df) == 0:
        return None

    row = metrics_df[metrics_df["Peak_ID"] == peak_id].iloc[0]
    p_idx = int(row["Peak Index"])
    t = results["t"]
    y_raw = results["y_signal"]
    y_smooth = results["y_smooth"] if results["y_smooth"] is not None else y_raw

    p_time = row["Time (ms)"]
    mask = (t >= p_time - 250) & (t <= p_time + 600)
    t_sub = t[mask]
    y_raw_sub = y_raw[mask]
    dff0_sub = dff0[mask]
    y_smooth_sub = y_smooth[mask]

    if theme == "Dark":
        bg_color = "#0e1117"
        card_color = "#161b22"
        text_color = "#fafafa"
        spine_color = "#30363d"
        grid_color = "#30363d"
    else:
        bg_color = "#ffffff"
        card_color = "#f8fafc"
        text_color = "#0f172a"
        spine_color = "#cbd5e1"
        grid_color = "#e2e8f0"

    fig, ax = plt.subplots(figsize=(10, 5), dpi=140)
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(card_color)

    ax.plot(t_sub, dff0_sub, color="#94a3b8", alpha=0.4, label="ΔF / F0 Local Trace", linewidth=1.2)
    ax.plot(t_sub, y_smooth_sub, color="#0d9488", linewidth=2.2, label="Smoothed Curve")
    ax.plot(p_time, dff0[p_idx], "o", color="#e11d48", markersize=9, label=f"Peak #{peak_id} Max")

    if pd.notna(row["Rise Time T10-90 (ms)"]):
        ax.axvspan(p_time - row["Rise Time T10-90 (ms)"], p_time, color="#2ecc71", alpha=0.2, label="Rise T10-90")

    if pd.notna(row["Decay Time T50 (ms)"]):
        ax.axvspan(p_time, p_time + row["Decay Time T50 (ms)"], color="#e74c3c", alpha=0.15, label="Decay T50")

    ax.set_title(f"Peak #{peak_id} Kinetic Profile  |  Time: {p_time:.1f} ms  |  dF/F0: {row['dF/F0 Peak']:.3f}",
                 color=text_color, fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Time (ms)", color=text_color, fontsize=10, fontweight=400)
    ax.set_ylabel("ΔF / F0", color=text_color, fontsize=10, fontweight=400)
    ax.tick_params(colors=text_color, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color(spine_color)
    ax.grid(True, alpha=0.3, color=grid_color, linestyle="--")
    ax.legend(loc="upper right", facecolor=bg_color, edgecolor=spine_color, labelcolor=text_color, fontsize=9)
    fig.tight_layout()
    return fig

# ──────────────────────────────────────────────
# Session State Initialization
# ──────────────────────────────────────────────
def reset_analysis_state():
    """Clear analysis state variables."""
    st.session_state.y_raw = None
    st.session_state.df_raw = None
    st.session_state.filename = None
    st.session_state.time_col = None
    st.session_state.signal_cols = []
    st.session_state.current_roi = None
    st.session_state.results = None
    st.session_state.metrics_df = None
    st.session_state.global_stats = None
    st.session_state.glossary_df = None
    st.session_state.baseline = None
    st.session_state.dff0 = None

defaults = {
    "y_raw": None,
    "df_raw": None,
    "filename": None,
    "time_col": None,
    "signal_cols": [],
    "current_roi": None,
    "results": None,
    "metrics_df": None,
    "global_stats": None,
    "glossary_df": None,
    "baseline": None,
    "dff0": None,
    "theme": "Light",
    "viz_engine": "Matplotlib (High-DPI)",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ──────────────────────────────────────────────
# Sidebar Controls & Configuration
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔬 Calcium Peak Analyzer")
    st.caption("v2.5 PRO • Scientific Signal Suite")

    # 1. Data Input Expander
    with st.expander("📁 Data Source & Input", expanded=True):
        input_mode = st.radio("Select Data Source", ["Upload CSV File", "Load Sample Dataset"], horizontal=True)
        
        if input_mode == "Load Sample Dataset":
            if st.button("✨ Load Synthetic Calcium Data", type="primary", width="stretch"):
                df_sample, y_sample = generate_sample_data()
                st.session_state.y_raw = y_sample
                st.session_state.df_raw = df_sample
                st.session_state.signal_cols = ["Calcium_Signal"]
                st.session_state.current_roi = "Calcium_Signal"
                st.session_state.time_col = "Time_ms"
                st.session_state.filename = "Synthetic_Calcium_Transients.csv"
                st.session_state.results = None
                st.session_state.metrics_df = None
                st.session_state.global_stats = None
                st.session_state.glossary_df = None
                st.success("Loaded Synthetic Calcium Transient Dataset!")

        else:
            uploaded_file = st.file_uploader(
                "Upload Signal CSV",
                type=["csv"],
                help="CSV with intensity values."
            )

            if uploaded_file is None:
                if st.session_state.filename is not None and st.session_state.filename != "Synthetic_Calcium_Transients.csv":
                    reset_analysis_state()
                    st.info("File cleared.")
            elif uploaded_file.name != st.session_state.filename:
                try:
                    df, time_col, signal_cols = CalciumSignalProcessor.parse_csv(uploaded_file)
                    st.session_state.df_raw = df
                    st.session_state.time_col = time_col
                    st.session_state.signal_cols = signal_cols
                    st.session_state.current_roi = signal_cols[0] if signal_cols else None
                    st.session_state.filename = uploaded_file.name
                    st.session_state.y_raw = df[st.session_state.current_roi].values.astype(float) if st.session_state.current_roi else None
                    st.session_state.results = None
                    st.session_state.metrics_df = None
                    st.session_state.global_stats = None
                    st.session_state.glossary_df = None
                    st.success(f"Loaded: {uploaded_file.name}")
                except Exception as e:
                    st.error(f"Failed to parse CSV: {e}")

        if st.session_state.df_raw is not None and len(st.session_state.signal_cols) > 1:
            st.session_state.current_roi = st.selectbox("Select Signal / ROI", st.session_state.signal_cols)
            if st.session_state.current_roi:
                st.session_state.y_raw = st.session_state.df_raw[st.session_state.current_roi].values.astype(float)

        if st.session_state.y_raw is not None:
            st.caption(f"Active File: **{st.session_state.filename}**")
            st.caption(f"Total Samples: **{len(st.session_state.y_raw):,}**")

    # 2. Baseline & Method Expander
    with st.expander("📉 Baseline & Display Mode", expanded=True):
        base_method = st.selectbox(
            "Baseline F0 Method",
            ["Rolling Percentile", "Local Minimum", "Constant Minimum"],
            index=0
        )
        base_window = st.slider("Baseline Window (frames)", 10, 500, 100, step=10)
        trace_mode = st.radio("Display Trace Mode", ["Delta F / F0", "Raw Intensity F(t)"], horizontal=True)

    # 3. Detection Algorithm & Tuning
    with st.expander("⚙️ Detection Algorithm & Parameters", expanded=True):
        method = st.selectbox(
            "Detection Method",
            ["Hybrid (Smooth + Refine)", "Direct (Raw)"],
            index=0,
            help="Hybrid uses Savitzky-Golay filtering to detect peak locations, then refines on raw signal."
        )

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            prominence = st.number_input("Prominence", min_value=0.001, max_value=1000.0, value=0.03, step=0.005, format="%.3f")
        with col_p2:
            min_distance = st.number_input("Min Dist (frames)", min_value=1, max_value=2000, value=50, step=5)

        if method == "Hybrid (Smooth + Refine)":
            smooth_window = st.slider("SG Window (odd)", 5, 51, 11, step=2, help="Savitzky-Golay window size")
        else:
            smooth_window = 11

        dt = st.number_input("Time Step dt (ms/frame)", min_value=0.1, max_value=2000.0, value=10.0, step=1.0, format="%.1f")

    # 4. Visual & Rendering Options
    with st.expander("🎨 Display & Themes", expanded=False):
        theme = st.radio("App Palette Theme", ["Light", "Dark"], horizontal=True)
        st.session_state.theme = theme
        viz_engine = st.radio("Plotting Engine", ["Matplotlib (High-DPI)", "Altair (Interactive Zoom)"])
        st.session_state.viz_engine = viz_engine

    # Action Button
    st.markdown("<br>", unsafe_allow_html=True)
    run_analysis = st.button("🚀 Run Signal Analysis", type="primary", width="stretch",
                             disabled=st.session_state.y_raw is None)

    if run_analysis and st.session_state.y_raw is not None:
        with st.spinner("Processing signal transients..."):
            y_raw = st.session_state.y_raw
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

            st.session_state.baseline = baseline
            st.session_state.dff0 = dff0
            st.session_state.results = results
            st.session_state.metrics_df = metrics_df
            st.session_state.global_stats = global_stats
            st.session_state.glossary_df = CalciumSignalProcessor.get_glossary()
            st.session_state.trace_mode = trace_mode
            
        st.toast("Peak Analysis Completed!", icon="✅")

    # Export Section
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("📥 Export Results & Reports", expanded=st.session_state.metrics_df is not None):
        if st.session_state.metrics_df is not None:
            df_trace = pd.DataFrame({
                "Time (ms)": st.session_state.results["t"],
                "Raw Intensity F(t)": st.session_state.y_raw,
                "Baseline F0(t)": st.session_state.baseline,
                "Delta F / F0": st.session_state.dff0
            })
            excel_bytes = create_excel_download(
                st.session_state.metrics_df,
                st.session_state.global_stats,
                st.session_state.glossary_df,
                df_trace=df_trace
            )
            st.download_button(
                label="📥 Download Excel Report (.xlsx)",
                data=excel_bytes,
                file_name=f"Calcium_Peak_Metrics_{st.session_state.filename}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch"
            )
            
            csv_bytes = st.session_state.metrics_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📄 Download Metrics CSV",
                data=csv_bytes,
                file_name="Peak_Metrics.csv",
                mime="text/csv",
                width="stretch"
            )
        else:
            st.info("Run analysis to unlock report downloads.")

# ──────────────────────────────────────────────
# Main Application Dashboard
# ──────────────────────────────────────────────

st.title("🔬 Calcium Signal Analysis Suite (Vibe Edition)")
st.caption("Automated peak detection, dynamic baseline estimation, sub-sample transient kinetics, and per-peak visual diagnostics.")

if st.session_state.y_raw is None:
    st.info("👈 **Getting Started:** Select **Upload CSV File** or click **Load Sample Dataset** in the sidebar to begin.")
    
    with st.container(border=True):
        st.subheader("💡 Key Capabilities")
        st.markdown(r"""
        - **Savitzky-Golay Hybrid Peak Detection:** Combines noise reduction with raw peak position refinement.
        - **Kinetic Parameter Extraction:** Automatic computation of baseline $F_0$, fractional change $\Delta F / F_0$, 10–90% rise time, 50% decay time, single-exponential decay time constant $\tau$, and AUC.
        - **Interactive Deep-Dive Inspector:** Zoom into individual peak morphologies with automated overlay markers.
        - **Publication Export:** Export multi-sheet formatted Excel reports and high-DPI scientific figures.
        """)

else:
    if st.session_state.results is None:
        with st.spinner("Initial analysis running..."):
            y_raw = st.session_state.y_raw
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

            st.session_state.baseline = baseline
            st.session_state.dff0 = dff0
            st.session_state.results = results
            st.session_state.metrics_df = metrics_df
            st.session_state.global_stats = global_stats
            st.session_state.glossary_df = CalciumSignalProcessor.get_glossary()
            st.session_state.trace_mode = trace_mode

    gs = st.session_state.global_stats
    if gs is not None:
        kpi_cols = st.columns(6)
        with kpi_cols[0]:
            with st.container(border=True):
                st.metric("Total Peaks", f"{gs['Total Peaks']}", help=f"Duration: {gs['Total Duration (s)']} s")
        with kpi_cols[1]:
            with st.container(border=True):
                st.metric("Frequency", f"{gs['Frequency (Hz)']:.2f} Hz", help="Transients per second")
        with kpi_cols[2]:
            with st.container(border=True):
                st.metric("Mean dF/F0", f"{gs['Mean Amplitude (dF/F0)']:.2f}", help="Fractional increase")
        with kpi_cols[3]:
            with st.container(border=True):
                st.metric("Mean Rise Time", f"{gs['Mean Rise Time T10-90 (ms)']:.1f} ms", help="10% to 90% rise")
        with kpi_cols[4]:
            with st.container(border=True):
                st.metric("Mean Decay Tau", f"{gs['Mean Decay Tau (ms)']:.1f} ms", help="Exponential decay constant")
        with kpi_cols[5]:
            with st.container(border=True):
                st.metric("Rhythmicity (CV)", f"{gs['Rhythmicity Index (CV of IEI)']:.3f}", help="Coefficient of Variation of IEI")

    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Signal & Peak Detection",
        "📈 Metrics & Distributions",
        "🔬 Peak Morphological Inspector",
        "📖 Method & Documentation"
    ])

    # TAB 1
    with tab1:
        st.subheader("📊 Full Time-Series Transient Visualization")
        
        if st.session_state.results is not None:
            if st.session_state.viz_engine == "Altair (Interactive Zoom)":
                chart = plot_altair(st.session_state.results, st.session_state.dff0, st.session_state.trace_mode, method)
                st.altair_chart(chart, width="stretch")
            else:
                fig = plot_matplotlib(
                    st.session_state.results, st.session_state.dff0, st.session_state.baseline, 
                    st.session_state.trace_mode, method, st.session_state.theme,
                    current_roi=st.session_state.current_roi or "Signal"
                )
                st.pyplot(fig, width="stretch")
                plt.close(fig)

        st.caption("💡 **Tip:** Adjust algorithm parameters in the sidebar and click **Run Signal Analysis** to update peak locations.")

    # TAB 2
    with tab2:
        st.subheader("📋 Comprehensive Peak Data & Kinetics")
        
        df_metrics = st.session_state.metrics_df
        if df_metrics is not None and len(df_metrics) > 0:
            df_show = df_metrics.copy()
            for col in df_show.columns:
                if df_show[col].dtype == float:
                    df_show[col] = df_show[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "—")

            st.dataframe(
                df_show,
                width="stretch",
                hide_index=True,
                height=320
            )

            st.subheader("📊 Metric Distributions")
            col_d1, col_d2, col_d3 = st.columns(3)

            with col_d1:
                st.markdown("##### Amplitude (dF/F0)")
                dff_vals = df_metrics["dF/F0 Peak"].dropna()
                if len(dff_vals) > 0:
                    fig_dff, ax_dff = plt.subplots(figsize=(4, 3), dpi=100)
                    ax_dff.hist(dff_vals, bins=max(5, len(dff_vals)//2), color="#0d9488", edgecolor="white", alpha=0.8)
                    ax_dff.set_xlabel("dF/F0 Peak")
                    ax_dff.set_ylabel("Count")
                    ax_dff.grid(True, alpha=0.2)
                    fig_dff.tight_layout()
                    st.pyplot(fig_dff)
                    plt.close(fig_dff)

            with col_d2:
                st.markdown("##### Rise Time T10-90 (ms)")
                rise_vals = df_metrics["Rise Time T10-90 (ms)"].dropna()
                if len(rise_vals) > 0:
                    fig_rise, ax_rise = plt.subplots(figsize=(4, 3), dpi=100)
                    ax_rise.hist(rise_vals, bins=max(5, len(rise_vals)//2), color="#6366f1", edgecolor="white", alpha=0.8)
                    ax_rise.set_xlabel("Rise Time T10-90 (ms)")
                    ax_rise.set_ylabel("Count")
                    ax_rise.grid(True, alpha=0.2)
                    fig_rise.tight_layout()
                    st.pyplot(fig_rise)
                    plt.close(fig_rise)

            with col_d3:
                st.markdown("##### Decay Tau (ms)")
                decay_vals = df_metrics["Decay Tau (ms)"].dropna()
                if len(decay_vals) > 0:
                    fig_decay, ax_decay = plt.subplots(figsize=(4, 3), dpi=100)
                    ax_decay.hist(decay_vals, bins=max(5, len(decay_vals)//2), color="#f59e0b", edgecolor="white", alpha=0.8)
                    ax_decay.set_xlabel("Decay Tau (ms)")
                    ax_decay.set_ylabel("Count")
                    ax_decay.grid(True, alpha=0.2)
                    fig_decay.tight_layout()
                    st.pyplot(fig_decay)
                    plt.close(fig_decay)
        else:
            st.warning("No peaks detected with current parameter threshold.")

    # TAB 3
    with tab3:
        st.subheader("🔬 Individual Peak Deep-Dive Inspector")
        
        df_metrics = st.session_state.metrics_df
        if df_metrics is not None and len(df_metrics) > 0:
            col_sel, col_info = st.columns([1, 2])
            
            with col_sel:
                peak_list = list(df_metrics["Peak_ID"].values)
                selected_peak_id = st.selectbox("Select Peak to Inspect", peak_list, index=0)
                
                p_row = df_metrics[df_metrics["Peak_ID"] == selected_peak_id].iloc[0]
                
                # Format strings safely outside f-string specifiers
                time_str = f"{p_row['Time (ms)']:.1f}" if pd.notna(p_row['Time (ms)']) else "—"
                raw_str = f"{p_row['Peak Raw Intensity']:.2f}" if pd.notna(p_row['Peak Raw Intensity']) else "—"
                base_str = f"{p_row['Baseline F0']:.2f}" if pd.notna(p_row['Baseline F0']) else "—"
                dff_str = f"{p_row['dF/F0 Peak']:.4f}" if pd.notna(p_row['dF/F0 Peak']) else "—"
                rise_str = f"{p_row['Rise Time T10-90 (ms)']:.1f}" if pd.notna(p_row['Rise Time T10-90 (ms)']) else "—"
                decay_str = f"{p_row['Decay Time T50 (ms)']:.1f}" if pd.notna(p_row['Decay Time T50 (ms)']) else "—"
                tau_str = f"{p_row['Decay Tau (ms)']:.1f}" if pd.notna(p_row['Decay Tau (ms)']) else "—"
                auc_str = f"{p_row['AUC (dF/F0 * s)']:.4f}" if pd.notna(p_row['AUC (dF/F0 * s)']) else "—"

                with st.container(border=True):
                    st.markdown(f"#### Peak #{selected_peak_id} Summary")
                    st.markdown(f"""
                    - **Time:** {time_str} ms
                    - **Raw Intensity:** {raw_str}
                    - **Baseline ($F_0$):** {base_str}
                    - **dF/F0 Peak:** {dff_str}
                    - **Rise Time (T10-90):** {rise_str} ms
                    - **Half-Decay (T50):** {decay_str} ms
                    - **Decay Tau ($\tau$):** {tau_str} ms
                    - **Area Under Curve (AUC):** {auc_str}
                    """)

            with col_info:
                fig_insp = plot_single_peak_inspector(
                    st.session_state.results, st.session_state.dff0, st.session_state.baseline, 
                    df_metrics, selected_peak_id, st.session_state.theme
                )
                if fig_insp is not None:
                    st.pyplot(fig_insp, width="stretch")
                    plt.close(fig_insp)
        else:
            st.info("No detected peaks to inspect.")

    # TAB 4
    with tab4:
        st.subheader("📖 Algorithm & Mathematical Documentation")
        
        st.markdown(r"""
        ### Peak Detection Algorithms

        #### 1. Dynamic Baseline Estimation ($F_0$)
        - **Rolling Percentile:** Computes moving quantile over sliding baseline window to track resting fluorescence.
        - **Local Minimum / Constant Minimum:** Tracks lower envelopes for signal baseline subtraction.

        #### 2. Hybrid Peak Detection (Savitzky-Golay Smooth + Raw Refinement)
        1. **Noise Filtering:** Applies a 3rd-order Savitzky-Golay polynomial filter over a local window of length $W$.
        2. **Candidate Peak Identification:** Detects peaks on the smoothed curve using minimum prominence $P$ and distance $D$.
        3. **Raw Peak Refinement:** Pinpoints maximum raw intensity position around candidates.

        ---

        ### Kinetic Metrics Glossary & Equations

        - **Fractional Fluorescence ($\Delta F / F_0$):**
          $$\frac{\Delta F}{F_0} = \frac{F(t) - F_0(t)}{F_0(t)}$$

        - **Sub-Sample Rise Time ($T_{10-90}$):**
          Linear interpolation for sub-frame duration from $10\%$ to $90\%$ of peak amplitude.

        - **Single-Exponential Decay Constant ($\tau_{\text{decay}}$):**
          Non-linear curve fit: $F(t) = A \cdot e^{-t/\tau} + C$.

        - **Rhythmicity Index ($CV_{\text{IEI}}$):**
          Coefficient of variation of Inter-Event Intervals ($SD / \text{Mean}$).
        """)

        with st.expander("📖 View Full Metrics Glossary Table"):
            st.dataframe(st.session_state.glossary_df, width="stretch", hide_index=True)

# streamlit_peak_analyzer.py
"""
Calcium Signal Peak Analyzer (Pro)
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
import base64
from datetime import datetime
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

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

# Enable direct mouse selection and copying of all metric labels, values, and cards
st.markdown("""
<style>
[data-testid="stMetricValue"], 
[data-testid="stMetricLabel"], 
[data-testid="stMetricDelta"], 
[data-testid="stMetric"], 
div[data-testid="stMetric"] * {
    user-select: text !important;
    -webkit-user-select: text !important;
    -moz-user-select: text !important;
    -ms-user-select: text !important;
    cursor: text !important;
}

/* Fix popover body width and scrolling so switching tabs never resizes or closes the popover */
div[data-testid="stPopoverBody"],
div[data-testid="stPopoverContent"],
.stPopoverContent {
    width: 640px !important;
    min-width: 640px !important;
    max-width: 92vw !important;
}
div[data-testid="stPopoverBody"] pre,
div[data-testid="stPopoverContent"] pre,
.stPopoverContent pre {
    overflow-x: auto !important;
    white-space: pre !important;
}
</style>
""", unsafe_allow_html=True)

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

def create_excel_download(df_metrics, global_stats, glossary, df_trace=None, params_dict=None):
    """Create a professionally formatted multi-sheet Excel file with openpyxl styling and audit trail."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # 1. Analysis Parameters & Audit Trail
        if params_dict:
            df_params = pd.DataFrame(list(params_dict.items()), columns=["Parameter / Setting", "Configured Value"])
            df_params.to_excel(writer, sheet_name="Analysis Parameters", index=False)

        # 2. Global Statistics
        pd.DataFrame([global_stats]).to_excel(writer, sheet_name="Global Statistics", index=False)

        # 3. Per-Peak Metrics
        df_metrics.to_excel(writer, sheet_name="Per-Peak Metrics", index=False)

        # 4. Signal Traces
        if df_trace is not None:
            df_trace.to_excel(writer, sheet_name="Signal Traces", index=False)

        # 5. Metrics Glossary
        glossary.to_excel(writer, sheet_name="Metrics Glossary", index=False)

        # Professional openpyxl formatting
        header_fill = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        cell_font = Font(name="Segoe UI", size=10)
        border_thin = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            try:
                ws.views.sheetView[0].showGridLines = True
            except Exception:
                pass
            ws.freeze_panes = "A2"

            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            for col in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    if cell.row > 1:
                        cell.font = cell_font
                        cell.border = border_thin
                        if isinstance(cell.value, float):
                            cell.number_format = "0.000" if abs(cell.value) < 1.0 else "0.00"
                    val_str = str(cell.value or "")
                    if len(val_str) > max_len:
                        max_len = len(val_str)
                ws.column_dimensions[col_letter].width = max(max_len + 4, 15)

    return output.getvalue()

def create_html_report(df_metrics, global_stats, params_dict, results, dff0, baseline, mode, method):
    """Generate a self-contained, publication-quality scientific HTML report printable to PDF."""
    # 1. Render Overview Figure to base64
    fig_overview = plot_matplotlib(results, dff0, baseline, mode, method, "Light", current_roi="Signal")
    buf_ov = BytesIO()
    fig_overview.savefig(buf_ov, format="png", dpi=140, bbox_inches="tight")
    img_ov_b64 = base64.b64encode(buf_ov.getvalue()).decode("utf-8")
    plt.close(fig_overview)

    # 2. Render 3 Histograms to base64
    fig_dist, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(11, 3.2), dpi=130)
    fig_dist.patch.set_facecolor("#ffffff")
    
    dff_vals = df_metrics["dF/F0 Peak"].dropna()
    if len(dff_vals) > 0:
        ax1.hist(dff_vals, bins=max(5, len(dff_vals)//2), color="#0d9488", edgecolor="white", alpha=0.85)
    ax1.set_title("Amplitude (dF/F0)", fontsize=10, fontweight="bold", color="#0f172a")
    ax1.set_xlabel("dF/F0 Peak", fontsize=9)
    ax1.grid(True, alpha=0.2, linestyle="--")

    rise_vals = df_metrics["Rise Time T10-90 (ms)"].dropna()
    if len(rise_vals) > 0:
        ax2.hist(rise_vals, bins=max(5, len(rise_vals)//2), color="#6366f1", edgecolor="white", alpha=0.85)
    ax2.set_title("Rise Time T10-90 (ms)", fontsize=10, fontweight="bold", color="#0f172a")
    ax2.set_xlabel("Rise Time (ms)", fontsize=9)
    ax2.grid(True, alpha=0.2, linestyle="--")

    decay_vals = df_metrics["Decay Tau (ms)"].dropna()
    if len(decay_vals) > 0:
        ax3.hist(decay_vals, bins=max(5, len(decay_vals)//2), color="#f59e0b", edgecolor="white", alpha=0.85)
    ax3.set_title("Decay Tau (ms)", fontsize=10, fontweight="bold", color="#0f172a")
    ax3.set_xlabel("Decay Tau (ms)", fontsize=9)
    ax3.grid(True, alpha=0.2, linestyle="--")

    fig_dist.tight_layout()
    buf_dist = BytesIO()
    fig_dist.savefig(buf_dist, format="png", dpi=130, bbox_inches="tight")
    img_dist_b64 = base64.b64encode(buf_dist.getvalue()).decode("utf-8")
    plt.close(fig_dist)

    # Top peaks table rows (first 15 peaks)
    top_peaks = df_metrics.head(15)
    peaks_rows_html = ""
    for _, row in top_peaks.iterrows():
        rise_val = f"{row['Rise Time T10-90 (ms)']:.1f}" if pd.notna(row['Rise Time T10-90 (ms)']) else "—"
        decay_val = f"{row['Decay Time T50 (ms)']:.1f}" if pd.notna(row['Decay Time T50 (ms)']) else "—"
        tau_val = f"{row['Decay Tau (ms)']:.1f}" if pd.notna(row['Decay Tau (ms)']) else "—"
        auc_val = f"{row['AUC (dF/F0 * s)']:.4f}" if pd.notna(row['AUC (dF/F0 * s)']) else "—"
        peaks_rows_html += f"""
        <tr>
            <td>#{int(row['Peak_ID'])}</td>
            <td>{row['Time (ms)']:.1f}</td>
            <td>{row['Baseline F0']:.2f}</td>
            <td><strong>{row['dF/F0 Peak']:.4f}</strong></td>
            <td>{rise_val}</td>
            <td>{decay_val}</td>
            <td>{tau_val}</td>
            <td>{auc_val}</td>
        </tr>
        """

    # Parameters table rows
    params_rows_html = ""
    if params_dict:
        for k, v in params_dict.items():
            params_rows_html += f"<tr><td class='param-name'>{k}</td><td class='param-val'>{v}</td></tr>"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Calcium Signal Analysis Report - {params_dict.get('Source File', 'Analysis')}</title>
<style>
    @page {{
        size: A4 portrait;
        margin: 15mm 15mm 15mm 15mm;
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #1e293b;
        background-color: #f8fafc;
        margin: 0;
        padding: 20px;
    }}
    .report-container {{
        max-width: 960px;
        margin: 0 auto;
        background: #ffffff;
        padding: 32px 40px;
        border-radius: 10px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
    }}
    .header-bar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 2px solid #0f766e;
        padding-bottom: 16px;
        margin-bottom: 24px;
    }}
    .header-title {{
        margin: 0;
        color: #0f766e;
        font-size: 24px;
        font-weight: 700;
    }}
    .header-subtitle {{
        color: #64748b;
        font-size: 13px;
        margin-top: 4px;
    }}
    .print-btn {{
        background: #0f766e;
        color: #ffffff;
        border: none;
        padding: 10px 18px;
        border-radius: 6px;
        font-weight: 600;
        cursor: pointer;
        font-size: 13px;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        transition: background 0.2s;
    }}
    .print-btn:hover {{
        background: #115e59;
    }}
    .kpi-grid {{
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 12px;
        margin-bottom: 28px;
    }}
    .kpi-card {{
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 10px;
        text-align: center;
    }}
    .kpi-label {{
        font-size: 11px;
        color: #64748b;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 6px;
    }}
    .kpi-value {{
        font-size: 17px;
        font-weight: 700;
        color: #0f172a;
    }}
    .section-title {{
        font-size: 16px;
        font-weight: 700;
        color: #0f172a;
        margin: 24px 0 12px 0;
        padding-bottom: 6px;
        border-bottom: 1px solid #e2e8f0;
    }}
    .chart-img {{
        width: 100%;
        height: auto;
        border-radius: 6px;
        border: 1px solid #e2e8f0;
        margin-bottom: 20px;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
        margin-bottom: 20px;
    }}
    th {{
        background-color: #0f766e;
        color: #ffffff;
        text-align: left;
        padding: 8px 10px;
        font-weight: 600;
    }}
    td {{
        padding: 7px 10px;
        border-bottom: 1px solid #f1f5f9;
    }}
    tr:nth-child(even) {{
        background-color: #f8fafc;
    }}
    .param-table {{
        margin-bottom: 24px;
    }}
    .param-name {{
        font-weight: 600;
        color: #334155;
        width: 35%;
    }}
    .footer {{
        margin-top: 32px;
        border-top: 1px solid #e2e8f0;
        padding-top: 12px;
        font-size: 11px;
        color: #94a3b8;
        text-align: center;
    }}
    @media print {{
        body {{
            background: #ffffff;
            padding: 0;
        }}
        .report-container {{
            box-shadow: none;
            padding: 0;
            max-width: 100%;
        }}
        .print-btn {{
            display: none !important;
        }}
        .page-break {{
            page-break-before: always;
        }}
    }}
</style>
</head>
<body>
<div class="report-container">
    <div class="header-bar">
        <div>
            <h1 class="header-title">🔬 Calcium Transient Analysis Report</h1>
            <div class="header-subtitle">Dataset: <strong>{params_dict.get('Source File', 'Signal')}</strong> | Generated: {params_dict.get('Analysis Date & Time', '')}</div>
        </div>
        <button class="print-btn" onclick="window.print()">🖨️ Print / Save as PDF</button>
    </div>

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">Total Peaks</div>
            <div class="kpi-value">{global_stats['Total Peaks']}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Frequency</div>
            <div class="kpi-value">{global_stats['Frequency (Hz)']:.2f} Hz</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Mean dF/F0</div>
            <div class="kpi-value">{global_stats['Mean Amplitude (dF/F0)']:.2f}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Rise T10-90</div>
            <div class="kpi-value">{global_stats['Mean Rise Time T10-90 (ms)']:.1f} ms</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Decay Tau (&tau;)</div>
            <div class="kpi-value">{global_stats['Mean Decay Tau (ms)']:.1f} ms</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Rhythmicity (CV)</div>
            <div class="kpi-value">{global_stats['Rhythmicity Index (CV of IEI)']:.3f}</div>
        </div>
    </div>

    <div class="section-title">📊 Calcium Transient Detection & Overview</div>
    <img class="chart-img" src="data:image/png;base64,{img_ov_b64}" alt="Calcium Signal Peak Detection">

    <div class="section-title">📈 Kinetic Parameter Distributions</div>
    <img class="chart-img" src="data:image/png;base64,{img_dist_b64}" alt="Kinetic Parameter Distributions">

    <div class="section-title">⚙️ Analysis Parameters & Experimental Settings</div>
    <table class="param-table">
        <thead>
            <tr><th>Parameter / Configuration</th><th>Value</th></tr>
        </thead>
        <tbody>
            {params_rows_html}
        </tbody>
    </table>

    <div class="section-title">📋 Detected Peaks & Kinetic Metrics (Top 15 Peaks)</div>
    <table>
        <thead>
            <tr>
                <th>Peak</th>
                <th>Time (ms)</th>
                <th>Baseline F0</th>
                <th>dF/F0 Peak</th>
                <th>Rise T10-90 (ms)</th>
                <th>Decay T50 (ms)</th>
                <th>Decay &tau; (ms)</th>
                <th>AUC (dF/F0&middot;s)</th>
            </tr>
        </thead>
        <tbody>
            {peaks_rows_html}
        </tbody>
    </table>
    <div style="font-size: 11px; color: #64748b; margin-top: -12px; margin-bottom: 20px;">
        *Showing {min(15, len(df_metrics))} of {len(df_metrics)} detected peaks. Complete records are included in the Excel export.
    </div>

    <div class="footer">
        Generated by Calcium Signal Peak Analyzer Pro &bull; Standardized &Delta;F/F0 Kinetics &bull; Open in any browser & print/save to PDF via Ctrl+P.
    </div>
</div>
</body>
</html>
"""
    return html_content.encode("utf-8")

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
    st.session_state.last_analyzed_params = None
    st.session_state.analyzed_trace_mode = "Delta F / F0"
    st.session_state.analyzed_detection_method = "Hybrid (Smooth + Refine)"
    st.session_state.fig_overview = None
    st.session_state.chart_overview = None
    st.session_state.last_rendered_theme = None
    st.session_state.last_rendered_engine = None

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
    "last_analyzed_params": None,
    "analyzed_trace_mode": "Delta F / F0",
    "analyzed_detection_method": "Hybrid (Smooth + Refine)",
    "fig_overview": None,
    "chart_overview": None,
    "last_rendered_theme": None,
    "last_rendered_engine": None,
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
    st.caption("v1 PRO • Scientific Signal Suite")

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
                st.session_state.last_analyzed_params = None
                st.session_state.fig_overview = None
                st.session_state.chart_overview = None
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
                    st.session_state.last_analyzed_params = None
                    st.session_state.fig_overview = None
                    st.session_state.chart_overview = None
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
        base_window = st.slider("Baseline Window (frames)", 10, 1000, 400, step=10)
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
            prominence = st.number_input("Prominence", min_value=0.001, max_value=1000.0, value=0.10, step=0.005, format="%.3f")
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

    current_params = (base_method, base_window, trace_mode, method, prominence, min_distance, smooth_window, dt, st.session_state.current_roi)

    # Automatically run initial analysis upon file upload or sample dataset load
    # so all KPI cards, charts, and export reports are instantly available on the very first render
    if st.session_state.y_raw is not None and st.session_state.results is None:
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
        st.session_state.analyzed_trace_mode = trace_mode
        st.session_state.analyzed_detection_method = method
        st.session_state.last_analyzed_params = current_params
        st.session_state.fig_overview = None
        st.session_state.chart_overview = None

    is_params_changed = (st.session_state.results is not None) and (st.session_state.last_analyzed_params != current_params)

    st.markdown("<br>", unsafe_allow_html=True)

    # Dynamic button label based on parameter modification state (Zero Layout Shift)
    button_label = "🔄 Apply Changed Parameters" if is_params_changed else "🚀 Re-Run Signal Analysis"
    run_analysis = st.button(button_label, type="primary", width="stretch", disabled=st.session_state.y_raw is None)

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
            st.session_state.analyzed_trace_mode = trace_mode
            st.session_state.analyzed_detection_method = method
            st.session_state.last_analyzed_params = current_params
            st.session_state.fig_overview = None  # Force figure re-render for new analysis
            st.session_state.chart_overview = None
            
        st.toast("Peak Analysis Completed!", icon="✅")
        st.rerun()

    # Export Section
    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("📥 Export Results & Reports", expanded=st.session_state.metrics_df is not None):
        if st.session_state.metrics_df is not None:
            if is_params_changed:
                st.warning("⚠️ **Pending Parameter Changes:** You modified analysis settings above. Click **🔄 Apply Changed Parameters** to update the analysis before downloading reports.")
            else:
                df_trace = pd.DataFrame({
                    "Time (ms)": st.session_state.results["t"],
                    "Raw Intensity F(t)": st.session_state.y_raw,
                    "Baseline F0(t)": st.session_state.baseline,
                    "Delta F / F0": st.session_state.dff0
                })

                clean_filename = st.session_state.filename or "Calcium_Signal.csv"
                params_dict = {
                    "Analysis Date & Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Source File": clean_filename,
                    "Total Samples": len(st.session_state.y_raw) if st.session_state.y_raw is not None else 0,
                    "Time Step dt (ms)": dt,
                    "Sampling Rate (FPS)": round(1000.0 / dt, 2) if dt > 0 else 0,
                    "Baseline Method": base_method,
                    "Baseline Window (frames)": base_window,
                    "Baseline Window (ms)": round(base_window * dt, 1),
                    "Display Trace Mode": trace_mode,
                    "Peak Detection Method": method,
                    "Prominence Threshold": prominence,
                    "Min Distance (frames)": min_distance,
                    "Min Distance (ms)": round(min_distance * dt, 1),
                    "Savitzky-Golay Window (pts)": smooth_window if method.startswith("Hybrid") else "N/A"
                }

                excel_bytes = create_excel_download(
                    st.session_state.metrics_df,
                    st.session_state.global_stats,
                    st.session_state.glossary_df,
                    df_trace=df_trace,
                    params_dict=params_dict
                )
                st.download_button(
                    label="📥 Download Excel Report (.xlsx)",
                    data=excel_bytes,
                    file_name=f"Calcium_Peak_Metrics_{clean_filename}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                    help="Stylized multi-sheet Excel report with analysis parameters, statistics, per-peak kinetics, traces, and glossary."
                )

                html_bytes = create_html_report(
                    st.session_state.metrics_df,
                    st.session_state.global_stats,
                    params_dict,
                    st.session_state.results,
                    st.session_state.dff0,
                    st.session_state.baseline,
                    st.session_state.analyzed_trace_mode,
                    st.session_state.analyzed_detection_method
                )
                st.download_button(
                    label="📄 Download Visual Report (.html / PDF)",
                    data=html_bytes,
                    file_name=f"Calcium_Report_{clean_filename}.html",
                    mime="text/html",
                    width="stretch",
                    help="Interactive standalone scientific report with embedded high-resolution figures. Open in browser to view or print/save as PDF."
                )
        else:
            st.info("Upload a CSV file or load sample dataset to unlock report downloads.")

# ──────────────────────────────────────────────
# Main Application Dashboard
# ──────────────────────────────────────────────

st.title("🔬 Calcium Signal Analysis Suite")

# Permanent reserved status slot (Zero Layout Shift)
status_slot = st.empty()

if st.session_state.y_raw is None:
    status_slot.caption("👈 Select **Upload CSV File** or click **Load Sample Dataset** in the sidebar to begin.")
    
    with st.container(border=True):
        st.subheader("💡 Key Capabilities")
        st.markdown(r"""
        - **Savitzky-Golay Hybrid Peak Detection:** Combines noise reduction with raw peak position refinement.
        - **Kinetic Parameter Extraction:** Automatic computation of baseline $F_0$, fractional change $\Delta F / F_0$, 10–90% rise time, 50% decay time, single-exponential decay time constant $\tau$, and AUC.
        - **Interactive Deep-Dive Inspector:** Zoom into individual peak morphologies with automated overlay markers.
        - **Publication Export:** Export multi-sheet formatted Excel reports and high-DPI scientific figures.
        """)

else:
    # Evaluate parameter modification state
    current_params = (base_method, base_window, trace_mode, method, prominence, min_distance, smooth_window, dt, st.session_state.current_roi)
    is_params_changed = (st.session_state.results is not None) and (st.session_state.last_analyzed_params != current_params)

    # In-place status update inside reserved slot (Yellow Warning Background)
    if is_params_changed:
        status_slot.warning("⚠️ **Pending Parameter Changes:** You modified analysis settings in the sidebar. Click **🔄 Apply Changed Parameters** in the sidebar to update peak detection, metrics, and all charts.")
    else:
        status_slot.caption("🟢 **Status:** Peak detection and metrics are up-to-date with current settings.")

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
            st.session_state.analyzed_trace_mode = trace_mode
            st.session_state.analyzed_detection_method = method
            st.session_state.last_analyzed_params = current_params
            st.session_state.fig_overview = None
            st.session_state.chart_overview = None

    gs = st.session_state.global_stats
    if gs is not None:
        current_file = st.session_state.filename or "Calcium_Signal"
        #current_roi = st.session_state.current_roi or "ROI"

        stats_kv_text = (
            f"--- Calcium Signal Global Statistics ---\n"
            f"File: {current_file}\n"
            f"Total Peaks: {gs['Total Peaks']}\n"
            f"Total Duration: {gs['Total Duration (s)']} s\n"
            f"Frequency: {gs['Frequency (Hz)']:.3f} Hz ({gs.get('Frequency (events/min)', 0):.2f} events/min)\n"
            f"Mean Amplitude (dF/F0): {gs['Mean Amplitude (dF/F0)']:.4f}\n"
            f"Mean Rise Time T10-90: {gs['Mean Rise Time T10-90 (ms)']:.2f} ms\n"
            f"Mean Decay T50: {gs.get('Mean Decay T50 (ms)', 0):.2f} ms\n"
            f"Mean Decay Tau: {gs['Mean Decay Tau (ms)']:.2f} ms\n"
            f"Mean Inter-Event Interval: {gs.get('Mean Inter-Event Interval (ms)', 0):.2f} ms\n"
            f"Median Inter-Event Interval: {gs.get('Median Inter-Event Interval (ms)', 0):.2f} ms\n"
            f"Rhythmicity (SD of IEI): {gs.get('Rhythmicity (SD of IEI ms)', 0):.2f} ms\n"
            f"Rhythmicity Index (CV of IEI): {gs['Rhythmicity Index (CV of IEI)']:.4f}"
        )

        stats_tsv_row_with_header = (
            "File\tTotal Peaks\tDuration (s)\tFrequency (Hz)\tFrequency (BPM)\tMean dF/F0\tMean Rise T10-90 (ms)\tMean Decay T50 (ms)\tMean Decay Tau (ms)\tMean IEI (ms)\tMedian IEI (ms)\tSD IEI (ms)\tCV IEI\n"
            f"{current_file}\t{gs['Total Peaks']}\t{gs['Total Duration (s)']}\t{gs['Frequency (Hz)']:.3f}\t{gs.get('Frequency (events/min)', 0):.2f}\t"
            f"{gs['Mean Amplitude (dF/F0)']:.4f}\t{gs['Mean Rise Time T10-90 (ms)']:.2f}\t{gs.get('Mean Decay T50 (ms)', 0):.2f}\t"
            f"{gs['Mean Decay Tau (ms)']:.2f}\t{gs.get('Mean Inter-Event Interval (ms)', 0):.2f}\t{gs.get('Median Inter-Event Interval (ms)', 0):.2f}\t"
            f"{gs.get('Rhythmicity (SD of IEI ms)', 0):.2f}\t{gs['Rhythmicity Index (CV of IEI)']:.4f}"
        )

        stats_tsv_row_no_header = (
            f"{current_file}\t{gs['Total Peaks']}\t{gs['Total Duration (s)']}\t{gs['Frequency (Hz)']:.3f}\t{gs.get('Frequency (events/min)', 0):.2f}\t"
            f"{gs['Mean Amplitude (dF/F0)']:.4f}\t{gs['Mean Rise Time T10-90 (ms)']:.2f}\t{gs.get('Mean Decay T50 (ms)', 0):.2f}\t"
            f"{gs['Mean Decay Tau (ms)']:.2f}\t{gs.get('Mean Inter-Event Interval (ms)', 0):.2f}\t{gs.get('Median Inter-Event Interval (ms)', 0):.2f}\t"
            f"{gs.get('Rhythmicity (SD of IEI ms)', 0):.2f}\t{gs['Rhythmicity Index (CV of IEI)']:.4f}"
        )

        stats_tsv_table = (
            f"Metric\tValue\n"
            f"Total Peaks (count)\t{gs['Total Peaks']}\n"
            f"Total Duration (s)\t{gs['Total Duration (s)']}\n"
            f"Frequency (Hz)\t{gs['Frequency (Hz)']:.3f}\n"
            f"Frequency (events/min)\t{gs.get('Frequency (events/min)', 0):.2f}\n"
            f"Mean Amplitude (dF/F0)\t{gs['Mean Amplitude (dF/F0)']:.4f}\n"
            f"Mean Rise Time T10-90 (ms)\t{gs['Mean Rise Time T10-90 (ms)']:.2f}\n"
            f"Mean Decay T50 (ms)\t{gs.get('Mean Decay T50 (ms)', 0):.2f}\n"
            f"Mean Decay Tau (ms)\t{gs['Mean Decay Tau (ms)']:.2f}\n"
            f"Mean Inter-Event Interval (ms)\t{gs.get('Mean Inter-Event Interval (ms)', 0):.2f}\n"
            f"Median Inter-Event Interval (ms)\t{gs.get('Median Inter-Event Interval (ms)', 0):.2f}\n"
            f"Rhythmicity (SD of IEI) (ms)\t{gs.get('Rhythmicity (SD of IEI ms)', 0):.2f}\n"
            f"Rhythmicity Index (CV of IEI) (ratio)\t{gs['Rhythmicity Index (CV of IEI)']:.4f}"
        )

        kpi_h1, kpi_h2 = st.columns([5, 1])
        with kpi_h1:
            st.markdown("#### 📊 Global Signal Statistics")
        with kpi_h2:
            with st.popover("📋 Copy Stats", width="stretch"):
                st.markdown("##### 📋 Copy Global Statistics")
                st.caption("Hover over any code box below and click the **copy icon** in the top-right corner:")
                tab_c1, tab_c2, tab_c3 = st.tabs(["📝 Text Summary", "📑 Excel Row", "📊 Excel Table"])
                with tab_c1:
                    st.caption("Plain text summary for reports, papers, or lab notebooks:")
                    st.code(stats_kv_text, language="text")
                with tab_c2:
                    st.markdown("**With Column Headers** *(for a new table / first row)*:")
                    st.code(stats_tsv_row_with_header, language="text")
                    st.markdown("**Without Headers — Values Only** *(paste as an additional row)*:")
                    st.code(stats_tsv_row_no_header, language="text")
                with tab_c3:
                    st.caption("Paste directly as 2 columns (Metric | Value):")
                    st.code(stats_tsv_table, language="text")

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
                if st.session_state.chart_overview is None or st.session_state.last_rendered_engine != st.session_state.viz_engine:
                    st.session_state.chart_overview = plot_altair(
                        st.session_state.results, st.session_state.dff0, 
                        st.session_state.analyzed_trace_mode, st.session_state.analyzed_detection_method
                    )
                    st.session_state.last_rendered_engine = st.session_state.viz_engine

                st.altair_chart(st.session_state.chart_overview, width="stretch")
            else:
                if (st.session_state.fig_overview is None or 
                    st.session_state.last_rendered_theme != st.session_state.theme or 
                    st.session_state.last_rendered_engine != st.session_state.viz_engine):
                    
                    st.session_state.fig_overview = plot_matplotlib(
                        st.session_state.results, st.session_state.dff0, st.session_state.baseline, 
                        st.session_state.analyzed_trace_mode, st.session_state.analyzed_detection_method, st.session_state.theme,
                        current_roi=st.session_state.current_roi or "Signal"
                    )
                    st.session_state.last_rendered_theme = st.session_state.theme
                    st.session_state.last_rendered_engine = st.session_state.viz_engine

                st.pyplot(st.session_state.fig_overview, width="stretch")

        st.caption("💡 **Tip:** Adjust algorithm parameters in the sidebar and click **Apply Parameter Changes** to update peak locations.")

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
        st.subheader("📖 Comprehensive Parameter Guide & Scientific Documentation")
        
        st.markdown(r"""
        This reference guide explains every analysis parameter, how adjusting it impacts peak detection, 
        and the mathematical formulas used by the literature-standard calculation engine.
        """)

        # Section 1: Parameter Tuning Guide
        with st.expander("🎛️ Complete Parameter Tuning Guide (What & How to Change)", expanded=True):
            st.markdown(r"""
            ### 1. Baseline Estimation Parameters

            #### **Baseline $F_0$ Method**
            - **What it does:** Selects the algorithm used to estimate local resting fluorescence $F_0(t)$ across your time-series.
            - **Options:**
              - `Rolling Percentile` **(Recommended):** Calculates a moving 10th percentile over a sliding window. Ignores upward transient spikes and tracks true baseline drift.
              - `Local Minimum:` Tracks the absolute minimum values in a sliding window. Highly sensitive to noise dips.
              - `Constant Minimum:` Sets $F_0$ as a single fixed baseline across the entire recording. Assumes zero baseline drift or photobleaching.
            - **Impact:** `Rolling Percentile` prevents baseline elevation caused by high-frequency firing bursts.

            #### **Baseline Window (frames)** ($W_{\text{base}}$)
            - **What it does:** The width of the sliding temporal window (in frames) over which resting fluorescence $F_0(t)$ is computed.
            - **Formula:** $F_0(t) = \text{Percentile}_{10}\left(F\left[t - \frac{W}{2} : t + \frac{W}{2}\right]\right)$
            - **How tuning affects detection:**
              - ⚠️ **Too Small (< 100 frames at 100 FPS / < 1s):** The baseline window climbs into transient peaks, artificially raising $F_0(t)$ and squishing peak amplitude $\Delta F / F_0$.
              - ✅ **Optimal (300 – 600 frames at 100 FPS / 3s – 6s):** Smoothly tracks slow photobleaching without climbing into calcium events.
              - ⚠️ **Too Large (> 1000 frames):** Lags behind fast baseline drift or illumination changes.

            #### **Display Trace Mode**
            - **What it does:** Toggles between fractional fluorescence change $\frac{\Delta F}{F_0}(t)$ and raw fluorescence $F(t)$.
            - **Formula:** $\frac{\Delta F}{F_0}(t) = \frac{F(t) - F_0(t)}{F_0(t)}$
            - **Impact:** $\Delta F / F_0$ normalizes for dye loading variations, making transient amplitudes directly comparable across different ROIs.

            ---

            ### 2. Peak Detection & Filtering Parameters

            #### **Detection Method**
            - **What it does:** Determines whether high-frequency noise smoothing is applied before identifying candidate peaks.
            - **Options:**
              - `Hybrid (Smooth + Refine)` **(Recommended):** Applies Savitzky-Golay polynomial filtering to detect candidate peak locations, then pinpoints raw peak amplitudes.
              - `Direct (Raw):` Searches for peaks directly on the raw un-smoothed signal.
            - **Impact:** `Hybrid` prevents high-frequency noise ripples from triggering false positive peak detections.

            #### **Prominence** ($P$)
            - **What it does:** The minimum vertical height a peak must extend above its surrounding baseline valleys.
            - **Formula:** $P_i = y_{\text{peak}} - \max\left(\min(y_{\text{left\_valley}}), \min(y_{\text{right\_valley}})\right)$
            - **How tuning affects detection:**
              - ⚠️ **Too Low (0.01 – 0.03 on $\Delta F/F_0$):** Detects minor noise ripples as false positive peaks.
              - ✅ **Optimal (0.08 – 0.12 on $\Delta F/F_0$):** Isolates genuine, high-confidence biological calcium transients.
              - ⚠️ **Too High (> 0.25):** Misses smaller, valid calcium events.

            #### **Min Distance (frames)** ($D_{\text{min}}$)
            - **What it does:** The minimum temporal spacing (in frames) required between consecutive peak detections.
            - **Impact:** Prevents double-counting multi-peaked noise ripples or split peaks within a single calcium event. Set $D_{\text{min}}$ slightly smaller than your shortest expected inter-event interval.

            #### **SG Window (odd integer)** ($W_{\text{SG}}$)
            - **What it does:** The frame length of the Savitzky-Golay smoothing polynomial filter (Hybrid method).
            - **Impact:** Higher values ($15–25$) provide stronger noise smoothing but may flatten fast peak spikes; lower values ($5–9$) preserve sharp transients.

            #### **Time Step dt (ms/frame)** ($\Delta t$)
            - **What it does:** The acquisition sampling interval in milliseconds per frame ($1 / \text{FPS} \times 1000$).
            - **Impact:** Converts frame indices to real-world units ($\text{ms}$, $\text{seconds}$, $\text{Hz}$). Used to compute transient duration, rise time, decay time constant $\tau$, and area under curve (AUC).
            """)

        # Section 2: Mathematical Formulas & Equations
        with st.expander("📐 Mathematical Formulas & Algorithm Equations", expanded=False):
            st.markdown(r"""
            ### 1. Savitzky-Golay Noise Smoothing
            Fits a local 3rd-degree polynomial $y(t) = a_0 + a_1 t + a_2 t^2 + a_3 t^3$ over a sliding window $W_{\text{SG}}$:
            $$S(t) = \sum_{i=-m}^{m} c_i \cdot F(t+i)$$
            where $c_i$ are convolution coefficients that preserve higher moments (peak height and width) better than simple moving averages.

            ---

            ### 2. Sub-Sample Linear Interpolation ($T_{10-90}$ Rise Time)
            To achieve sub-frame accuracy for fast transients, $10\%$ ($y_{10}$) and $90\%$ ($y_{90}$) amplitude threshold crossing times ($t_{10}$ and $t_{90}$) are computed via linear interpolation:
            $$t_{10} = t_1 + \frac{(y_{10} - y_1)(t_2 - t_1)}{y_2 - y_1}$$
            $$\text{Rise Time } T_{10-90} = t_{90} - t_{10}$$

            ---

            ### 3. Single-Exponential Decay Time Constant ($\tau_{\text{decay}}$)
            Fits an exponential decay curve to the post-peak signal segment:
            $$y(t) = A \cdot e^{-\frac{t - t_{\text{peak}}}{\tau}} + C$$
            **Neurophysiology Fallback:** If non-linear curve fitting fails due to signal noise, $\tau$ is robustly calculated from the half-decay time $T_{50}$:
            $$\tau_{\text{decay}} = \frac{T_{50}}{\ln(2)} \approx 1.4427 \times T_{50}$$

            ---

            ### 4. Area Under Curve (AUC)
            Trapezoidal integration of net transient amplitude from onset $t_{\text{onset}}$ to offset $t_{\text{offset}}$:
            $$\text{AUC} = \int_{t_{\text{onset}}}^{t_{\text{offset}}} \max\left(0, \frac{\Delta F}{F_0}(t) - y_{\text{base}}\right) dt$$

            ---

            ### 5. Rhythmicity Index ($CV_{\text{IEI}}$)
            Coefficient of Variation of Inter-Event Intervals ($\text{IEI} = t_{\text{peak}_{i+1}} - t_{\text{peak}_i}$):
            $$CV_{\text{IEI}} = \frac{\text{SD}(\text{IEI})}{\text{Mean}(\text{IEI})}$$
            - $CV \to 0$: Perfectly regular, metronomic firing.
            - $CV \approx 1$: Stochastic Poisson process.
            - $CV > 1$: Irregular / bursting activity patterns.
            """)

        # Section 3: Glossary Table
        with st.expander("📖 Metrics Glossary Table", expanded=False):
            st.dataframe(st.session_state.glossary_df, width="stretch", hide_index=True)

# 🔬 Calcium Signal Peak Analyzer (Pro)

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://calcium-peak-analysis.streamlit.app/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)

An interactive, publication-grade web application for the automated analysis, baseline normalization, peak detection, sub-sample kinetic parameter extraction, and reporting of calcium imaging and fluorescence transients ($F(t)$ and $\Delta F / F_0$).

🌐 **Live Cloud Application:** [https://calcium-peak-analysis.streamlit.app/](https://calcium-peak-analysis.streamlit.app/)

---

## 🌟 Key Highlights & Capabilities

### 1. 📁 Flexible Data Ingestion & Auto-Detection
* **Universal CSV Parsing:** Handles comma (`,`), semicolon (`;`), and tab (`\t`) delimiters automatically via Python CSV sniffing.
* **Automatic Acquisition Frame Rate (FPS) & $\Delta t$ Inference:** Recognizes timestamp columns (`Time`, `Time_(Frames)`, `sec`, `ms`, `t`) and automatically pre-populates your camera's acquisition frame rate and frame interval $\Delta t$.
* **Multi-ROI Selection:** Supports CSV files containing multiple region-of-interest (ROI) fluorescence columns with a 1-click dropdown switcher.
* **Instant Synthetic Signal Generator:** Built-in synthetic calcium transient simulator with baseline drift and Gaussian noise for demonstration and testing.

---

### 2. 🪄 Intelligent Auto-Tune & Biological Presets *(Optional Helper)*
Designed for users without signal processing expertise, this assistant automatically configures optimal algorithmic settings based on your camera FPS and cell preparation:
* **Empirical Noise Floor Detection:** Uses the Median Absolute Deviation (MAD) of successive frame differences to accurately isolate camera noise ($\sigma_{\text{noise}}$) without bias from transient spikes or photobleaching.
* **Calibrated Preparation Profiles:**
  * 🫀 **Cardiomyocytes:** Tuned for rhythmic cardiac contractions ($W_{\text{base}} \approx 3.5\text{s}$, refractory gap $\approx 350\text{ms}$, SG smoothing $\approx 110\text{ms}$).
  * 🧠 **Neurons (Fast Transients):** Tuned for sharp somatic action potential bursts ($W_{\text{base}} \approx 2.0\text{s}$, refractory gap $\approx 150\text{ms}$, SG smoothing $\approx 70\text{ms}$).
  * 🧫 **Astrocytes (Slow Waves):** Tuned for wide, multi-second propagating calcium waves ($W_{\text{base}} \approx 8.0\text{s}$, refractory gap $\approx 1.2\text{s}$, SG smoothing $\approx 250\text{ms}$).
  * 🔍 **Auto-Detect (General):** Balanced settings dynamically scaled to acquisition frame rate.
* **Theme-Adaptive Summary Card:** Displays active settings in both frame counts and physiological units (seconds/milliseconds) with high contrast in both Light and Dark modes.
* **Manual Override:** Sliders and number inputs remain fully interactive for manual fine-tuning.

---

### 3. 📉 Literature-Standard Baseline $F_0(t)$ & $\Delta F / F_0$
* **Dynamic Baseline Algorithms:**
  * **Rolling Percentile (Default):** Moving quantile over a window $W_{\text{base}}$, robust against transient spikes while tracking photobleaching.
  * **Local Minimum:** Moving-window minimum with light smoothing.
  * **Constant Minimum:** Trace-wide lowest percentile floor.
* **Normalization:** 
  $$\frac{\Delta F}{F_0}(t) = \frac{F(t) - F_0(t)}{F_0(t)}$$

---

### 4. ⚡ Savitzky-Golay Hybrid Peak Detection
* **High-Frequency Denoising:** 3rd-degree polynomial Savitzky-Golay filtering removes pixel noise without blunting peak height.
* **Dual-Stage Peak Refinement:** Identifies peak candidates on smoothed data to avoid false local maxima, then refines coordinates to the true absolute maximum on the raw signal trace.
* **Prominence & Distance Filtering:** Eliminates baseline noise fluctuations and respects biological refractory periods.

---

### 5. ⏱️ Sub-Sample Precision Kinetic Metrics
Extracts scientific transient properties with sub-frame linear interpolation:
* **Rise Time ($T_{10-90}$):** Sub-frame interval between 10% and 90% peak amplitude.
* **Half-Decay Time ($T_{50}$):** Duration from peak maximum down to 50% amplitude recovery.
* **Decay Time Constant ($\tau$):** Non-linear single-exponential curve fitting ($y(t) = A e^{-t/\tau} + C$) on normalized $\Delta F / F_0$ space, with robust neurophysiology fallback:
  $$\tau_{\text{decay}} \approx 1.4427 \times T_{50}$$
* **Area Under Curve (AUC):** Trapezoidal integration ($\Delta F / F_0 \cdot \text{s}$).
* **Frequency & Rhythmicity:** Event rate ($\text{Hz}$ and $\text{min}^{-1}$), Inter-Event Intervals (IEI), and Rhythmicity Index ($CV_{\text{IEI}}$).

---

### 6. 📊 4-Tab Interactive Analysis Dashboard
* **Tab 1: 📊 Full Time-Series Visualization:** Dual visualization engines:
  * **Matplotlib (High-DPI):** Zero-flicker, content-addressed PNG byte caching. Unrelated clicks and slider changes never flash the screen.
  * **Altair:** Interactive browser-native pan and zoom.
* **Tab 2: 📈 Metrics & Distributions:** Interactive per-peak kinetic table plus three publication histograms ($\Delta F / F_0$, Rise Time $T_{10-90}$, Decay $\tau$).
* **Tab 3: 🔬 Peak Morphological Inspector:** Deep-dive into individual peaks with local window zoom and shaded kinetic regions ($T_{10-90}$ and $T_{50}$).
* **Tab 4: 📖 Scientific Method & Documentation:** Detailed parameter guide, mathematical formulas, and full kinetic glossary.

---

### 7. 📋 1-Click Clipboard Copy Suite
* Direct mouse text-selection enabled across all executive KPI metric cards (`Total Peaks`, `Frequency`, `Mean dF/F0`, `Rise Time`, `Decay T50`, `Rhythmicity`).
* **`📋 Copy Stats` Popover:** Stabilized 1-click clipboard export supporting:
  * **Formatted Text Summary** (for laboratory notebooks and presentations).
  * **Excel Row with Headers** (for aggregating experimental datasets).
  * **Excel Row (Values Only)** (for appending rows into existing spreadsheets).
  * **2-Column TSV Table** (for direct pasting into Word/PowerPoint/Sheets).

---

### 8. 📥 Dual Publication-Grade Export Suite
* **Enhanced Multi-Sheet Excel Workbook (`.xlsx`):**
  * Built with `openpyxl`, styled with dark teal headers (`#0F766E`), frozen top panes, and auto-adjusted column widths.
  * Includes dedicated sheets: **Analysis Parameters & Audit Trail**, **Global Statistics**, **Per-Peak Metrics**, an optional user-toggled **Signal Traces** sheet (`[x] Include raw signal traces sheet`), and **Metrics Glossary**.
* **Printable Standalone Visual Report (`.html` / PDF):**
  * Zero-dependency standalone HTML file with base64-embedded high-resolution charts.
  * Includes executive KPI grid, audit parameters, top peak kinetics, and a 1-click print-to-PDF button styled via `@media print`.
* **Integrity Guard:** Download buttons are locked behind an alert if parameters have been modified without clicking `🔄 Apply Changed Parameters`, ensuring exported files never contain mismatched settings.

---

## 🚀 Getting Started

### Access Online (No Installation Needed)
Launch the application directly in your browser:  
👉 **[https://calcium-peak-analysis.streamlit.app/](https://calcium-peak-analysis.streamlit.app/)**

---

### Local Installation & Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/bernas-estevam97/calcium-peak-analysis.git
   cd calcium-peak-analysis
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the Streamlit app:**
   ```bash
   streamlit run streamlit_peak_analyzer.py
   ```

5. **(Optional) Launch the Desktop GUI application:**
   ```bash
   python peak_analyzer.py
   ```

---

## 🧪 Running Tests

Verify engine algorithms, noise estimation, and auto-tuning profiles:
```bash
python tests/test_processor.py
```

---

## 📁 Repository Structure

```
calcium-peak-analysis/
├── README.md                      # [THIS FILE] Project documentation & quickstart
├── PROJECT_STATE.md               # Detailed architecture, release notes & status log
├── requirements.txt               # Production dependencies
│
├── streamlit_peak_analyzer.py     # 🏆 Streamlit Web Application (4-Tab Suite)
├── peak_analyzer.py               # 🖥️ CustomTkinter Desktop Launcher
│
├── src/calcium_peak_analyzer/
│   ├── core/
│   │   └── calcium_processor.py   # Core scientific calculation engine (NumPy, SciPy, Pandas)
│   ├── gui/
│   │   └── peak_analyzer_app.py   # CustomTkinter Desktop GUI
│   └── assets/                    # Application icons
│
└── tests/
    └── test_processor.py          # Unit test verification suite
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

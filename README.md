# Calcium Signal Peak Analyzer

This project provides a Streamlit web app for analyzing calcium imaging or fluorescence signal traces. The app loads a CSV file, detects peaks in the signal, computes peak-related metrics, and exports the results to Excel.

## What the app does

The Streamlit app in [streamlit_peak_analyzer.py](streamlit_peak_analyzer.py) can:

- Load a CSV file containing one or more columns of numeric data
- Use the last column as the signal intensity trace
- Detect peaks using either:
  - Hybrid smoothing + refinement
  - Direct raw-signal detection
- Compute metrics such as:
  - peak timing
  - peak intensity
  - baseline estimate
  - dF/F0
  - rise time
  - decay time
  - FWHM
  - global frequency and rhythmicity statistics
- Display results interactively and export them as an Excel report

## Requirements

Install the required Python packages with:

```bash
pip install -r requirements.txt
```

## Run the app

You can use this application in two ways:

### 1. Run locally

From the project folder, run:

```bash
streamlit run streamlit_peak_analyzer.py
```

The app will open in your browser.

### 2. Run on Streamlit Cloud

This application is also designed to be deployed and run on Streamlit Cloud. To do so, connect this repository to a Streamlit Cloud app and point it to [streamlit_peak_analyzer.py](streamlit_peak_analyzer.py) as the main script. Streamlit Cloud will install the dependencies from [requirements.txt](requirements.txt) automatically.

## Input file format

The app expects a CSV file with the following behavior:

- Any number of columns is allowed
- The last column is used as the signal intensity values
- Header rows are optional; the app will attempt to read the data automatically

Example structure:

```csv
0,1.2
1,1.5
2,1.8
3,1.7
```

## Analysis options

In the sidebar, you can adjust:

- detection method
- peak prominence
- minimum peak distance
- smoothing window (for hybrid mode)
- time step per frame
- light/dark theme

After changing parameters, click the Run Analysis button to update the plot and metrics.

## Output

Once analysis is complete, the app displays:

- a plot of the detected peaks
- global statistics
- a table of per-peak metrics
- a metrics glossary
- an Excel download option for the full report

## Notes

- The Hybrid method is usually better for noisy signals because it smooths the trace before detecting peaks.
- The Direct method is faster and may be preferable for cleaner signals.
- Make sure to click Run Analysis after changing settings.

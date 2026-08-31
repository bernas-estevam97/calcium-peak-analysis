"""
Calcium Signal Peak Analyzer Desktop Application
------------------------------------------------
A professional CustomTkinter application for calcium transient analysis in 
fluorescence imaging signals (GCaMP, Fura-2, Fluo-4, etc.).

Features:
- Dynamically parses single or multi-ROI CSV datasets.
- Dynamic baseline estimation (Rolling Percentile, Local Min, Constant Min).
- Delta F / F0 normalization and visualization.
- Hybrid Savitzky-Golay peak detection with sub-frame kinetic extraction 
  (T10-90 rise time, T50 decay time, tau exponential decay constant, AUC, max slope).
- Multi-Tab Desktop Interface:
    1. Signal Trace & Interactive Peak Editing (Matplotlib Navigation Toolbar + Click Edit)
    2. Individual Transient Inspector (Zoomed transient, rise/decay markers, fitted tau)
    3. Live Per-Peak Metrics Table
    4. Population Kinetics & Summary Dashboard (KPI Cards + 4-Panel Distribution Histograms)
- Auto-Parameter Estimation based on noise std deviation (MAD).
- Sidebar height expanded down to theme toggle switch.
- Multi-sheet Excel workbook export and publication-ready 300 DPI image exporter.
"""

import sys
import os
import ctypes
import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import logging

from calcium_peak_analyzer.core.calcium_processor import CalciumSignalProcessor

# --- App Styling Configuration ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class PeakAnalyzerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Explicitly register Windows Taskbar AppUserModelID to display custom icon on Taskbar
        if sys.platform.startswith("win"):
            try:
                myappid = "antigravity.calcium_peak_analyzer.desktop.2.5"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        self.title("Calcium Signal Peak Analyzer — Professional Edition")
        self.geometry("1350x880")
        self.minsize(1100, 700)

        # Apply Window Title Bar and Taskbar Icons
        self.set_app_icon()

        # Intercept close window event
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def set_app_icon(self):
        """Loads and sets the custom calcium icon for window title bar and taskbar."""
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
        ico_path = os.path.join(assets_dir, "app_icon.ico")
        png_path = os.path.join(assets_dir, "app_icon.png")

        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        if os.path.exists(png_path):
            try:
                img = Image.open(png_path)
                photo = ImageTk.PhotoImage(img)
                self.iconphoto(False, photo)
                self._icon_photo_ref = photo
            except Exception:
                pass

        # --- Internal Data State ---
        self.df_raw = None
        self.filepath = None
        self.time_col = None
        self.signal_cols = []
        self.current_roi = None
        
        self.y_raw = None
        self.baseline = None
        self.dff0 = None
        self.dt = 10.0 # ms/frame
        
        self.results = None
        self.metrics_df = None
        self.global_stats = None
        
        self.interactive_click_mode = False
        self.click_cid = None

        self.setup_ui()

    def setup_ui(self):
        # Configure Main Window Grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # -----------------------------------------------------------------
        # 1. Left Sidebar (Controls & Settings)
        # -----------------------------------------------------------------
        self.sidebar_frame = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        # Grid Configuration for Sidebar:
        # Row 0: Logo
        # Row 1: Subtitle
        # Row 2: Controls Scrollable Container (WEIGHT=1 -> EXPANDS TO FILL ENTIRE HEIGHT ABOVE THEME SWITCH)
        # Row 3: Theme Switch (WEIGHT=0 -> Anchored cleanly at bottom)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        self.sidebar_frame.grid_rowconfigure(0, weight=0)
        self.sidebar_frame.grid_rowconfigure(1, weight=0)
        self.sidebar_frame.grid_rowconfigure(2, weight=1)
        self.sidebar_frame.grid_rowconfigure(3, weight=0)

        # Header Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="🔬 Ca²⁺ Peak Analyzer", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=15, pady=(15, 2), sticky="w")
        
        self.sub_logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="Calcium Signal Kinetics & Rhythmicity",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color="gray"
        )
        self.sub_logo_label.grid(row=1, column=0, padx=15, pady=(0, 8), sticky="w")

        # Scrollable Control Panel inside Sidebar (STRETCHES VERTICALLY TO FILL SPACE)
        self.controls_scroll = ctk.CTkScrollableFrame(self.sidebar_frame, corner_radius=6)
        self.controls_scroll.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="nsew")
        self.controls_scroll.grid_columnconfigure(0, weight=1)

        # --- Section A: File & ROI Selection ---
        self.lbl_sec_file = ctk.CTkLabel(self.controls_scroll, text="1. Data Source", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_sec_file.pack(anchor="w", padx=10, pady=(10, 5))

        self.load_btn = ctk.CTkButton(
            self.controls_scroll, 
            text="📁 Load CSV File", 
            command=self.load_csv,
            fg_color="#1f6aa5", 
            hover_color="#144870"
        )
        self.load_btn.pack(fill="x", padx=10, pady=4)

        self.file_label = ctk.CTkLabel(
            self.controls_scroll, 
            text="No file loaded", 
            font=ctk.CTkFont(size=11, slant="italic"),
            wraplength=260
        )
        self.file_label.pack(anchor="w", padx=10, pady=(0, 5))

        # ROI Selector Dropdown
        self.lbl_roi = ctk.CTkLabel(self.controls_scroll, text="Select Signal / ROI:", font=ctk.CTkFont(size=12))
        self.lbl_roi.pack(anchor="w", padx=10, pady=(5, 0))
        self.roi_dropdown = ctk.CTkOptionMenu(self.controls_scroll, values=["None"], command=self.on_roi_change)
        self.roi_dropdown.pack(fill="x", padx=10, pady=4)

        # Trace Display Mode
        self.lbl_trace_mode = ctk.CTkLabel(self.controls_scroll, text="Signal Display Mode:", font=ctk.CTkFont(size=12))
        self.lbl_trace_mode.pack(anchor="w", padx=10, pady=(5, 0))
        self.trace_mode_var = ctk.StringVar(value="Delta F / F0")
        self.trace_mode_menu = ctk.CTkOptionMenu(
            self.controls_scroll,
            values=["Delta F / F0", "Raw Intensity F(t)"],
            variable=self.trace_mode_var,
            command=self.update_analysis
        )
        self.trace_mode_menu.pack(fill="x", padx=10, pady=4)

        # --- Section B: Baseline Parameters ---
        self.lbl_sec_base = ctk.CTkLabel(self.controls_scroll, text="2. Baseline Estimation (F₀)", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_sec_base.pack(anchor="w", padx=10, pady=(15, 5))

        self.baseline_method_var = ctk.StringVar(value="Rolling Percentile")
        self.baseline_dropdown = ctk.CTkOptionMenu(
            self.controls_scroll,
            values=["Rolling Percentile", "Local Minimum", "Constant Minimum"],
            variable=self.baseline_method_var,
            command=self.update_analysis
        )
        self.baseline_dropdown.pack(fill="x", padx=10, pady=4)

        # Baseline Window slider
        self.lbl_base_win = ctk.CTkLabel(self.controls_scroll, text="Baseline Window (frames):", font=ctk.CTkFont(size=11))
        self.lbl_base_win.pack(anchor="w", padx=10, pady=(4, 0))
        self.base_win_slider = ctk.CTkSlider(self.controls_scroll, from_=10, to=500, number_of_steps=490, command=self.update_analysis_debounce)
        self.base_win_slider.set(100)
        self.base_win_slider.pack(fill="x", padx=10, pady=2)

        # --- Section C: Peak Detection Parameters ---
        self.lbl_sec_peak = ctk.CTkLabel(self.controls_scroll, text="3. Peak Detection", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_sec_peak.pack(anchor="w", padx=10, pady=(15, 5))

        self.method_var = ctk.StringVar(value="Hybrid (Smooth + Refine)")
        self.method_dropdown = ctk.CTkOptionMenu(
            self.controls_scroll,
            values=["Hybrid (Smooth + Refine)", "Direct (Raw)"],
            variable=self.method_var,
            command=self.update_analysis
        )
        self.method_dropdown.pack(fill="x", padx=10, pady=4)

        # Prominence
        self.lbl_prom = ctk.CTkLabel(self.controls_scroll, text="Prominence (dF/F0 or count):", font=ctk.CTkFont(size=11))
        self.lbl_prom.pack(anchor="w", padx=10, pady=(4, 0))
        
        self.prom_frame = ctk.CTkFrame(self.controls_scroll, fg_color="transparent")
        self.prom_frame.pack(fill="x", padx=10, pady=2)
        self.prom_slider = ctk.CTkSlider(self.prom_frame, from_=0.01, to=2.0, command=self.on_prom_slider)
        self.prom_slider.set(0.10)
        self.prom_slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.prom_entry = ctk.CTkEntry(self.prom_frame, width=55)
        self.prom_entry.insert(0, "0.10")
        self.prom_entry.pack(side="right")
        self.prom_entry.bind("<Return>", self.on_prom_entry)

        # Min Distance
        self.lbl_dist = ctk.CTkLabel(self.controls_scroll, text="Min Distance (frames):", font=ctk.CTkFont(size=11))
        self.lbl_dist.pack(anchor="w", padx=10, pady=(4, 0))
        
        self.dist_frame = ctk.CTkFrame(self.controls_scroll, fg_color="transparent")
        self.dist_frame.pack(fill="x", padx=10, pady=2)
        self.dist_slider = ctk.CTkSlider(self.dist_frame, from_=5, to=500, number_of_steps=495, command=self.on_dist_slider)
        self.dist_slider.set(50)
        self.dist_slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.dist_entry = ctk.CTkEntry(self.dist_frame, width=55)
        self.dist_entry.insert(0, "50")
        self.dist_entry.pack(side="right")
        self.dist_entry.bind("<Return>", self.on_dist_entry)

        # Smooth Window
        self.lbl_win = ctk.CTkLabel(self.controls_scroll, text="Smooth Window (odd):", font=ctk.CTkFont(size=11))
        self.lbl_win.pack(anchor="w", padx=10, pady=(4, 0))
        
        self.win_frame = ctk.CTkFrame(self.controls_scroll, fg_color="transparent")
        self.win_frame.pack(fill="x", padx=10, pady=2)
        self.win_slider = ctk.CTkSlider(self.win_frame, from_=5, to=51, number_of_steps=23, command=self.on_win_slider)
        self.win_slider.set(11)
        self.win_slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.win_entry = ctk.CTkEntry(self.win_frame, width=55)
        self.win_entry.insert(0, "11")
        self.win_entry.pack(side="right")
        self.win_entry.bind("<Return>", self.on_win_entry)

        # Time step (dt)
        self.lbl_dt = ctk.CTkLabel(self.controls_scroll, text="Time Step Δt (ms/frame):", font=ctk.CTkFont(size=11))
        self.lbl_dt.pack(anchor="w", padx=10, pady=(4, 0))
        self.dt_entry = ctk.CTkEntry(self.controls_scroll)
        self.dt_entry.insert(0, "10.0")
        self.dt_entry.pack(fill="x", padx=10, pady=2)
        self.dt_entry.bind("<Return>", self.update_analysis)

        # Auto-Estimate Parameters Button
        self.auto_btn = ctk.CTkButton(
            self.controls_scroll, 
            text="⚡ Auto-Estimate Thresholds", 
            command=self.auto_estimate_params,
            fg_color="#d35400", 
            hover_color="#e67e22"
        )
        self.auto_btn.pack(fill="x", padx=10, pady=(12, 5))

        # --- Section D: Export ---
        self.lbl_sec_exp = ctk.CTkLabel(self.controls_scroll, text="4. Export Results", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_sec_exp.pack(anchor="w", padx=10, pady=(15, 5))

        self.export_excel_btn = ctk.CTkButton(
            self.controls_scroll, 
            text="📊 Export Excel Report", 
            command=self.export_excel,
            fg_color="#27ae60", 
            hover_color="#2ecc71"
        )
        self.export_excel_btn.pack(fill="x", padx=10, pady=4)

        self.export_img_btn = ctk.CTkButton(
            self.controls_scroll, 
            text="📷 Save High-Res Figures", 
            command=self.export_figures,
            fg_color="#8e44ad", 
            hover_color="#9b59b6"
        )
        self.export_img_btn.pack(fill="x", padx=10, pady=(4, 15))

        # Dark/Light Theme Switch anchored cleanly at bottom of sidebar
        self.appearance_mode_var = ctk.StringVar(value="Dark")
        self.theme_switch = ctk.CTkSwitch(
            self.sidebar_frame, 
            text="Dark Mode", 
            command=self.toggle_theme,
            variable=self.appearance_mode_var, 
            onvalue="Dark", 
            offvalue="Light"
        )
        self.theme_switch.grid(row=3, column=0, padx=20, pady=(10, 15), sticky="w")

        # -----------------------------------------------------------------
        # 2. Right Workspace Panel (Multi-Tab Architecture)
        # -----------------------------------------------------------------
        self.workspace_frame = ctk.CTkFrame(self, corner_radius=0)
        self.workspace_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.workspace_frame.grid_columnconfigure(0, weight=1)
        self.workspace_frame.grid_rowconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self.workspace_frame)
        self.tabview.grid(row=0, column=0, sticky="nsew")

        # Create 4 Tabs
        self.tab_overview = self.tabview.add("📈 Signal & Peaks Overview")
        self.tab_inspector = self.tabview.add("🔍 Peak Inspector")
        self.tab_table = self.tabview.add("📋 Per-Peak Metrics Table")
        self.tab_summary = self.tabview.add("📊 Population Summary & Kinetics")

        self.setup_tab_overview()
        self.setup_tab_inspector()
        self.setup_tab_table()
        self.setup_tab_summary()

    # -----------------------------------------------------------------
    # Tab 1: Overview Setup
    # -----------------------------------------------------------------
    def setup_tab_overview(self):
        self.tab_overview.grid_columnconfigure(0, weight=1)
        self.tab_overview.grid_rowconfigure(1, weight=1)

        # Top Control Bar on Overview Tab
        self.ov_top_bar = ctk.CTkFrame(self.tab_overview, fg_color="transparent")
        self.ov_top_bar.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        self.click_edit_btn = ctk.CTkButton(
            self.ov_top_bar, 
            text="👆 Toggle Interactive Peak Add/Delete Mode: OFF",
            fg_color="#444444", 
            hover_color="#555555",
            command=self.toggle_interactive_click_mode
        )
        self.click_edit_btn.pack(side="left", padx=5)

        self.status_label = ctk.CTkLabel(
            self.ov_top_bar, 
            text="Ready. Load a CSV dataset to begin.", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#3498db"
        )
        self.status_label.pack(side="right", padx=10)

        # Matplotlib Container Frame
        self.plot_container = ctk.CTkFrame(self.tab_overview)
        self.plot_container.grid(row=1, column=0, sticky="nsew")
        self.plot_container.grid_columnconfigure(0, weight=1)
        self.plot_container.grid_rowconfigure(0, weight=1)

        self.fig_ov, self.ax_ov = plt.subplots(figsize=(9, 5), dpi=100)
        self.canvas_ov = FigureCanvasTkAgg(self.fig_ov, master=self.plot_container)
        self.canvas_ov.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        # Add Matplotlib Navigation Toolbar
        self.toolbar_frame = ctk.CTkFrame(self.tab_overview, height=40, fg_color="transparent")
        self.toolbar_frame.grid(row=2, column=0, sticky="ew")
        self.toolbar_ov = NavigationToolbar2Tk(self.canvas_ov, self.toolbar_frame)
        self.toolbar_ov.update()

        self.apply_plot_style(self.fig_ov, self.ax_ov)

    # -----------------------------------------------------------------
    # Tab 2: Inspector Setup
    # -----------------------------------------------------------------
    def setup_tab_inspector(self):
        self.tab_inspector.grid_columnconfigure(1, weight=1)
        self.tab_inspector.grid_rowconfigure(0, weight=1)

        # Left Control Panel in Inspector Tab
        self.insp_left = ctk.CTkFrame(self.tab_inspector, width=280)
        self.insp_left.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.insp_left.grid_columnconfigure(0, weight=1)

        self.lbl_insp_title = ctk.CTkLabel(self.insp_left, text="Peak Detail Inspector", font=ctk.CTkFont(size=15, weight="bold"))
        self.lbl_insp_title.pack(padx=10, pady=(10, 5), anchor="w")

        self.lbl_select_peak = ctk.CTkLabel(self.insp_left, text="Select Peak ID:")
        self.lbl_select_peak.pack(padx=10, pady=(5, 0), anchor="w")

        self.peak_select_dropdown = ctk.CTkOptionMenu(self.insp_left, values=["None"], command=self.update_inspector_plot)
        self.peak_select_dropdown.pack(fill="x", padx=10, pady=5)

        # Metrics Card inside Inspector
        self.insp_card = ctk.CTkFrame(self.insp_left, fg_color="#1e1e1e" if self.appearance_mode_var.get() == "Dark" else "#f0f0f0")
        self.insp_card.pack(fill="both", expand=True, padx=10, pady=10)

        self.insp_card_lbl = ctk.CTkLabel(
            self.insp_card, 
            text="Select a peak to inspect detailed kinetic parameters.", 
            justify="left", 
            anchor="nw",
            font=ctk.CTkFont(size=12)
        )
        self.insp_card_lbl.pack(fill="both", expand=True, padx=10, pady=10)

        # Inspector Plot Right Panel
        self.insp_right = ctk.CTkFrame(self.tab_inspector)
        self.insp_right.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.insp_right.grid_columnconfigure(0, weight=1)
        self.insp_right.grid_rowconfigure(0, weight=1)

        self.fig_insp, self.ax_insp = plt.subplots(figsize=(7, 5), dpi=100)
        self.canvas_insp = FigureCanvasTkAgg(self.fig_insp, master=self.insp_right)
        self.canvas_insp.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.apply_plot_style(self.fig_insp, self.ax_insp)

    # -----------------------------------------------------------------
    # Tab 3: Data Table Setup
    # -----------------------------------------------------------------
    def setup_tab_table(self):
        self.tab_table.grid_columnconfigure(0, weight=1)
        self.tab_table.grid_rowconfigure(0, weight=1)

        # Treeview Container
        self.table_frame = ctk.CTkFrame(self.tab_table)
        self.table_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.table_frame.grid_columnconfigure(0, weight=1)
        self.table_frame.grid_rowconfigure(0, weight=1)

        # Scrollbars
        self.tree_scroll_y = ttk.Scrollbar(self.table_frame, orient="vertical")
        self.tree_scroll_x = ttk.Scrollbar(self.table_frame, orient="horizontal")

        self.tree = ttk.Treeview(
            self.table_frame, 
            yscrollcommand=self.tree_scroll_y.set, 
            xscrollcommand=self.tree_scroll_x.set,
            selectmode="browse"
        )
        self.tree_scroll_y.config(command=self.tree.yview)
        self.tree_scroll_x.config(command=self.tree.xview)

        self.tree_scroll_y.grid(row=0, column=1, sticky="ns")
        self.tree_scroll_x.grid(row=1, column=0, sticky="ew")
        self.tree.grid(row=0, column=0, sticky="nsew")

    # -----------------------------------------------------------------
    # Tab 4: Summary & Distributions Setup
    # -----------------------------------------------------------------
    def setup_tab_summary(self):
        self.tab_summary.grid_columnconfigure(0, weight=1)
        self.tab_summary.grid_rowconfigure(1, weight=1)

        # Top KPI Cards Container
        self.kpi_frame = ctk.CTkFrame(self.tab_summary, height=90, fg_color="transparent")
        self.kpi_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        self.kpi_labels = {}
        kpi_keys = ["Total Peaks", "Frequency (Hz)", "Mean Rise T10-90 (ms)", "Mean Decay Tau (ms)", "Rhythmicity (CV)"]
        for idx, key in enumerate(kpi_keys):
            card = ctk.CTkFrame(self.kpi_frame, corner_radius=8)
            card.pack(side="left", fill="both", expand=True, padx=5)
            
            lbl_title = ctk.CTkLabel(card, text=key, font=ctk.CTkFont(size=11), text_color="gray")
            lbl_title.pack(pady=(8, 2))
            lbl_val = ctk.CTkLabel(card, text="—", font=ctk.CTkFont(size=16, weight="bold"))
            lbl_val.pack(pady=(0, 8))
            self.kpi_labels[key] = lbl_val

        # 4-Panel Histogram Plot
        self.hist_frame = ctk.CTkFrame(self.tab_summary)
        self.hist_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.hist_frame.grid_columnconfigure(0, weight=1)
        self.hist_frame.grid_rowconfigure(0, weight=1)

        self.fig_hist, self.axes_hist = plt.subplots(2, 2, figsize=(8, 5), dpi=100)
        self.canvas_hist = FigureCanvasTkAgg(self.fig_hist, master=self.hist_frame)
        self.canvas_hist.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        for ax in self.axes_hist.flatten():
            self.apply_plot_style(self.fig_hist, ax)

    # -----------------------------------------------------------------
    # Data Loading & ROI Handling
    # -----------------------------------------------------------------
    def load_csv(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not filepath:
            return

        try:
            df, time_col, signal_cols = CalciumSignalProcessor.parse_csv(filepath)
            self.df_raw = df
            self.filepath = filepath
            self.time_col = time_col
            self.signal_cols = signal_cols
            
            self.file_label.configure(text=f"{os.path.basename(filepath)} ({len(df):,} samples)")
            
            # Populate ROI dropdown
            self.roi_dropdown.configure(values=self.signal_cols)
            self.current_roi = self.signal_cols[0]
            self.roi_dropdown.set(self.current_roi)
            
            # Auto estimate dt if time column is present
            if self.time_col is not None and len(df) > 1:
                t_vals = df[self.time_col].values
                dt_calc = float(np.mean(np.diff(t_vals)))
                if dt_calc > 0:
                    self.dt = dt_calc
                    self.dt_entry.delete(0, 'end')
                    self.dt_entry.insert(0, f"{self.dt:.2f}")

            self.auto_estimate_params()
            self.update_analysis()
            
        except Exception as e:
            messagebox.showerror("Error Loading Data", f"Failed to parse CSV file:\n\n{e}")

    def on_roi_change(self, roi_name):
        self.current_roi = roi_name
        self.auto_estimate_params()
        self.update_analysis()

    # -----------------------------------------------------------------
    # Parameter Controls Sync & Validation
    # -----------------------------------------------------------------
    def on_prom_slider(self, val):
        self.prom_entry.delete(0, 'end')
        self.prom_entry.insert(0, f"{float(val):.3f}")
        self.update_analysis_debounce()

    def on_prom_entry(self, event=None):
        try:
            val = float(self.prom_entry.get())
            val = max(0.001, min(1000.0, val))
            self.prom_slider.set(min(2.0, val))
            self.update_analysis()
        except ValueError:
            self.prom_entry.delete(0, 'end')
            self.prom_entry.insert(0, f"{self.prom_slider.get():.3f}")

    def on_dist_slider(self, val):
        self.dist_entry.delete(0, 'end')
        self.dist_entry.insert(0, str(int(val)))
        self.update_analysis_debounce()

    def on_dist_entry(self, event=None):
        try:
            val = int(self.dist_entry.get())
            val = max(1, min(2000, val))
            self.dist_slider.set(min(500, val))
            self.update_analysis()
        except ValueError:
            self.dist_entry.delete(0, 'end')
            self.dist_entry.insert(0, str(int(self.dist_slider.get())))

    def on_win_slider(self, val):
        win = int(val)
        if win % 2 == 0: win += 1
        self.win_entry.delete(0, 'end')
        self.win_entry.insert(0, str(win))
        self.update_analysis_debounce()

    def on_win_entry(self, event=None):
        try:
            win = int(self.win_entry.get())
            if win % 2 == 0: win += 1
            win = max(5, min(101, win))
            self.win_slider.set(min(51, win))
            self.update_analysis()
        except ValueError:
            self.win_entry.delete(0, 'end')
            self.win_entry.insert(0, str(int(self.win_slider.get())))

    def auto_estimate_params(self):
        """Computes noise standard deviation and sets recommended prominence threshold."""
        if self.df_raw is None or self.current_roi is None:
            return
            
        y_raw = self.df_raw[self.current_roi].values.astype(float)
        sigma = CalciumSignalProcessor.estimate_noise_std(y_raw)
        
        mode = self.trace_mode_var.get()
        if mode == "Delta F / F0":
            rec_prom = max(0.03, round(3.5 * (sigma / np.median(y_raw)), 3))
        else:
            rec_prom = max(1.0, round(3.5 * sigma, 1))
            
        self.prom_slider.set(min(2.0, rec_prom))
        self.prom_entry.delete(0, 'end')
        self.prom_entry.insert(0, str(rec_prom))

    def update_analysis_debounce(self, event=None):
        """Debounced analysis trigger for slider movements."""
        self.update_analysis()

    # -----------------------------------------------------------------
    # Core Analysis Execution
    # -----------------------------------------------------------------
    def update_analysis(self, event=None):
        if self.df_raw is None or self.current_roi is None:
            return

        try:
            self.dt = float(self.dt_entry.get())
        except ValueError:
            self.dt = 10.0

        self.y_raw = self.df_raw[self.current_roi].values.astype(float)
        n = len(self.y_raw)
        
        # 1. Baseline Computation
        base_win = int(self.base_win_slider.get())
        base_method = self.baseline_method_var.get()
        self.baseline = CalciumSignalProcessor.compute_baseline(self.y_raw, method=base_method, window_pts=base_win)
        self.dff0 = CalciumSignalProcessor.compute_dff0(self.y_raw, self.baseline)

        # 2. Pick Signal Space based on user toggle
        mode = self.trace_mode_var.get()
        y_analysis = self.dff0 if mode == "Delta F / F0" else self.y_raw
        
        # 3. Peak Detection
        prom = float(self.prom_entry.get())
        dist = int(self.dist_entry.get())
        win = int(self.win_entry.get())
        method = self.method_var.get()

        self.results = CalciumSignalProcessor.detect_peaks(
            y_analysis, self.dt, method=method, prominence=prom, min_distance_pts=dist, smooth_window_pts=win
        )

        # 4. Extract Per-Peak Metrics
        peaks = self.results["peaks"]
        self.metrics_df = CalciumSignalProcessor.extract_peak_metrics(
            self.results["t"], self.y_raw, self.results["y_smooth"], self.baseline, self.dff0, peaks, self.dt
        )

        # 5. Global Statistics
        self.global_stats = CalciumSignalProcessor.compute_global_statistics(self.metrics_df, n, self.dt)

        # 6. Update all UI Views
        self.plot_overview()
        self.update_inspector_options()
        self.update_metrics_table()
        self.update_summary_dashboard()

        self.status_label.configure(
            text=f"ROI: {self.current_roi} | Peaks Detected: {len(peaks)} | Rate: {self.global_stats['Frequency (Hz)']:.2f} Hz",
            text_color="#2ecc71" if len(peaks) > 0 else "#e74c3c"
        )

    # -----------------------------------------------------------------
    # Tab 1: Overview Plotting & Interactive Editing
    # -----------------------------------------------------------------
    def apply_plot_style(self, fig, ax):
        mode = self.appearance_mode_var.get()
        if mode == "Dark":
            bg_color = '#1e1e1e'
            text_color = '#ffffff'
            spine_color = '#444444'
            grid_color = '#333333'
        else:
            bg_color = '#ffffff'
            text_color = '#000000'
            spine_color = '#cccccc'
            grid_color = '#e5e7eb'

        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)
        ax.tick_params(colors=text_color, labelsize=9)
        ax.xaxis.label.set_color(text_color)
        ax.yaxis.label.set_color(text_color)
        ax.title.set_color(text_color)
        for spine in ax.spines.values():
            spine.set_color(spine_color)
        ax.grid(True, alpha=0.3, color=grid_color)

    def plot_overview(self):
        self.ax_ov.clear()
        self.apply_plot_style(self.fig_ov, self.ax_ov)

        if self.results is None or self.y_raw is None:
            self.canvas_ov.draw()
            return

        t = self.results["t"]
        mode = self.trace_mode_var.get()
        peaks = self.results["peaks"]

        if mode == "Delta F / F0":
            self.ax_ov.plot(t, self.dff0, color='#3498db', linewidth=1.0, alpha=0.8, label='ΔF / F₀ Trace')
            if self.results["y_smooth"] is not None and self.method_var.get().startswith("Hybrid"):
                self.ax_ov.plot(t, self.results["y_smooth"], color='#2ecc71', linewidth=1.2, alpha=0.9, label='Smoothed')
            if len(peaks) > 0:
                self.ax_ov.plot(t[peaks], self.dff0[peaks], "x", color='#e74c3c', markersize=9, markeredgewidth=2.5, label=f'Peaks (N={len(peaks)})')
            self.ax_ov.set_ylabel("ΔF / F₀", fontsize=10)
        else:
            self.ax_ov.plot(t, self.y_raw, color='#7f8c8d', linewidth=0.8, alpha=0.7, label='Raw Intensity F(t)')
            self.ax_ov.plot(t, self.baseline, color='#f1c40f', linewidth=1.5, linestyle='--', label='Baseline F₀(t)')
            if len(peaks) > 0:
                self.ax_ov.plot(t[peaks], self.y_raw[peaks], "x", color='#e74c3c', markersize=9, markeredgewidth=2.5, label=f'Peaks (N={len(peaks)})')
            self.ax_ov.set_ylabel("Fluorescence Intensity", fontsize=10)

        self.ax_ov.set_title(f"Calcium Transient Trace — ROI: {self.current_roi} | Freq: {self.global_stats['Frequency (Hz)']:.2f} Hz", fontsize=11, pad=10)
        self.ax_ov.set_xlabel("Time (ms)", fontsize=10)
        self.ax_ov.legend(loc='upper right', framealpha=0.8, fontsize=8)
        self.fig_ov.tight_layout()
        self.canvas_ov.draw()

    def toggle_interactive_click_mode(self):
        self.interactive_click_mode = not self.interactive_click_mode
        if self.interactive_click_mode:
            self.click_edit_btn.configure(
                text="👆 Interactive Peak Add/Delete Mode: ON (Click Plot)",
                fg_color="#e74c3c", hover_color="#c0392b"
            )
            self.click_cid = self.canvas_ov.mpl_connect("button_press_event", self.on_plot_click)
        else:
            self.click_edit_btn.configure(
                text="👆 Toggle Interactive Peak Add/Delete Mode: OFF",
                fg_color="#444444", hover_color="#555555"
            )
            if self.click_cid is not None:
                self.canvas_ov.mpl_disconnect(self.click_cid)
                self.click_cid = None

    def on_plot_click(self, event):
        if not self.interactive_click_mode or event.inaxes != self.ax_ov or self.results is None:
            return

        click_t = event.xdata
        if click_t is None:
            return

        t = self.results["t"]
        click_idx = int(np.argmin(np.abs(t - click_t)))
        peaks = list(self.results["peaks"])

        near_peak = [p for p in peaks if abs(p - click_idx) <= 20]
        if near_peak:
            for p in near_peak:
                peaks.remove(p)
        else:
            start = max(0, click_idx - 15)
            end = min(len(t), click_idx + 16)
            mode = self.trace_mode_var.get()
            y_sig = self.dff0 if mode == "Delta F / F0" else self.y_raw
            local_max_idx = start + np.argmax(y_sig[start:end])
            peaks.append(local_max_idx)

        peaks.sort()
        self.results["peaks"] = np.array(peaks, dtype=int)
        
        self.metrics_df = CalciumSignalProcessor.extract_peak_metrics(
            t, self.y_raw, self.results["y_smooth"], self.baseline, self.dff0, self.results["peaks"], self.dt
        )
        self.global_stats = CalciumSignalProcessor.compute_global_statistics(self.metrics_df, len(t), self.dt)

        self.plot_overview()
        self.update_inspector_options()
        self.update_metrics_table()
        self.update_summary_dashboard()

    # -----------------------------------------------------------------
    # Tab 2: Individual Peak Inspector
    # -----------------------------------------------------------------
    def update_inspector_options(self):
        if self.metrics_df is None or len(self.metrics_df) == 0:
            self.peak_select_dropdown.configure(values=["None"])
            self.peak_select_dropdown.set("None")
            self.update_inspector_plot("None")
            return

        p_list = [f"Peak #{row['Peak_ID']} ({row['Time (ms)']:.1f} ms)" for _, row in self.metrics_df.iterrows()]
        self.peak_select_dropdown.configure(values=p_list)
        self.peak_select_dropdown.set(p_list[0])
        self.update_inspector_plot(p_list[0])

    def update_inspector_plot(self, selected_str):
        self.ax_insp.clear()
        self.apply_plot_style(self.fig_insp, self.ax_insp)

        if self.metrics_df is None or len(self.metrics_df) == 0 or selected_str == "None":
            self.insp_card_lbl.configure(text="No peaks detected or selected.")
            self.canvas_insp.draw()
            return

        try:
            peak_id = int(selected_str.split("#")[1].split(" ")[0])
            row = self.metrics_df[self.metrics_df["Peak_ID"] == peak_id].iloc[0]
        except Exception:
            self.canvas_insp.draw()
            return

        p_idx = int(row["Peak Index"])
        t = self.results["t"]
        dt = self.dt
        n = len(t)

        w_pts = max(30, int(600.0 / dt))
        start = max(0, p_idx - w_pts)
        end = min(n, p_idx + w_pts)

        sub_t = t[start:end]
        sub_raw = self.y_raw[start:end]
        sub_dff0 = self.dff0[start:end]
        sub_base = self.baseline[start:end]

        mode = self.trace_mode_var.get()
        if mode == "Delta F / F0":
            self.ax_insp.plot(sub_t, sub_dff0, color='#3498db', linewidth=1.5, label='ΔF / F₀')
            self.ax_insp.axhline(0, color='gray', linestyle=':', alpha=0.5)
            self.ax_insp.plot(t[p_idx], self.dff0[p_idx], "ro", markersize=8, label='Peak Max')
            self.ax_insp.set_ylabel("ΔF / F₀", fontsize=10)
        else:
            self.ax_insp.plot(sub_t, sub_raw, color='#34495e', linewidth=1.5, label='Raw Intensity')
            self.ax_insp.plot(sub_t, sub_base, color='#f1c40f', linestyle='--', label='F₀ Baseline')
            self.ax_insp.plot(t[p_idx], self.y_raw[p_idx], "ro", markersize=8, label='Peak Max')
            self.ax_insp.set_ylabel("Fluorescence Intensity", fontsize=10)

        if pd.notna(row["Rise Time T10-90 (ms)"]):
            self.ax_insp.axvspan(
                row["Time (ms)"] - row["Rise Time T10-90 (ms)"], row["Time (ms)"], 
                color='#2ecc71', alpha=0.2, label='Rise Phase T10-90'
            )
            
        if pd.notna(row["Decay Time T50 (ms)"]):
            self.ax_insp.axvspan(
                row["Time (ms)"], row["Time (ms)"] + row["Decay Time T50 (ms)"], 
                color='#e74c3c', alpha=0.15, label='Decay Phase T50'
            )

        self.ax_insp.set_title(f"Detailed Transient Profile — Peak #{peak_id} at {row['Time (ms)']:.1f} ms", fontsize=11)
        self.ax_insp.set_xlabel("Time (ms)", fontsize=10)
        self.ax_insp.legend(loc='upper right', fontsize=8)
        self.fig_insp.tight_layout()
        self.canvas_insp.draw()

        card_text = (
            f"📌 Peak #{row['Peak_ID']} Properties:\n"
            f"───────────────────────────\n"
            f"• Peak Time: {row['Time (ms)']:.1f} ms ({row['Time (s)']:.2f} s)\n"
            f"• Peak Amplitude (dF/F0): {row['Amplitude (dF/F0)']:.4f}\n"
            f"• Raw Intensity: {row['Peak Raw Intensity']:.2f}\n"
            f"• Baseline F0: {row['Baseline F0']:.2f}\n"
            f"• Rise Time (T10-90): {row['Rise Time T10-90 (ms)']:.2f} ms\n"
            f"• Max Rise Slope (dF/dt): {row['Max Rise Rate (dF/dt)']:.4f}\n"
            f"• Half-Decay (T50): {row['Decay Time T50 (ms)']:.2f} ms\n"
            f"• Decay Tau (exp fit): {row['Decay Tau (ms)']:.2f} ms\n"
            f"• Duration (FWHM): {row['FWHM (ms)']:.2f} ms\n"
            f"• Area Under Curve (AUC): {row['AUC (dF/F0 * s)']:.4f} dF/F0·s\n"
        )
        self.insp_card_lbl.configure(text=card_text)

    # -----------------------------------------------------------------
    # Tab 3: Per-Peak Metrics Table
    # -----------------------------------------------------------------
    def update_metrics_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        if self.metrics_df is None or len(self.metrics_df) == 0:
            return

        cols = list(self.metrics_df.columns)
        self.tree["columns"] = cols
        self.tree["show"] = "headings"

        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="center")

        for _, row in self.metrics_df.iterrows():
            formatted_vals = []
            for col in cols:
                val = row[col]
                if isinstance(val, (float, np.floating)):
                    formatted_vals.append(f"{val:.3f}" if pd.notna(val) else "—")
                else:
                    formatted_vals.append(str(val))
            self.tree.insert("", "end", values=formatted_vals)

    # -----------------------------------------------------------------
    # Tab 4: Population Kinetics & Dashboard
    # -----------------------------------------------------------------
    def update_summary_dashboard(self):
        if self.global_stats is None:
            return

        gs = self.global_stats
        self.kpi_labels["Total Peaks"].configure(text=str(gs["Total Peaks"]))
        self.kpi_labels["Frequency (Hz)"].configure(text=f"{gs['Frequency (Hz)']:.2f} Hz ({gs['Frequency (events/min)']:.1f} bpm)")
        self.kpi_labels["Mean Rise T10-90 (ms)"].configure(text=f"{gs['Mean Rise Time T10-90 (ms)']:.1f} ms")
        self.kpi_labels["Mean Decay Tau (ms)"].configure(text=f"{gs['Mean Decay Tau (ms)']:.1f} ms")
        self.kpi_labels["Rhythmicity (CV)"].configure(text=f"{gs['Rhythmicity Index (CV of IEI)']:.3f}")

        for ax in self.axes_hist.flatten():
            ax.clear()
            self.apply_plot_style(self.fig_hist, ax)

        if self.metrics_df is not None and len(self.metrics_df) > 0:
            df = self.metrics_df
            
            amps = df["Amplitude (dF/F0)"].dropna()
            if len(amps) > 0:
                self.axes_hist[0, 0].hist(amps, bins=10, color='#3498db', edgecolor='black', alpha=0.7)
                self.axes_hist[0, 0].set_title("Peak Amplitudes (ΔF / F₀)", fontsize=10)

            rises = df["Rise Time T10-90 (ms)"].dropna()
            if len(rises) > 0:
                self.axes_hist[0, 1].hist(rises, bins=10, color='#2ecc71', edgecolor='black', alpha=0.7)
                self.axes_hist[0, 1].set_title("Rise Times T10-90 (ms)", fontsize=10)

            taus = df["Decay Tau (ms)"].dropna()
            if len(taus) > 0:
                self.axes_hist[1, 0].hist(taus, bins=10, color='#e74c3c', edgecolor='black', alpha=0.7)
                self.axes_hist[1, 0].set_title("Decay Tau Constants (ms)", fontsize=10)

            if len(df) > 1:
                ieis = np.diff(df["Time (ms)"])
                self.axes_hist[1, 1].hist(ieis, bins=10, color='#9b59b6', edgecolor='black', alpha=0.7)
                self.axes_hist[1, 1].set_title("Inter-Event Intervals (ms)", fontsize=10)

        self.fig_hist.tight_layout()
        self.canvas_hist.draw()

    # -----------------------------------------------------------------
    # Theme & Exporters
    # -----------------------------------------------------------------
    def toggle_theme(self):
        mode = self.appearance_mode_var.get()
        ctk.set_appearance_mode(mode)
        
        self.plot_overview()
        self.update_inspector_plot(self.peak_select_dropdown.get())
        self.update_summary_dashboard()

    def export_excel(self):
        if self.metrics_df is None or len(self.metrics_df) == 0:
            messagebox.showwarning("No Data", "No peak metrics available to export.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx", 
            filetypes=[("Excel Files", "*.xlsx")], 
            initialfile="Calcium_Peak_Metrics_Report.xlsx"
        )
        if not filepath:
            return

        try:
            df_global = pd.DataFrame([self.global_stats])
            df_glossary = CalciumSignalProcessor.get_glossary()
            
            df_trace = pd.DataFrame({
                "Time (ms)": self.results["t"],
                "Raw Intensity F(t)": self.y_raw,
                "Baseline F0(t)": self.baseline,
                "Delta F / F0": self.dff0
            })

            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                df_global.to_excel(writer, sheet_name="Global Statistics", index=False)
                self.metrics_df.to_excel(writer, sheet_name="Per-Peak Metrics", index=False)
                df_trace.to_excel(writer, sheet_name="Signal Traces", index=False)
                df_glossary.to_excel(writer, sheet_name="Metrics Glossary", index=False)

            messagebox.showinfo("Export Successful", f"Excel report exported successfully to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not write Excel file:\n\n{e}")

    def export_figures(self):
        if self.results is None:
            messagebox.showwarning("No Figure", "No active plot to export.")
            return

        folder = filedialog.askdirectory(title="Select Folder to Save Publication Figures")
        if not folder:
            return

        try:
            fig_path1 = os.path.join(folder, f"Calcium_Trace_Overview_{self.current_roi}.png")
            self.fig_ov.savefig(fig_path1, dpi=300, bbox_inches='tight')
            
            fig_path2 = os.path.join(folder, f"Calcium_Distribution_Dashboard_{self.current_roi}.png")
            self.fig_hist.savefig(fig_path2, dpi=300, bbox_inches='tight')

            messagebox.showinfo("Export Successful", f"Saved publication-grade figures (300 DPI) to:\n{folder}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not save figures:\n\n{e}")

    def on_closing(self):
        plt.close('all')
        self.quit()
        self.destroy()
        sys.exit(0)

def main():
    app = PeakAnalyzerApp()
    app.mainloop()

if __name__ == "__main__":
    main()

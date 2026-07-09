import sys
import customtkinter as ctk
from tkinter import filedialog, messagebox
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from scipy.signal import find_peaks, savgol_filter, peak_widths

# --- App Configuration ---
ctk.set_appearance_mode("Dark") 
ctk.set_default_color_theme("blue") 

class PeakAnalyzerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Signal Peak Analyzer")
        self.geometry("1200x800")
        self.minsize(1000, 600)

        # Intercept the "X" button to close gracefully
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Data variables
        self.df = None
        self.y_raw = None
        self.y_smooth = None
        self.t = None
        self.dt = 10.0
        self.peaks = []
        self.peaks_smooth = []
        self.peak_pairs = []

        self.setup_ui()

    def setup_ui(self):
        # --- Grid Layout ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Left Panel (Controls) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(8, weight=1) 

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Peak Analyzer", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # 1. File Selection
        self.load_btn = ctk.CTkButton(self.sidebar_frame, text="Load CSV File", command=self.load_csv)
        self.load_btn.grid(row=1, column=0, padx=20, pady=10)
        self.file_label = ctk.CTkLabel(self.sidebar_frame, text="No file loaded", font=ctk.CTkFont(size=12, slant="italic"))
        self.file_label.grid(row=2, column=0, padx=20, pady=(0, 20))

        # 2. Method Selection
        self.method_label = ctk.CTkLabel(self.sidebar_frame, text="Detection Method:", anchor="w")
        self.method_label.grid(row=3, column=0, padx=20, pady=(10, 0), sticky="w")
        self.method_var = ctk.StringVar(value="Hybrid (Smooth + Refine)")
        self.method_dropdown = ctk.CTkOptionMenu(self.sidebar_frame, values=["Hybrid (Smooth + Refine)", "Direct (Raw)"],
                                                 variable=self.method_var, command=self.update_analysis)
        self.method_dropdown.grid(row=4, column=0, padx=20, pady=10, sticky="ew")

        # 3. Parameters
        self.param_frame = ctk.CTkFrame(self.sidebar_frame)
        self.param_frame.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        self.param_frame.grid_columnconfigure(0, weight=1)
        self.param_frame.grid_columnconfigure(1, weight=0)

        # Prominence
        self.prom_label = ctk.CTkLabel(self.param_frame, text="Prominence:")
        self.prom_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")
        self.prom_entry = ctk.CTkEntry(self.param_frame, width=50)
        self.prom_entry.insert(0, "15")
        self.prom_entry.grid(row=0, column=1, padx=10, pady=(10, 0), sticky="e")
        self.prom_entry.bind("<Return>", self.sync_from_entries)

        self.prom_slider = ctk.CTkSlider(self.param_frame, from_=1, to=100, number_of_steps=99, command=self.update_prom_entry)
        self.prom_slider.set(15)
        self.prom_slider.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        self.prom_slider.bind("<ButtonRelease-1>", self.update_analysis)

        # Min Distance
        self.dist_label = ctk.CTkLabel(self.param_frame, text="Min Distance (frames):")
        self.dist_label.grid(row=2, column=0, padx=10, pady=(5, 0), sticky="w")
        self.dist_entry = ctk.CTkEntry(self.param_frame, width=50)
        self.dist_entry.insert(0, "100")
        self.dist_entry.grid(row=2, column=1, padx=10, pady=(5, 0), sticky="e")
        self.dist_entry.bind("<Return>", self.sync_from_entries)

        self.dist_slider = ctk.CTkSlider(self.param_frame, from_=10, to=500, number_of_steps=490, command=self.update_dist_entry)
        self.dist_slider.set(100)
        self.dist_slider.grid(row=3, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        self.dist_slider.bind("<ButtonRelease-1>", self.update_analysis)

        # Smooth Window
        self.window_label = ctk.CTkLabel(self.param_frame, text="Smooth Window:")
        self.window_label.grid(row=4, column=0, padx=10, pady=(5, 0), sticky="w")
        self.window_entry = ctk.CTkEntry(self.param_frame, width=50)
        self.window_entry.insert(0, "11")
        self.window_entry.grid(row=4, column=1, padx=10, pady=(5, 0), sticky="e")
        self.window_entry.bind("<Return>", self.sync_from_entries)

        self.window_slider = ctk.CTkSlider(self.param_frame, from_=5, to=51, number_of_steps=23, command=self.update_window_entry)
        self.window_slider.set(11)
        self.window_slider.grid(row=5, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        self.window_slider.bind("<ButtonRelease-1>", self.update_analysis)

        # Time step (dt)
        self.dt_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.dt_frame.grid(row=6, column=0, padx=20, pady=10, sticky="ew")
        self.dt_label = ctk.CTkLabel(self.dt_frame, text="Time step (ms/frame):")
        self.dt_label.pack(side="left")
        self.dt_entry = ctk.CTkEntry(self.dt_frame, width=60)
        self.dt_entry.insert(0, "10.0")
        self.dt_entry.pack(side="right")
        self.dt_entry.bind("<Return>", self.update_analysis)

        # 4. Export Metrics Button
        self.export_btn = ctk.CTkButton(self.sidebar_frame, text="Extract & Save Metrics", fg_color="#27ae60", hover_color="#2ecc71", command=self.export_metrics)
        self.export_btn.grid(row=9, column=0, padx=20, pady=(20, 10))

        # 5. Theme Toggle
        self.appearance_mode_var = ctk.StringVar(value="Dark")
        self.theme_switch = ctk.CTkSwitch(self.sidebar_frame, text="Dark Mode", command=self.toggle_theme, 
                                          variable=self.appearance_mode_var, onvalue="Dark", offvalue="Light")
        self.theme_switch.grid(row=10, column=0, padx=20, pady=(0, 20), sticky="w")

        # --- Right Panel (Plot) ---
        self.plot_frame = ctk.CTkFrame(self, corner_radius=0)
        self.plot_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.plot_frame.grid_columnconfigure(0, weight=1)
        self.plot_frame.grid_rowconfigure(0, weight=1)

        self.fig, self.ax = plt.subplots(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        
        self.apply_plot_theme()

    # --- Theme & UI Updaters ---
    def toggle_theme(self):
        mode = self.appearance_mode_var.get()
        ctk.set_appearance_mode(mode)
        self.apply_plot_theme()
        
        if self.y_raw is not None:
            self.plot_data()
        else:
            self.canvas.draw()

    def apply_plot_theme(self):
        mode = self.appearance_mode_var.get()
        if mode == "Dark":
            bg_color = '#2b2b2b'
            text_color = 'white'
            spine_color = '#555555'
        else:
            bg_color = '#ebebeb'
            text_color = 'black'
            spine_color = '#cccccc'

        self.fig.patch.set_facecolor(bg_color)
        self.ax.set_facecolor(bg_color)
        self.ax.tick_params(colors=text_color)
        self.ax.xaxis.label.set_color(text_color)
        self.ax.yaxis.label.set_color(text_color)
        self.ax.title.set_color(text_color)
        for spine in self.ax.spines.values():
            spine.set_color(spine_color)

    def update_prom_entry(self, value):
        self.prom_entry.delete(0, 'end')
        self.prom_entry.insert(0, str(int(value)))

    def update_dist_entry(self, value):
        self.dist_entry.delete(0, 'end')
        self.dist_entry.insert(0, str(int(value)))

    def update_window_entry(self, value):
        val = int(value)
        if val % 2 == 0: val += 1
        self.window_entry.delete(0, 'end')
        self.window_entry.insert(0, str(val))

    def sync_from_entries(self, event=None):
        try:
            prom = max(1, min(100, int(self.prom_entry.get())))
            self.prom_slider.set(prom)
            self.update_prom_entry(prom)

            dist = max(10, min(500, int(self.dist_entry.get())))
            self.dist_slider.set(dist)
            self.update_dist_entry(dist)

            win = int(self.window_entry.get())
            if win % 2 == 0: win += 1
            win = max(5, min(51, win))
            self.window_slider.set(win)
            self.update_window_entry(win)

            self.update_analysis()
        except ValueError:
            self.update_prom_entry(self.prom_slider.get())
            self.update_dist_entry(self.dist_slider.get())
            self.update_window_entry(self.window_slider.get())

    # --- Data Processing ---
    def load_csv(self):
        filepath = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
        if not filepath:
            return

        try:
            self.df = pd.read_csv(filepath, sep=None, engine='python')
            self.y_raw = self.df.iloc[:, -1].values  
            self.file_label.configure(text=filepath.split("/")[-1])
            self.update_analysis()
        except Exception as e:
            messagebox.showerror("Error Loading File", f"Could not load the file.\n\n{e}")

    def update_analysis(self, event=None):
        if self.y_raw is None:
            return

        try:
            self.dt = float(self.dt_entry.get())
        except ValueError:
            self.dt = 10.0
            self.dt_entry.delete(0, 'end')
            self.dt_entry.insert(0, "10.0")

        self.t = np.arange(len(self.y_raw)) * self.dt
        
        prom = int(self.prom_slider.get())
        dist = int(self.dist_slider.get())
        method = self.method_var.get()

        self.peaks = []
        self.peak_pairs = []
        self.y_smooth = None

        if method == "Direct (Raw)":
            self.peaks, _ = find_peaks(self.y_raw, distance=dist, prominence=prom, width=2)
            self.window_slider.configure(state="disabled")
            self.window_entry.configure(state="disabled")
        else:
            self.window_slider.configure(state="normal")
            self.window_entry.configure(state="normal")
            win_len = int(self.window_slider.get())
            if win_len % 2 == 0: win_len += 1
            
            self.y_smooth = savgol_filter(self.y_raw, window_length=win_len, polyorder=3)
            self.peaks_smooth, _ = find_peaks(self.y_smooth, distance=dist, prominence=prom, width=5)
            search_window = 100 
            for p_smooth in self.peaks_smooth:
                start = max(0, p_smooth - search_window)
                end = min(len(self.y_raw), p_smooth + search_window)
                local_max_idx = np.argmax(self.y_raw[start:end])
                p_refined = start + local_max_idx
                self.peaks.append(p_refined)
                self.peak_pairs.append((p_refined, p_smooth))
            self.peaks = np.array(self.peaks)

        self.plot_data()

    def plot_data(self):
        self.ax.clear()
        
        # Plot Raw
        self.ax.plot(self.t, self.y_raw, color='gray', alpha=0.5, label='Raw Signal')

        # Plot Smooth & Peaks
        if self.method_var.get() == "Hybrid (Smooth + Refine)" and self.y_smooth is not None:
            self.ax.plot(self.t, self.y_smooth, color='#2ecc71', linewidth=1.5, alpha=0.8, label='Smoothed')
            if len(self.peaks) > 0:
                self.ax.plot(self.t[self.peaks], self.y_raw[self.peaks], "x", color='#e74c3c', markersize=10, markeredgewidth=2, label='Hybrid Peaks')
        else:
            if len(self.peaks) > 0:
                self.ax.plot(self.t[self.peaks], self.y_raw[self.peaks], "x", color='#3498db', markersize=10, markeredgewidth=2, label='Raw Peaks')

        freq_hz = len(self.peaks) / (len(self.y_raw) * self.dt / 1000.0) if len(self.y_raw) > 0 else 0
        
        mode = self.appearance_mode_var.get()
        text_color = 'white' if mode == "Dark" else 'black'
        grid_color = 'white' if mode == "Dark" else 'gray'
        legend_bg = '#333333' if mode == "Dark" else '#ffffff'
        
        self.ax.set_title(f"Peak Detection | Freq: {freq_hz:.2f} Hz", color=text_color)
        self.ax.set_xlabel("Time (ms)", color=text_color)
        self.ax.set_ylabel("Intensity", color=text_color)
        self.ax.legend(loc='upper right', facecolor=legend_bg, edgecolor=text_color, labelcolor=text_color)
        self.ax.grid(True, alpha=0.2, color=grid_color)
        self.fig.tight_layout()
        self.canvas.draw()

    # --- Export ---
    def export_metrics(self):
        if self.y_raw is None or len(self.peaks) == 0:
            messagebox.showwarning("No Data", "No data loaded or no peaks detected to export.")
            return

        filepath = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")], initialfile="Peak_Metrics.xlsx")
        if not filepath:
            return

        total_duration_sec = len(self.y_raw) * (self.dt / 1000.0)
        freq_hz = len(self.peaks) / total_duration_sec

        metrics_list = []
        
        for i, p_idx in enumerate(self.peaks):
            peak_val = self.y_raw[p_idx]
            
            if self.method_var.get() == "Hybrid (Smooth + Refine)":
                p_smooth = self.peak_pairs[i][1]
                search_back = 200
                search_start = max(0, p_smooth - search_back)
                f0_idx = np.argmin(self.y_smooth[search_start:p_smooth]) + search_start
                f0_val = self.y_smooth[f0_idx]
                
                amplitude = peak_val - f0_val
                dff = (peak_val - f0_val) / f0_val if f0_val != 0 else 0
                
                amp_10 = f0_val + (0.1 * amplitude)
                amp_90 = f0_val + (0.9 * amplitude)
                amp_50 = f0_val + (0.5 * amplitude)
                
                pre_seg = self.y_smooth[f0_idx:p_smooth]
                t_10_idx = np.where(pre_seg >= amp_10)[0][0] if len(np.where(pre_seg >= amp_10)[0]) > 0 else 0
                t_90_idx = np.where(pre_seg >= amp_90)[0][0] if len(np.where(pre_seg >= amp_90)[0]) > 0 else len(pre_seg)-1
                rise_time = self.t[f0_idx + t_90_idx] - self.t[f0_idx + t_10_idx] if t_90_idx > t_10_idx else np.nan
                
                post_seg = self.y_smooth[p_smooth:min(len(self.y_smooth), p_smooth + 400)]
                try:
                    t_50_local = np.where(post_seg <= amp_50)[0][0]
                    decay_time = self.t[p_smooth + int(t_50_local)] - self.t[p_smooth]
                except IndexError:
                    decay_time = np.nan
                    
                try:
                    w = peak_widths(self.y_smooth, [p_smooth], rel_height=0.5)
                    fwhm = w[0][0] * self.dt
                except:
                    fwhm = np.nan
            else:
                f0_val = np.nan
                dff = np.nan
                rise_time = np.nan
                decay_time = np.nan
                fwhm = np.nan

            metrics_list.append({
                "Peak_ID": i+1,
                "Time (ms)": self.t[p_idx],
                "Peak Intensity": peak_val,
                "F0 Baseline": f0_val,
                "dF/F0": dff,
                "Rise Time (ms)": rise_time,
                "Decay Time (ms)": decay_time,
                "FWHM (ms)": fwhm
            })

        df_metrics = pd.DataFrame(metrics_list)
        
        iei = np.diff(df_metrics['Time (ms)'])
        global_stats = {
            "Total Peaks": len(self.peaks),
            "Total Duration (s)": total_duration_sec,
            "Frequency (Hz)": freq_hz,
            "Avg Inter-Event Interval (ms)": np.mean(iei) if len(iei) > 0 else 0,
            "Rhythmicity (Std Dev IEI)": np.std(iei) if len(iei) > 0 else 0,
        }
        df_global = pd.DataFrame([global_stats])
        
        glossary = {
            "Metric": ["Peak Intensity", "F0 Baseline", "dF/F0", "Rise Time (ms)", "Decay Time (ms)", "FWHM (ms)", "Avg Inter-Event Interval (ms)", "Rhythmicity"],
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
        }
        df_glossary = pd.DataFrame(glossary)

        with pd.ExcelWriter(filepath) as writer:
            df_global.to_excel(writer, sheet_name="Global Stats", index=False)
            df_metrics.to_excel(writer, sheet_name="Metrics per Peak", index=False)
            df_glossary.to_excel(writer, sheet_name="Metrics Glossary", index=False)

        msg = f"Successfully saved to:\n{filepath}\n\nIncluded Sheets:\n1. Global Stats\n2. Metrics per Peak\n3. Metrics Glossary"
        messagebox.showinfo("Export Successful", msg)

    # --- Graceful Shutdown ---
    def on_closing(self):
        # 1. Close the matplotlib figure to stop its background rendering loops
        plt.close('all')
        # 2. Stop the tkinter main loop
        self.quit()
        # 3. Destroy all widgets
        self.destroy()
        # 4. Ensure Python fully exits, killing any lingering threads
        sys.exit(0)

if __name__ == "__main__":
    app = PeakAnalyzerApp()
    app.mainloop()
"""
Calcium Signal Peak Analyzer — Desktop GUI Entry Launcher
"""
import sys
import os

# Add src folder to python path
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from calcium_peak_analyzer.gui.peak_analyzer_app import main

if __name__ == "__main__":
    main()
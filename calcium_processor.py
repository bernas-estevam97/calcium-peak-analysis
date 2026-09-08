"""
Legacy module import alias for CalciumSignalProcessor
"""
import sys
import os

src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import importlib
import calcium_peak_analyzer.core.calcium_processor as _cp
if not hasattr(_cp.CalciumSignalProcessor, "auto_tune_parameters"):
    _cp = importlib.reload(_cp)

from calcium_peak_analyzer.core.calcium_processor import CalciumSignalProcessor, trapz_func

__all__ = ["CalciumSignalProcessor", "trapz_func"]

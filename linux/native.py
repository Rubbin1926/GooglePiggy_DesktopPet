"""Optional app-private Ubuntu xcb-cursor library; no global loader changes."""
import ctypes
import sys
from pathlib import Path


def preload():
    if getattr(sys, 'frozen', False):
        return  # PyInstaller collects the library next to its other native libraries.
    library = Path(__file__).resolve().parents[1]/'.native/usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0'
    if library.is_file():
        ctypes.CDLL(str(library), mode=ctypes.RTLD_GLOBAL)

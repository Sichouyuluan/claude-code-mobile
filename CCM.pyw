"""CC Remote Dashboard — 静默启动（无命令行窗口）"""
import sys
import os

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Add to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from panel import Panel
import tkinter as tk

if __name__ == "__main__":
    app = Panel()
    app.mainloop()

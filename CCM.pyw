"""CC Remote Dashboard — 静默启动（无命令行窗口）"""
import sys
import os

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Add to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import webview
from panel import PanelAPI, _cleanup_orphaned, PROJECT_DIR

if __name__ == "__main__":
    _cleanup_orphaned()
    api = PanelAPI()
    window = webview.create_window(
        'claude-code-mobile',
        url=str(PROJECT_DIR / 'static' / 'panel.html'),
        js_api=api,
        width=820,
        height=620,
        min_size=(640, 450),
        background_color='#080b14',
    )
    webview.start(debug=False)

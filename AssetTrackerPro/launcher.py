import os
import sys
import time
import webbrowser
import threading
import streamlit.web.cli as stcli

def open_browser():
    """Opens default browser automatically after Streamlit server starts."""
    time.sleep(2.5)
    webbrowser.open("http://localhost:8501")

if __name__ == "__main__":
    # Determine base directory whether running from PyInstaller bundle or script
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    app_script = os.path.join(base_dir, "app.py")

    # Launch browser thread in background
    threading.Thread(target=open_browser, daemon=True).start()

    # Pass Streamlit CLI arguments programmatically
    sys.argv = [
        "streamlit",
        "run",
        app_script,
        "--global.developmentMode=false",
        "--server.headless=true",
        "--server.port=8501"
    ]

    sys.exit(stcli.main())

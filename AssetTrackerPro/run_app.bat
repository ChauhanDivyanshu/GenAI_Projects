@echo off
cd /d %~dp0
echo Starting Infosware Asset Tracker...
python -m streamlit run app.py --server.port 8501
pause

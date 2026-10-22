@echo off
echo ========================================================
echo Cleaning old builds...
echo ========================================================
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist AssetTrackerPro.spec del /f /q AssetTrackerPro.spec

echo ========================================================
echo Installing/Upgrading PyInstaller...
echo ========================================================
python -m pip install --upgrade pyinstaller

echo ========================================================
echo Building Executable Bundle for AssetTrackerPro...
echo ========================================================
python -m PyInstaller --noconfirm --onedir --console ^
  --name "AssetTrackerPro" ^
  --add-data "app.py;." ^
  --add-data "config.json;." ^
  --add-data "ZMPrintService.exe.config;." ^
  --add-data "ZMPrintService.ini;." ^
  --add-binary "ZMPrintService.exe;." ^
  --add-binary "ZMPCL.dll;." ^
  --add-data "core;core" ^
  --add-data "ui;ui" ^
  --add-data "templates;templates" ^
  --copy-metadata streamlit ^
  --collect-all streamlit ^
  --collect-all altair ^
  --collect-all pywin32 ^
  --collect-all wmi ^
  --collect-all qrcode ^
  --collect-all PIL ^
  --collect-all pandas ^
  --collect-all openpyxl ^
  --collect-all requests ^
  --hidden-import qrcode ^
  --hidden-import PIL ^
  --hidden-import PIL.Image ^
  launcher.py

echo ========================================================
echo EXE Build Completed!
echo Output directory: dist\AssetTrackerPro
echo Launch File: dist\AssetTrackerPro\AssetTrackerPro.exe
echo ========================================================
pause

@echo off
REM One-click runner for Windows. Double-click this file.
cd /d "%~dp0"
echo Installing required libraries (first run only)...
pip install -r requirements.txt
echo.
echo Running the tracker...
REM Use sample data by default. Remove --offline for live data; remove --no-ai if you set an API key.
python src\main.py --offline --no-ai
echo.
echo ============================================================
echo Done. Open output\macro_risk_tracker.xlsx to see the spreadsheet.
echo For live data instead of samples, run:  python src\main.py --no-ai
echo ============================================================
pause

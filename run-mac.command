#!/bin/bash
# One-click runner for Mac. Right-click -> Open the first time.
cd "$(dirname "$0")"
echo "Installing required libraries (first run only)..."
pip3 install -r requirements.txt
echo
echo "Running the tracker..."
# Use sample data by default. Remove --offline for live data; remove --no-ai if you set an API key.
python3 src/main.py --offline --no-ai
echo
echo "============================================================"
echo "Done. Open output/macro_risk_tracker.xlsx to see the spreadsheet."
echo "For live data instead of samples, run:  python3 src/main.py --no-ai"
echo "============================================================"

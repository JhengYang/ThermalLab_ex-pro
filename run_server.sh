#!/bin/bash
# 啟動 FLIR Server 腳本 (Linux/Mac)
echo "=========================================="
echo "    FLIR Thermal Analyzer - Server Mode"
echo "=========================================="

cd "$(dirname "$0")/app"

# 確保虛擬環境存在
if [ ! -d "venv" ]; then
    echo "[!] Creating virtual environment..."
    python3 -m venv venv
fi

# 啟動虛擬環境並安裝依賴
source venv/bin/activate
echo "[*] Installing requirements..."
pip install -r requirements.txt

echo "[*] Starting Gunicorn server on http://0.0.0.0:5050 ..."
echo "[*] Press Ctrl+C to stop the server."
gunicorn --bind 0.0.0.0:5050 --workers 1 --threads 8 --timeout 120 app:app

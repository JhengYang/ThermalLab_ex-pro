@echo off
REM 啟動 FLIR Server 腳本 (Windows)
echo ==========================================
echo     FLIR Thermal Analyzer - Server Mode
echo ==========================================

cd /d "%~dp0\app"

REM 確保虛擬環境存在
IF NOT EXIST venv (
    echo [!] Creating virtual environment...
    python -m venv venv
)

REM 啟動虛擬環境並安裝依賴
call venv\Scripts\activate.bat
echo [*] Installing requirements...
pip install -r requirements.txt
pip install waitress

echo [*] Starting Waitress server on http://0.0.0.0:5050 ...
echo [*] Press Ctrl+C to stop the server.
waitress-serve --listen=0.0.0.0:5050 --threads=8 app:app

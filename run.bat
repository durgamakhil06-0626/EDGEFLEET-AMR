@echo off
cd /d "%~dp0"
echo.
echo ==========================================
echo       EDGEFLEET BACKEND SERVER
echo ==========================================
echo.
echo Installing/checking Python packages...
python -m pip install -r backend\requirements.txt
echo.
echo Starting FastAPI backend...
echo Open http://127.0.0.1:8000 in Chrome or Edge.
echo Press CTRL+C to stop.
echo.
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
pause

@echo off
cd /d "%%~dp0"
echo ================================
echo   CC Remote Dashboard
echo ================================
echo   1. GUI Panel [Recommended]
echo   2. CLI Mode
echo ================================
set /p choice=Select (1/2):
if "%%choice%%"=="1" (
    python panel.py
) else (
    python server.py
)
pause

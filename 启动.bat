@echo off
cd /d "%~dp0"
echo ================================
echo   CC Remote Dashboard
echo ================================
echo   1. GUI 管理面板 (推荐)
echo   2. 命令行模式
echo ================================
set /p choice=请选择 (1/2):
if "%choice%"=="1" (
    python panel.py
) else (
    python server.py
)
pause

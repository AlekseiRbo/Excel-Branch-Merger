@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" make_screenshot.py
if errorlevel 1 (
    echo.
    echo Screenshot generation failed.
    pause
    exit /b 1
)

echo.
echo Screenshot updated: screenshots\application.png
pause

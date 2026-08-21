@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo uv was not found on PATH.
    echo Install uv, then run: uv sync --locked
    pause
    exit /b 1
)

uv run --locked python make_screenshot.py
if errorlevel 1 (
    echo.
    echo Screenshot generation failed.
    pause
    exit /b 1
)

echo.
echo Screenshot updated: screenshots\application.png
pause
endlocal

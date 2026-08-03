@echo off
cd /d "%~dp0"
title Excel Branch Merger Development Mode

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo.
    echo Create it with:
    echo   python -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" dev_runner.py
if errorlevel 1 pause

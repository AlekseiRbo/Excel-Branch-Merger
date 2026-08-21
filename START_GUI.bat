@echo off
setlocal
cd /d "%~dp0"
title Excel Branch Merger

where uv >nul 2>nul
if errorlevel 1 (
    echo uv was not found on PATH.
    echo Install uv, then run: uv sync --locked
    pause
    exit /b 1
)

uv run --locked python gui.py
if errorlevel 1 pause
endlocal

@echo off
setlocal
echo ===================================================
echo   RepoDNA v0.7.0 — Repository Intelligence Platform
echo ===================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3.12+ was not found in PATH.
    echo Please install Python 3.12+ and try again.
    pause
    exit /b 1
)

if exist .venv\Scripts\python.exe (
    echo [INFO] Using virtual environment (.venv)...
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    echo [INFO] Virtual environment not found, using system Python...
    set "PYTHON_EXE=python"
)

echo [INFO] Starting RepoDNA Intelligence Server and Workstation UI...
%PYTHON_EXE% -m repodna.cli.main start --open-browser
endlocal

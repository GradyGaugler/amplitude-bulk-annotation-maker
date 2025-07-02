@echo off
echo Starting Amplitude Bulk Annotation Maker...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.13 or later from https://www.python.org
    pause
    exit /b 1
)

REM Check if dependencies are installed
python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo Installing required dependencies...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

REM Run the application
echo Launching application...
python amplitude_bulk_annotator.py

if errorlevel 1 (
    echo.
    echo ERROR: Application failed to start
    pause
) 
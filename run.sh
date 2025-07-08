#!/bin/bash

echo "Starting Amplitude Bulk Annotation Maker..."
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.9 or later"
    exit 1
fi

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "WARNING: Python $python_version detected. Python 3.9+ is recommended."
    echo "Continuing anyway..."
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import PySide6" 2>/dev/null; then
    echo "Installing required dependencies..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies"
        exit 1
    fi
fi

# Run the application
echo "Launching application..."
python amplitude_bulk_annotator.py

if [ $? -ne 0 ]; then
    echo
    echo "ERROR: Application failed to start"
    read -p "Press any key to continue..."
fi 
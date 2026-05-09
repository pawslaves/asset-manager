@echo off
pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies
    pause
    exit /b 1
)
cls
echo ok
pythonw main.py

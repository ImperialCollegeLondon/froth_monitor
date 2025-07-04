@echo off
REM ----------------------------------------
REM 1) create venv if needed, install deps
REM ----------------------------------------
set VENV=venv

if not exist "%VENV%\Scripts\activate.bat" (
    echo [*] Creating virtual environment...
    python -m venv "%VENV%"
    if errorlevel 1 (
      echo Failed to create venv. Make sure Python is on your PATH.
      pause & exit /b 1
    )
)

echo [*] Activating venv...
call "%VENV%\Scripts\activate.bat"

echo [*] Ensuring pip is up to date...
python -m pip install --upgrade pip

echo [*] Installing requirements...
python -m pip install -r requirements.txt

REM ----------------------------------------
REM 2) run the lidar script
REM ----------------------------------------
echo [*] Launching lidar monitor...
python lidar_test.py

REM ----------------------------------------
REM 3) keep window open
REM ----------------------------------------
echo.
echo Press any key to exit
pause > nul

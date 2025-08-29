@echo off
echo Building IDF Reader with Flet...
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

REM Install/update requirements
echo Installing requirements...
pip install -r requirements.txt

REM Build with flet pack (includes icon)
echo Building executable...
flet pack main.py --name "IDF Reader" --icon "data/logo.ico"

echo.
echo Build complete! Check the 'dist' folder for the executable.
pause
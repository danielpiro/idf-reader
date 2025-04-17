@echo off
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate

echo Installing requirements...
pip install -r requirements.txt

echo Starting development server...
python main.py tests/amir.idf --idd tests/Energy+.idd
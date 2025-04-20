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
python main.py tests/_20.4in.idf --idd tests/Energy+.idd
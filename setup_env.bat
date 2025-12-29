@echo off
cd /d "%~dp0"
echo Setting up Python 3.11 environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo Python 3.11 not found or failed to create venv.
    pause
    exit /b %errorlevel%
)
call venv\Scripts\activate.bat
echo Installing dependencies...
pip install -r requirements.txt
echo Environment setup complete.
pause

@echo off
setlocal
cd /d "%~dp0.."

echo [0/3] Activating virtual environment...
if not exist "venv\Scripts\activate.bat" goto :NO_VENV
call venv\Scripts\activate.bat
goto :VENV_OK

:NO_VENV
echo Error: Virtual environment (venv) not found. 
echo Please run setup_env.bat first.
pause
exit /b 1

:VENV_OK
echo [1/3] Generating ICO file from JPG...
python tools\generate_ico.py

if not exist "src\resource\icon\icon.ico" goto :NO_ICO
goto :ICO_OK

:NO_ICO
echo Error: Failed to generate icon.ico
exit /b 1

:ICO_OK
echo [2/3] Building EXE with PyInstaller...
:: Check if pyinstaller is installed in venv
where pyinstaller >nul 2>nul
if %ERRORLEVEL% neq 0 goto :NO_PYINSTALLER
goto :PY_OK

:NO_PYINSTALLER
echo Error: PyInstaller is not installed in the virtual environment.
echo Please run: pip install pyinstaller
pause
exit /b 1

:PY_OK
pyinstaller --noconsole ^
            --onefile ^
            --icon "src\resource\icon\icon.ico" ^
            --add-data "src/resource/icon;src/resource/icon" ^
            --add-data "src/resource/se;src/resource/se" ^
            --name "Dionys Control" ^
            src\main.py

if %ERRORLEVEL% neq 0 (
    echo Error: PyInstaller build failed.
    exit /b 1
)

echo [2.5/3] Copying external resources...
xcopy "config\locale" "dist\config\locale" /E /I /Y >nul

echo [3/3] Build completed!
echo Executable is located in: dist\Dionys Control.exe
echo.
pause

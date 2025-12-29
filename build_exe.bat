@echo off
setlocal

echo [1/3] Generating ICO file from JPG...
python generate_ico.py

if not exist "src\resource\icon\icon.ico" (
    echo Error: Failed to generate icon.ico
    exit /b 1
)

echo [2/3] Building EXE with PyInstaller...
:: --noconsole: GUI-only
:: --onefile: Single EXE
:: --icon: Set the EXE icon
:: --add-data: Include icons in the bundle (format: source;dest)
:: --name: Output EXE name
pyinstaller --noconsole ^
            --onefile ^
            --icon "src\resource\icon\icon.ico" ^
            --add-data "src/resource/icon;src/resource/icon" ^
            --name "LinkMaster" ^
            src\main.py

if %ERRORLEVEL% neq 0 (
    echo Error: PyInstaller build failed.
    exit /b 1
)

echo [3/3] Build completed!
echo Executable is located in: dist\LinkMaster.exe
echo.
pause

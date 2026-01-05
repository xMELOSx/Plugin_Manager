@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0.."

set "SOURCE_DIR=src"
set "BACKUP_ROOT=backups"
set "VERSION_FILE=VERSION.txt"

:: Read current version from VERSION.txt
if exist "%VERSION_FILE%" (
    for /f "delims=" %%v in (%VERSION_FILE%) do set "CURRENT_VERSION=%%v"
) else (
    set "CURRENT_VERSION=0.9.100"
    echo %CURRENT_VERSION%>"%VERSION_FILE%"
)

:: Parse version parts (MAJOR.MINOR.PATCH)
for /f "tokens=1,2,3 delims=." %%a in ("%CURRENT_VERSION%") do (
    set "MAJOR=%%a"
    set "MINOR=%%b"
    set "PATCH=%%c"
)

:: Get current date and time
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set "TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%"

:: Prefix and version handling
set "PREFIX=Dev"
set "INCREMENT="
if /i "%~1"=="stable" set "PREFIX=Stable"
if /i "%~1"=="dev" set "PREFIX=Dev"
if /i "%~1"=="patch" (
    set "PREFIX=Release"
    set /a PATCH+=1
    set "INCREMENT=patch"
)
if /i "%~1"=="minor" (
    set "PREFIX=Release"
    set /a MINOR+=1
    set "PATCH=0"
    set "INCREMENT=minor"
)
if /i "%~1"=="major" (
    set "PREFIX=Release"
    set /a MAJOR+=1
    set "MINOR=0"
    set "PATCH=0"
    set "INCREMENT=major"
)

:: Build new version string
set "NEW_VERSION=%MAJOR%.%MINOR%.%PATCH%"

set "BACKUP_DIR=%BACKUP_ROOT%\%PREFIX%_v%NEW_VERSION%_%TIMESTAMP%"

echo ========================================
echo Dionys Debug Backup Utility
echo Current Version: %CURRENT_VERSION%
if defined INCREMENT (
    echo Incrementing: %INCREMENT%
    echo New Version: %NEW_VERSION%
)
echo ========================================
echo Backing up %SOURCE_DIR% to %BACKUP_DIR%...

if not exist "%BACKUP_ROOT%" mkdir "%BACKUP_ROOT%"

xcopy "%SOURCE_DIR%" "%BACKUP_DIR%" /E /I /Q /Y

if %errorlevel% equ 0 (
    echo Backup successful!
    if defined INCREMENT (
        echo %NEW_VERSION%>"%VERSION_FILE%"
        echo Version updated to %NEW_VERSION%
    )
) else (
    echo Backup failed!
)

echo.
echo Usage: backup_source.bat [dev^|stable^|patch^|minor^|major]
echo   dev    - Development backup (no version change)
echo   stable - Stable backup (no version change)
echo   patch  - Increment patch version (0.2.0 -^> 0.2.1)
echo   minor  - Increment minor version (0.2.0 -^> 0.3.0)
echo   major  - Increment major version (0.2.0 -^> 1.0.0)
endlocal

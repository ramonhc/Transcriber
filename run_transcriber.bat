@echo off
setlocal

REM Default language if none passed
set "LANG=%~1"
if "%LANG%"=="" set "LANG=en"

REM Move to this BAT file's directory (important if called from elsewhere)
cd /d "%~dp0"

REM Activate virtual environment
call ".\venv\Scripts\activate.bat"

REM Run script with language argument
python ".\TranscriberAuto.py" "%LANG%"

REM Capture Python exit code
set "PY_EXIT=%ERRORLEVEL%"

REM Deactivate venv
call ".\venv\Scripts\deactivate.bat"

REM Return Python's exit code to caller
exit /b %PY_EXIT%

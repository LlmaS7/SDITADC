@echo off
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Please create .venv and install requirements.txt first.
  pause
  exit /b 1
)
if "%~1"=="" (
  start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
) else (
  "%~dp0.venv\Scripts\python.exe" "%~dp0main.py" %*
  if errorlevel 1 pause
)


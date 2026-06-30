@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Local environment missing. Run setup-windows.cmd first.
  exit /b 1
)

".venv\Scripts\python.exe" groove.py run %*
exit /b %ERRORLEVEL%

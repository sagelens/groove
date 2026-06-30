@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

echo Groove non-admin setup
echo Repository: %CD%
echo.

if exist ".venv\Scripts\python.exe" goto install

where py >nul 2>&1
if errorlevel 1 goto python_command

py -3.13 -c "import sys" >nul 2>&1
if errorlevel 1 goto try_py312
echo Creating .venv with Python 3.13...
py -3.13 -m venv .venv
goto venv_created

:try_py312
py -3.12 -c "import sys" >nul 2>&1
if errorlevel 1 goto python_command
echo Creating .venv with Python 3.12...
py -3.12 -m venv .venv
goto venv_created

:python_command
where python >nul 2>&1
if errorlevel 1 goto no_python
python -c "import sys; assert (3, 12) <= sys.version_info[:2] < (3, 14)" >nul 2>&1
if errorlevel 1 goto no_python
echo Creating .venv with python.exe...
python -m venv .venv

:venv_created
if errorlevel 1 goto venv_failed
if not exist ".venv\Scripts\python.exe" goto venv_failed

:install
echo Installing Groove into the repository-local virtual environment...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto install_failed
".venv\Scripts\python.exe" -m pip install -e ".[proxy]"
if errorlevel 1 goto install_failed

echo.
echo Setup complete. No administrator access or Rust toolchain was used.
echo.
echo Next:
echo   .venv\Scripts\python.exe groove.py prepare --model YOUR_MODEL --context-window 32768
echo   .venv\Scripts\python.exe groove.py verify
echo   run-windows.cmd
exit /b 0

:no_python
echo ERROR: Install 64-bit Python 3.12 or 3.13 for your Windows user, then retry.
echo        Administrator access is not required when "Install for all users" is unchecked.
exit /b 1

:venv_failed
echo ERROR: Could not create the local .venv directory.
echo        Move the repository to a writable user folder and retry.
exit /b 1

:install_failed
echo ERROR: Python dependency installation failed.
echo        Review the pip error above. This script never contacts Hugging Face.
exit /b 1

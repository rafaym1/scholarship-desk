@echo off
rem Starts the Scholarship Desk dashboard and opens it in your browser.
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
  python -m scholar serve --open
  goto :end
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -m scholar serve --open
  goto :end
)
echo Python 3.10 or newer is required: https://www.python.org/downloads/
pause
:end

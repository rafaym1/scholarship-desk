@echo off
rem Free daily check (no Claude usage): fetches watched pages and queues what changed.
cd /d "%~dp0\.."
if not exist data mkdir data
where python >nul 2>nul
if %errorlevel%==0 (
  python -m scholar watch run >> data\watch.log 2>&1
) else (
  py -m scholar watch run >> data\watch.log 2>&1
)

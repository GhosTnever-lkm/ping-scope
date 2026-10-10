@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 ping_scope.py
  goto :finish
)
where python >nul 2>nul
if not errorlevel 1 (
  python ping_scope.py
  goto :finish
)
echo PingScope needs Python 3.10+. Install it from https://www.python.org/downloads/windows/
pause
:finish

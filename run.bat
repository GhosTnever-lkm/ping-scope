@echo off
cd /d "%~dp0"
py -3 ping_scope.py
if errorlevel 1 (
  echo.
  echo PingScope could not start. Install Python 3.10+ and enable the py launcher.
  pause
)

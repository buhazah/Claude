@echo off
REM Double-click launcher for JARVIS on Windows.
REM Runs the PowerShell quickstart with execution policy bypassed so you
REM don't have to change any system settings.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0quickstart.ps1"
if %ERRORLEVEL% neq 0 (
  echo.
  echo Something went wrong. See the message above.
  pause
)

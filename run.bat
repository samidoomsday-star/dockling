@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Install Python and Dockling first using docs\OPERATOR_GUIDE.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m stmtconv inbox
set "STMTCONV_LAUNCH_EXIT=%errorlevel%"
pause
exit /b %STMTCONV_LAUNCH_EXIT%

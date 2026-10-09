@echo off
setlocal
cd /d "%~dp0frontend"
where node >nul 2>nul
if errorlevel 1 (
  echo Install Node.js 24 LTS from https://nodejs.org/en/download, then reopen this launcher.
  pause
  exit /b 1
)
node -e "const v=process.versions.node.split('.').map(Number); if(v[0]!==24 || v[1]<15) process.exit(1)"
if errorlevel 1 (
  echo This preview needs Node.js 24 LTS, version 24.15 or newer within version 24.
  pause
  exit /b 1
)
echo Installing the locked frontend dependencies. No Python models or API key are needed.
call npm ci
if errorlevel 1 (
  echo Dependency installation failed. Keep this output for your coding assistant.
  pause
  exit /b 1
)
echo Opening the synthetic frontend preview. Keep this window open while testing.
call npm run dev -- --open
if errorlevel 1 (
  echo Preview startup failed. Keep this output for your coding assistant.
  pause
  exit /b 1
)
endlocal

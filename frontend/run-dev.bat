@echo off
cd /d "%~dp0"
echo Installing dependencies if needed...
call npm install
echo.
echo Starting Tự Minh Frontend on http://localhost:3010
echo Press Ctrl+C to stop.
echo.
call npm run dev:3010
pause

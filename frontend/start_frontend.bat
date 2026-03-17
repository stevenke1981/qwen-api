@echo off
setlocal

set PORT=%1
if "%PORT%"=="" set PORT=3000

cd /d "%~dp0"
echo Frontend: http://localhost:%PORT%
python -m http.server %PORT%

endlocal

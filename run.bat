@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python app\main.py %*
    goto :eof
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py -3.11 app\main.py %*
    goto :eof
)

if exist "C:\Program Files\Tencent\Marvis\MarvisAgent\1.60.3000.716\runtime\python311\python.exe" (
    "C:\Program Files\Tencent\Marvis\MarvisAgent\1.60.3000.716\runtime\python311\python.exe" app\main.py %*
    goto :eof
)

echo Python 3.11 executable not found!
pause

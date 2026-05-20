@echo off
chcp 65001 >nul
title SwimTrack Pro V28

echo.
echo  ╔══════════════════════════════════════╗
echo  ║       SwimTrack Pro  V28  🏊         ║
echo  ╚══════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: Find Python
set PYTHON=
for %%p in (
  "C:\Users\%USERNAME%\AppData\Local\Python\bin\python.exe"
  "C:\Python313\python.exe"
  "C:\Python312\python.exe"
  "C:\Python311\python.exe"
  "C:\Python310\python.exe"
) do (
  if exist %%p (
    set PYTHON=%%p
    goto :found
  )
)
:: Fallback to PATH
where python >nul 2>&1
if %ERRORLEVEL%==0 (
  set PYTHON=python
  goto :found
)
echo  ERROR: Python לא נמצא. הורד מ-https://python.org
pause
exit /b 1

:found
echo  ✓  Python: %PYTHON%

:: Install requirements if needed
echo  ↻  בודק חבילות...
%PYTHON% -m pip install -r requirements.txt -q --exists-action i
echo  ✓  חבילות מותקנות

echo.
echo  ↻  מפעיל שרת...
echo  ──────────────────────────────────────
echo  גישה לאפליקציה: http://localhost:8501
echo  ──────────────────────────────────────
echo.

:: Open launcher.html after 4 seconds (opens in default browser)
start "" /min cmd /c "timeout /t 4 /nobreak >nul && start launcher.html"

:: Start Streamlit
%PYTHON% -m streamlit run app.py ^
  --server.port 8501 ^
  --browser.gatherUsageStats false ^
  --server.headless false

echo.
echo  השרת הופסק.
pause

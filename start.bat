@echo off
echo.
echo  ====================================
echo    SwimTrack Pro V28 - Starting...
echo  ====================================
echo.
cd /d "%~dp0"
"C:\Users\HOME\AppData\Local\Python\bin\python.exe" -m streamlit run app.py --server.port 8501 --browser.gatherUsageStats false
pause

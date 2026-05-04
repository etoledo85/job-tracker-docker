@echo off
echo === Job Tracker — Build Windows ===

pip install -r requirements.txt

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "JobTracker-Setup" ^
  --icon "..\assets\icon.ico" ^
  --add-data "..\config.yaml;." ^
  --add-data "..\docker-compose.yml;." ^
  --distpath ".." ^
  installer.py

echo.
echo Build completado: ..\JobTracker-Setup.exe
pause

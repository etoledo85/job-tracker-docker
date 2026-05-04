#!/usr/bin/env bash
set -e
echo "=== Job Tracker — Build Linux ==="

pip3 install -r requirements.txt

pyinstaller \
  --onefile \
  --name "JobTracker-Setup" \
  --add-data "../config.yaml:." \
  --add-data "../docker-compose.yml:." \
  --distpath ".." \
  installer.py

echo ""
echo "Build completado: ../JobTracker-Setup"
chmod +x ../JobTracker-Setup

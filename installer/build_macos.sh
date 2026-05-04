#!/usr/bin/env bash
set -e
echo "=== Job Tracker — Build macOS ==="

pip3 install -r requirements.txt

pyinstaller \
  --onefile \
  --windowed \
  --name "JobTracker-Setup" \
  --add-data "../config.yaml:." \
  --add-data "../docker-compose.yml:." \
  --distpath ".." \
  installer.py

echo ""
echo "Build completado: ../JobTracker-Setup"
echo "Nota: macOS puede requerir que el usuario haga clic derecho → Abrir la primera vez."

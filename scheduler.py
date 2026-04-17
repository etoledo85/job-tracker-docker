#!/usr/bin/env python3
"""
Scheduler interno — reemplaza el systemd timer.
Corre daily_scrape.py cada día a las 08:00 hora local del contenedor.
"""
import time
import subprocess
import sys
from datetime import datetime, timedelta


def next_run_at(hour=8, minute=0):
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def main():
    print(f"[scheduler] Iniciado — scrape diario a las 08:00", flush=True)
    while True:
        run_at = next_run_at(hour=8)
        wait_secs = (run_at - datetime.now()).total_seconds()
        print(f"[scheduler] Próximo scrape: {run_at.strftime('%Y-%m-%d %H:%M')} "
              f"(en {wait_secs/3600:.1f}h)", flush=True)
        time.sleep(max(wait_secs, 0))

        print(f"[scheduler] Ejecutando scrape — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        result = subprocess.run([sys.executable, "daily_scrape.py"], capture_output=False)
        if result.returncode != 0:
            print(f"[scheduler] daily_scrape.py terminó con código {result.returncode}", flush=True)

        # Esperar 61 segundos para no re-ejecutar en el mismo minuto
        time.sleep(61)


if __name__ == "__main__":
    main()

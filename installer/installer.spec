# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

repo_root = Path(SPECPATH).parent

datas = [
    (str(repo_root / "docker-compose.yml"), "."),
    (str(repo_root / "Dockerfile"), "."),
    (str(repo_root / "requirements.txt"), "."),
    (str(repo_root / "main.py"), "."),
    (str(repo_root / "daily_scrape.py"), "."),
    (str(repo_root / "scheduler.py"), "."),
    (str(repo_root / "src"), "src"),
]

env_example = repo_root / ".env.example"
if env_example.exists():
    datas.append((str(env_example), "."))

a = Analysis(
    ["installer.py"],
    pathex=[str(repo_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="job-tracker-installer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=sys.platform == "linux",
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

#!/usr/bin/env python3
"""
Job Tracker — Instalador GUI
Wizard paso a paso para instalar y configurar Job Tracker con Docker.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import platform
import os
import sys
import shutil
import threading
import webbrowser
import urllib.request
import time
from pathlib import Path

# ─── Rutas ────────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    _BUNDLE_DIR = Path(sys._MEIPASS)
    PROJECT_DIR = Path(sys.executable).parent / "job-tracker"
else:
    _BUNDLE_DIR = Path(__file__).resolve().parent.parent
    PROJECT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_DIR / "data"

# ─── Imports opcionales (Windows) ─────────────────────────────────────────────
if sys.platform == "win32":
    try:
        import winshell
        from win32com.shell import shell, shellcon  # noqa: F401
    except ImportError:
        winshell = None
else:
    winshell = None


def _extract_project_files():
    """Copia todos los archivos del proyecto del bundle a PROJECT_DIR en disco."""
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    for fname in ("docker-compose.yml", "Dockerfile", "requirements.txt",
                  "main.py", "daily_scrape.py", "scheduler.py", ".env.example"):
        src = _BUNDLE_DIR / fname
        dst = PROJECT_DIR / fname
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
    src_dir = _BUNDLE_DIR / "src"
    dst_dir = PROJECT_DIR / "src"
    if src_dir.exists() and not dst_dir.exists():
        shutil.copytree(src_dir, dst_dir)


SYSTEM = platform.system()  # 'Windows', 'Darwin', 'Linux'

# ─── Rutas de Docker en Windows ───────────────────────────────────────────────
_DOCKER_WIN_PATHS = [
    r"C:\Program Files\Docker\Docker\resources\bin",
    r"C:\ProgramData\DockerDesktop\version-bin",
    r"C:\Program Files\Docker\resources\bin",
]


def _docker_env() -> dict:
    """Env vars con las rutas de Docker inyectadas (necesario en binarios PyInstaller)."""
    env = os.environ.copy()
    if SYSTEM == "Windows":
        extra = ";".join(p for p in _DOCKER_WIN_PATHS if Path(p).exists())
        if extra:
            env["PATH"] = extra + ";" + env.get("PATH", "")
    return env


def _compose_cmd() -> list:
    """Detecta si usar 'docker compose' (plugin v2) o 'docker-compose' (v1)."""
    env = _docker_env()
    r = subprocess.run(["docker", "compose", "version"], capture_output=True, env=env)
    if r.returncode == 0:
        return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return ["docker", "compose"]  # último recurso


# ─── Atajos de escritorio ─────────────────────────────────────────────────────
def _icon_path() -> str:
    p = _BUNDLE_DIR / "icon.ico"
    return str(p) if p.exists() else ""


def _create_shortcuts():
    """Crea launcher y acceso directo en escritorio / menú inicio según plataforma."""
    if SYSTEM == "Windows":
        launcher = PROJECT_DIR / "launch.bat"
        if not launcher.exists():
            launcher.write_text(
                "@echo off\n"
                'cd /d "%~dp0"\n'
                "docker compose up -d\n"
                "timeout /t 4 /nobreak >nul\n"
                "start http://localhost:8501\n",
                encoding="utf-8",
            )
        if winshell is None:
            return
        icon = _icon_path()
        desktop = Path(winshell.desktop())
        programs = Path(winshell.programs())
        programs.mkdir(parents=True, exist_ok=True)
        for dest_dir in (desktop, programs):
            lnk = str(dest_dir / "Job Tracker.lnk")
            winshell.CreateShortcut(
                Path=lnk,
                Target=str(launcher),
                StartIn=str(PROJECT_DIR),
                Description="Rastreador automático de empleos",
                Icon=(icon, 0) if icon else ("", 0),
            )
    elif SYSTEM == "Darwin":
        launcher = PROJECT_DIR / "launch.command"
        if not launcher.exists():
            launcher.write_text(
                "#!/bin/bash\n"
                f'cd "{PROJECT_DIR}"\n'
                "docker compose up -d\n"
                "sleep 4\n"
                "open http://localhost:8501\n"
            )
        os.chmod(launcher, 0o755)
        desktop_link = Path.home() / "Desktop" / "Job Tracker.command"
        shutil.copy2(launcher, desktop_link)
        os.chmod(desktop_link, 0o755)
    else:  # Linux
        launcher = PROJECT_DIR / "launch.sh"
        if not launcher.exists():
            launcher.write_text(
                "#!/bin/bash\n"
                f'cd "{PROJECT_DIR}"\n'
                "docker compose up -d\n"
                "sleep 4\n"
                "xdg-open http://localhost:8501\n"
            )
        os.chmod(launcher, 0o755)
        apps_dir = Path.home() / ".local" / "share" / "applications"
        apps_dir.mkdir(parents=True, exist_ok=True)
        icon = _icon_path() or "applications-internet"
        entry = apps_dir / "job-tracker.desktop"
        entry.write_text(
            "[Desktop Entry]\n"
            "Version=1.0\n"
            "Type=Application\n"
            "Name=Job Tracker\n"
            "Comment=Rastreador automático de empleos\n"
            f"Exec=bash {launcher}\n"
            f"Icon={icon}\n"
            "Terminal=false\n"
            "Categories=Network;Office;\n"
        )
        os.chmod(entry, 0o755)


def _remove_shortcuts():
    """Elimina los accesos directos creados durante la instalación."""
    if SYSTEM == "Windows" and winshell is not None:
        desktop = Path(winshell.desktop())
        programs = Path(winshell.programs())
        for d in (desktop, programs):
            lnk = d / "Job Tracker.lnk"
            if lnk.exists():
                lnk.unlink()
    elif SYSTEM == "Darwin":
        link = Path.home() / "Desktop" / "Job Tracker.command"
        if link.exists():
            link.unlink()
    else:
        entry = Path.home() / ".local" / "share" / "applications" / "job-tracker.desktop"
        if entry.exists():
            entry.unlink()


# ─── Proveedores de IA ────────────────────────────────────────────────────────
AI_PROVIDERS = {
    "Gemini Flash (Gratuito — Recomendado)": {
        "env_key": "GEMINI_API_KEY",
        "url": "https://aistudio.google.com/app/apikey",
        "hint": "Obtén tu API key gratuita en Google AI Studio",
    },
    "Groq — Llama 3.3 70B (Gratuito)": {
        "env_key": "GROQ_API_KEY",
        "url": "https://console.groq.com/keys",
        "hint": "Obtén tu API key gratuita en Groq Console",
    },
    "OpenRouter (Gratuito con límite)": {
        "env_key": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/keys",
        "hint": "Crea tu cuenta gratuita en OpenRouter",
    },
    "Claude / Anthropic (De pago)": {
        "env_key": "ANTHROPIC_API_KEY",
        "url": "https://console.anthropic.com/",
        "hint": "Requiere cuenta con saldo en Anthropic Console",
    },
}

# ─── Paleta ───────────────────────────────────────────────────────────────────
BG      = "#0f172a"
CARD    = "#1e293b"
ACCENT  = "#6366f1"
ACCENT2 = "#818cf8"
TEXT    = "#f1f5f9"
MUTED   = "#94a3b8"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
ERROR   = "#ef4444"
ENTRY   = "#0d1a2d"


# ─── Utilidades ──────────────────────────────────────────────────────────────
def _run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    kwargs.setdefault("env", _docker_env())
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def docker_running() -> bool:
    env = _docker_env()
    docker_exe = shutil.which("docker", path=env.get("PATH"))
    if docker_exe is None:
        return False
    r = subprocess.run(["docker", "info"], capture_output=True, env=env)
    return r.returncode == 0


def docker_version() -> str:
    r = _run(["docker", "--version"])
    return r.stdout.strip() if r.returncode == 0 else ""


def _get_or_create_key() -> bytes:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    key_path = DATA_DIR / "secret.key"
    if key_path.exists():
        return key_path.read_bytes()
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    return key


def encrypt_value(value: str) -> str:
    from cryptography.fernet import Fernet
    key = _get_or_create_key()
    return "ENC:" + Fernet(key).encrypt(value.encode()).decode()


# ─── Aplicación ──────────────────────────────────────────────────────────────
class InstallerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Job Tracker — Instalación")
        self.geometry("700x520")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.eval("tk::PlaceWindow . center")

        self.data = {
            "provider": list(AI_PROVIDERS.keys())[0],
            "api_key": "",
            "name": "",
            "email": "",
            "cv_path": "",
            "keywords": "sysadmin, devops, linux administrator, cloud engineer",
            "locations": "remote, remoto",
            "remote_only": True,
        }

        self.step_titles = [
            "Bienvenido",
            "Docker",
            "Proveedor de IA",
            "Tu Perfil",
            "Preferencias de Búsqueda",
            "Instalación",
        ]
        self.steps = [
            self._step_welcome,
            self._step_docker,
            self._step_provider,
            self._step_profile,
            self._step_preferences,
            self._step_launch,
        ]
        self.current = 0

        self._build_shell()

        # Si ya hay una instalación previa, ofrecer instalar/desinstalar
        if (PROJECT_DIR / "docker-compose.yml").exists():
            self._show_mode_choice()
        else:
            self._show(0)

    # ── Shell ──────────────────────────────────────────────────────────────────
    def _build_shell(self):
        self.header = tk.Frame(self, bg=ACCENT, height=58)
        self.header.pack(fill=tk.X)
        self.header.pack_propagate(False)

        self.title_lbl = tk.Label(
            self.header, text="", font=("Helvetica", 15, "bold"), bg=ACCENT, fg="white"
        )
        self.title_lbl.pack(side=tk.LEFT, padx=20)

        self.step_lbl = tk.Label(
            self.header, text="", font=("Helvetica", 11), bg=ACCENT, fg="white"
        )
        self.step_lbl.pack(side=tk.RIGHT, padx=20)

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill=tk.BOTH, expand=True, padx=22, pady=14)

        footer = tk.Frame(self, bg=BG, height=52)
        footer.pack(fill=tk.X, padx=22, pady=(0, 10))
        footer.pack_propagate(False)

        self.btn_back = tk.Button(
            footer, text="← Atrás", command=self._back,
            bg=CARD, fg=TEXT, activebackground="#334155", activeforeground=TEXT,
            relief=tk.FLAT, padx=16, pady=8, cursor="hand2", font=("Helvetica", 11),
        )
        self.btn_back.pack(side=tk.LEFT)

        self.btn_next = tk.Button(
            footer, text="Siguiente →", command=self._next,
            bg=ACCENT, fg="white", activebackground=ACCENT2, activeforeground="white",
            relief=tk.FLAT, padx=18, pady=8, cursor="hand2", font=("Helvetica", 11, "bold"),
        )
        self.btn_next.pack(side=tk.RIGHT)

    def _show(self, idx: int):
        for w in self.content.winfo_children():
            w.destroy()

        self.current = idx
        n = len(self.steps)
        self.title_lbl.config(text=self.step_titles[idx])
        self.step_lbl.config(text=f"Paso {idx + 1} de {n}")
        self.btn_back.config(state=tk.NORMAL if idx > 0 else tk.DISABLED,
                             command=self._back)

        is_last = idx == n - 1
        self.btn_next.config(
            text="✓ Finalizar" if is_last else "Siguiente →",
            command=self._next,
            state=tk.DISABLED if is_last else tk.NORMAL,
        )

        frame = tk.Frame(self.content, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True)
        self.steps[idx](frame)

    def _next(self):
        if self.current < len(self.steps) - 1:
            self._show(self.current + 1)

    def _back(self):
        if self.current > 0:
            self._show(self.current - 1)

    # ── Pantalla de elección (instalar vs desinstalar) ──────────────────────────
    def _show_mode_choice(self):
        for w in self.content.winfo_children():
            w.destroy()
        self.geometry("700x520")
        self.title_lbl.config(text="Instalación detectada")
        self.step_lbl.config(text="")
        self.btn_back.config(state=tk.DISABLED)
        self.btn_next.config(state=tk.DISABLED)

        frame = tk.Frame(self.content, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="💼", font=("Helvetica", 44), bg=BG).pack(pady=(24, 4))
        self._lbl(frame, "Job Tracker ya está instalado", size=17, bold=True).pack()
        self._lbl(frame, str(PROJECT_DIR), color=MUTED, size=10).pack(pady=(2, 24))

        btn_row = tk.Frame(frame, bg=BG)
        btn_row.pack()

        tk.Button(
            btn_row, text="⬆️  Instalar / Actualizar",
            command=lambda: self._show(0),
            bg=ACCENT, fg="white", activebackground=ACCENT2,
            relief=tk.FLAT, padx=24, pady=12, cursor="hand2",
            font=("Helvetica", 12, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 16))

        tk.Button(
            btn_row, text="🗑️  Desinstalar",
            command=self._show_uninstall,
            bg=ERROR, fg="white", activebackground="#b91c1c",
            relief=tk.FLAT, padx=24, pady=12, cursor="hand2",
            font=("Helvetica", 12, "bold"),
        ).pack(side=tk.LEFT)

    # ── Pantalla de desinstalación ─────────────────────────────────────────────
    def _show_uninstall(self):
        for w in self.content.winfo_children():
            w.destroy()
        self.geometry("700x580")
        self.title_lbl.config(text="Desinstalar Job Tracker")
        self.step_lbl.config(text="")
        self.btn_back.config(state=tk.NORMAL, command=self._show_mode_choice)
        self.btn_next.config(state=tk.DISABLED)

        frame = tk.Frame(self.content, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True)

        # Tarjeta de advertencia
        warn = tk.Frame(frame, bg="#7f1d1d", padx=14, pady=10)
        warn.pack(fill=tk.X, pady=(0, 10))
        tk.Label(
            warn,
            text="⚠️  ¿Estás seguro? Esto eliminará los contenedores y todos los datos de Job Tracker.",
            font=("Helvetica", 11), bg="#7f1d1d", fg="white",
            wraplength=620, justify=tk.LEFT,
        ).pack(anchor="w")

        # Checkbox datos
        self._del_data_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            frame,
            text="  También eliminar la base de datos y archivos de datos (no recuperable)",
            variable=self._del_data_var,
            font=("Helvetica", 10), bg=BG, fg=TEXT,
            selectcolor=ENTRY, activebackground=BG, activeforeground=TEXT,
        ).pack(anchor="w", pady=(0, 8))

        # Progressbar
        self._uninst_pb = ttk.Progressbar(frame, mode="indeterminate")
        self._uninst_pb.pack(fill=tk.X, pady=(0, 4))

        # Log
        log_frame = tk.Frame(frame, bg=BG)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self._uninst_log = tk.Text(
            log_frame, height=8, bg="#0a0f1a", fg=TEXT,
            font=("Courier", 9), state=tk.DISABLED, wrap=tk.WORD,
        )
        self._uninst_log.tag_configure("success", foreground=SUCCESS)
        self._uninst_log.tag_configure("error", foreground=ERROR)
        _sb = ttk.Scrollbar(log_frame, command=self._uninst_log.yview)
        self._uninst_log.configure(yscrollcommand=_sb.set)
        _sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._uninst_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Botón desinstalar
        self._uninst_btn = tk.Button(
            frame, text="🗑️  Desinstalar",
            command=self._do_uninstall,
            bg=ERROR, fg="white", activebackground="#b91c1c",
            relief=tk.FLAT, padx=20, pady=10, cursor="hand2",
            font=("Helvetica", 12, "bold"),
        )
        self._uninst_btn.pack(pady=(8, 0))

    def _do_uninstall(self):
        del_data = self._del_data_var.get()
        self._uninst_btn.config(state=tk.DISABLED, text="⏳  Desinstalando...")
        self.btn_back.config(state=tk.DISABLED)
        self._uninst_pb.start(10)
        threading.Thread(target=lambda: self._uninstall_worker(del_data), daemon=True).start()

    def _uninstall_worker(self, del_data: bool):
        try:
            self.after(0, lambda: self._uninst_append_log("Deteniendo contenedores Docker...\n"))
            compose = _compose_cmd()
            process = subprocess.Popen(
                compose + ["down"],
                cwd=str(PROJECT_DIR),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                env=_docker_env(),
            )
            for line in process.stdout:
                l = line
                self.after(0, lambda l=l: self._uninst_append_log(l))
            process.wait()

            if del_data:
                self.after(0, lambda: self._uninst_append_log("\nEliminando archivos del proyecto...\n"))
                shutil.rmtree(PROJECT_DIR, ignore_errors=True)

            self.after(0, lambda: self._uninst_append_log("\nEliminando accesos directos...\n"))
            try:
                _remove_shortcuts()
            except Exception as _se:
                self.after(0, lambda e=_se: self._uninst_append_log(f"(Atajos: {e})\n"))

            self.after(0, lambda: self._uninst_append_log(
                "\n✅  Desinstalación completada.\n", "success"
            ))
            self.after(0, self._uninst_pb.stop)
            self.after(0, lambda: messagebox.showinfo(
                "Desinstalado", "Job Tracker ha sido desinstalado correctamente."
            ))
            self.after(500, self.destroy)

        except Exception as exc:
            err = str(exc)
            self.after(0, self._uninst_pb.stop)
            self.after(0, lambda: self._uninst_append_log(f"\n❌  Error: {err}\n", "error"))
            self.after(0, lambda: self._uninst_btn.config(
                state=tk.NORMAL, text="🗑️  Reintentar"
            ))
            self.after(0, lambda: messagebox.showerror("Error", f"Ocurrió un error:\n{err}"))

    def _uninst_append_log(self, text: str, tag: str = ""):
        self._uninst_log.config(state=tk.NORMAL)
        if tag:
            self._uninst_log.insert(tk.END, text, tag)
        else:
            self._uninst_log.insert(tk.END, text)
        self._uninst_log.see(tk.END)
        self._uninst_log.config(state=tk.DISABLED)

    # ── Helpers UI ─────────────────────────────────────────────────────────────
    def _lbl(self, parent, text, size=12, bold=False, color=TEXT, wrap=640):
        w = "bold" if bold else "normal"
        return tk.Label(
            parent, text=text, font=("Helvetica", size, w),
            bg=BG, fg=color, wraplength=wrap, justify=tk.LEFT, anchor="w",
        )

    def _card(self, parent, **kw):
        return tk.Frame(parent, bg=CARD, **kw)

    def _entry(self, parent, var, show=None, width=None):
        kw = dict(
            textvariable=var, font=("Helvetica", 11),
            bg=ENTRY, fg=TEXT, insertbackground=TEXT, relief=tk.FLAT,
        )
        if show:
            kw["show"] = show
        if width:
            kw["width"] = width
        return tk.Entry(parent, **kw)

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 1 — BIENVENIDA
    # ══════════════════════════════════════════════════════════════════════════
    def _step_welcome(self, frame):
        tk.Label(frame, text="💼", font=("Helvetica", 50), bg=BG).pack(pady=(15, 4))
        self._lbl(frame, "Job Tracker", size=22, bold=True).pack()
        self._lbl(
            frame,
            "Este asistente te guiará para instalar y configurar Job Tracker "
            "en tu computadora en menos de 10 minutos.",
            color=MUTED,
        ).pack(pady=(6, 16))

        card = self._card(frame, padx=18, pady=12)
        card.pack(fill=tk.X, pady=4)

        for line in [
            "✅  Busca vacantes automáticamente en múltiples portales",
            "✅  Analiza el match de cada vacante con tu CV usando IA",
            "✅  Genera cover letters personalizadas con un clic",
            "✅  Rastrea el estado de todas tus aplicaciones",
        ]:
            tk.Label(card, text=line, font=("Helvetica", 11), bg=CARD, fg=TEXT, anchor="w").pack(
                fill=tk.X, pady=2
            )

        self._lbl(
            frame,
            "ℹ️  Asegúrate de tener conexión a internet antes de continuar.",
            color=WARNING, size=11,
        ).pack(pady=(14, 0))

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 2 — DOCKER
    # ══════════════════════════════════════════════════════════════════════════
    def _step_docker(self, frame):
        self._lbl(frame, "Verificando Docker...", size=13, bold=True).pack(pady=(0, 10))

        self._docker_card = self._card(frame, padx=18, pady=18)
        self._docker_card.pack(fill=tk.X)

        self._docker_status = tk.Label(
            self._docker_card, text="⏳  Verificando...",
            font=("Helvetica", 12), bg=CARD, fg=MUTED,
        )
        self._docker_status.pack()

        self._docker_actions = tk.Frame(self._docker_card, bg=CARD)
        self._docker_actions.pack(fill=tk.X, pady=(12, 0))

        threading.Thread(target=self._check_docker, daemon=True).start()

    def _check_docker(self):
        if docker_running():
            ver = docker_version()
            self.after(0, lambda: self._on_docker_ok(ver))
        else:
            self.after(0, self._on_docker_missing)

    def _on_docker_ok(self, ver):
        self._docker_status.config(text=f"✅  Docker instalado y funcionando\n{ver}", fg=SUCCESS)
        self.btn_next.config(state=tk.NORMAL)

    def _on_docker_missing(self):
        self._docker_status.config(text="⚠️  Docker no está instalado.", fg=WARNING)
        for w in self._docker_actions.winfo_children():
            w.destroy()

        if SYSTEM == "Windows":
            self._docker_windows()
        elif SYSTEM == "Darwin":
            self._docker_macos()
        else:
            self._docker_linux()

    # Docker — Windows
    def _docker_windows(self):
        tk.Label(
            self._docker_actions,
            text=(
                "Se instalará Docker Desktop automáticamente usando winget.\n"
                "Esto puede tardar varios minutos y requerirá reiniciar tu PC."
            ),
            font=("Helvetica", 11), bg=CARD, fg=TEXT, justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 8))

        tk.Label(
            self._docker_actions,
            text=(
                "ℹ️  Después de la instalación:\n"
                "   1. Acepta los términos de licencia si aparecen\n"
                "   2. Reinicia tu PC cuando se solicite\n"
                "   3. Vuelve a ejecutar este instalador"
            ),
            font=("Helvetica", 10), bg=CARD, fg=MUTED, justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 10))

        tk.Button(
            self._docker_actions,
            text="⬇️  Instalar Docker Desktop",
            command=self._install_docker_windows,
            bg=ACCENT, fg="white", relief=tk.FLAT, padx=16, pady=7,
            cursor="hand2", font=("Helvetica", 11, "bold"),
        ).pack()

    def _install_docker_windows(self):
        def run():
            self.after(0, lambda: self._docker_status.config(
                text="⏳  Instalando Docker Desktop via winget...", fg=WARNING
            ))
            r = _run(
                ["winget", "install", "--id", "Docker.DockerDesktop", "-e",
                 "--accept-package-agreements", "--accept-source-agreements"],
                timeout=600,
            )
            if r.returncode == 0:
                self.after(0, lambda: messagebox.showinfo(
                    "Instalación completada",
                    "Docker Desktop se instaló.\n\n"
                    "Por favor REINICIA tu PC y vuelve a ejecutar este instalador.",
                ))
                self.after(0, self.destroy)
            else:
                self.after(0, self._fallback_download)

        threading.Thread(target=run, daemon=True).start()

    def _fallback_download(self):
        messagebox.showinfo(
            "Descarga manual",
            "No se pudo instalar automáticamente.\n\n"
            "Se abrirá la página de descarga de Docker Desktop.\n"
            "Instálalo, reinicia tu PC y vuelve a ejecutar este instalador.",
        )
        webbrowser.open("https://www.docker.com/products/docker-desktop/")
        self.destroy()

    # Docker — macOS
    def _docker_macos(self):
        tk.Label(
            self._docker_actions,
            text="En macOS Docker Desktop requiere instalación manual (solo toma 2 minutos):",
            font=("Helvetica", 11), bg=CARD, fg=TEXT, justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 8))

        tk.Label(
            self._docker_actions,
            text=(
                "   1. Haz clic en 'Descargar Docker Desktop'\n"
                "   2. Abre el archivo .dmg descargado\n"
                "   3. Arrastra Docker.app a la carpeta Applications\n"
                "   4. Abre Docker desde Applications y sigue las instrucciones\n"
                "   5. Cuando Docker muestre '✅ Running', vuelve aquí y verifica"
            ),
            font=("Helvetica", 10), bg=CARD, fg=MUTED, justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 10))

        btn_row = tk.Frame(self._docker_actions, bg=CARD)
        btn_row.pack(fill=tk.X)

        tk.Button(
            btn_row,
            text="⬇️  Descargar Docker Desktop",
            command=lambda: webbrowser.open("https://www.docker.com/products/docker-desktop/"),
            bg=ACCENT, fg="white", relief=tk.FLAT, padx=14, pady=7,
            cursor="hand2", font=("Helvetica", 11, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_row,
            text="🔄  Ya instalé — Verificar",
            command=lambda: threading.Thread(target=self._check_docker, daemon=True).start(),
            bg=CARD, fg=TEXT, relief=tk.FLAT, padx=14, pady=6,
            cursor="hand2", font=("Helvetica", 10),
        ).pack(side=tk.LEFT)

    # Docker — Linux
    def _docker_linux(self):
        tk.Label(
            self._docker_actions,
            text="Se instalará Docker Engine usando el script oficial de Docker.",
            font=("Helvetica", 11), bg=CARD, fg=TEXT,
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            self._docker_actions,
            text="⚠️  Se requerirá tu contraseña de administrador (sudo).",
            font=("Helvetica", 10), bg=CARD, fg=WARNING,
        ).pack(anchor="w", pady=(0, 10))

        tk.Button(
            self._docker_actions,
            text="⬇️  Instalar Docker (script oficial)",
            command=self._install_docker_linux,
            bg=ACCENT, fg="white", relief=tk.FLAT, padx=16, pady=7,
            cursor="hand2", font=("Helvetica", 11, "bold"),
        ).pack()

    def _install_docker_linux(self):
        def run():
            self.after(0, lambda: self._docker_status.config(
                text="⏳  Descargando e instalando Docker...", fg=WARNING
            ))
            try:
                script = "/tmp/get-docker.sh"
                urllib.request.urlretrieve("https://get.docker.com", script)
                os.chmod(script, 0o755)
                result = subprocess.run(["sudo", "sh", script], timeout=600)
                if result.returncode == 0:
                    user = os.environ.get("USER", "")
                    if user:
                        subprocess.run(["sudo", "usermod", "-aG", "docker", user])
                    self.after(0, lambda: messagebox.showinfo(
                        "Docker instalado",
                        "Docker se instaló correctamente.\n\n"
                        "IMPORTANTE: Cierra sesión y vuelve a entrar (o reinicia)\n"
                        "para que los permisos tomen efecto.\n\n"
                        "Luego vuelve a ejecutar este instalador.",
                    ))
                    self.after(0, self.destroy)
                else:
                    self.after(0, lambda: messagebox.showerror(
                        "Error",
                        "Instalación fallida.\n\nInstala manualmente:\n"
                        "  curl -fsSL https://get.docker.com | sh",
                    ))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))

        threading.Thread(target=run, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 3 — PROVEEDOR DE IA
    # ══════════════════════════════════════════════════════════════════════════
    def _step_provider(self, frame):
        self._lbl(
            frame,
            "Elige un proveedor de IA. Los marcados como 'Gratuito' no requieren tarjeta de crédito.",
            color=MUTED,
        ).pack(pady=(0, 10))

        card = self._card(frame, padx=16, pady=14)
        card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(card, text="Proveedor:", font=("Helvetica", 11, "bold"), bg=CARD, fg=TEXT).pack(anchor="w")

        self._provider_var = tk.StringVar(value=self.data["provider"])
        cb = ttk.Combobox(
            card, textvariable=self._provider_var,
            values=list(AI_PROVIDERS.keys()), state="readonly",
            font=("Helvetica", 11),
        )
        cb.pack(fill=tk.X, pady=(5, 4))
        cb.bind("<<ComboboxSelected>>", lambda e: self._update_hint())

        self._hint_lbl = tk.Label(
            card, text="", font=("Helvetica", 10), bg=CARD, fg=ACCENT2, cursor="hand2"
        )
        self._hint_lbl.pack(anchor="w")
        self._hint_lbl.bind("<Button-1>", lambda e: webbrowser.open(
            AI_PROVIDERS.get(self._provider_var.get(), {}).get("url", "")
        ))

        card2 = self._card(frame, padx=16, pady=14)
        card2.pack(fill=tk.X)

        tk.Label(card2, text="API Key:", font=("Helvetica", 11, "bold"), bg=CARD, fg=TEXT).pack(anchor="w")

        key_row = tk.Frame(card2, bg=CARD)
        key_row.pack(fill=tk.X, pady=(5, 0))

        self._key_var = tk.StringVar(value=self.data["api_key"])
        self._key_entry = self._entry(key_row, self._key_var, show="•")
        self._key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)

        self._show_key = False
        tk.Button(
            key_row, text="👁", command=self._toggle_key,
            bg=CARD, fg=TEXT, relief=tk.FLAT, cursor="hand2", font=("Helvetica", 12),
        ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Label(
            card2, text="🔒  Tu clave se guardará cifrada en disco.",
            font=("Helvetica", 10), bg=CARD, fg=SUCCESS,
        ).pack(anchor="w", pady=(8, 0))

        self._update_hint()

    def _update_hint(self):
        info = AI_PROVIDERS.get(self._provider_var.get(), {})
        self._hint_lbl.config(
            text=f"🔗  {info.get('hint','')}  →  {info.get('url','')}"
        )

    def _toggle_key(self):
        self._show_key = not self._show_key
        self._key_entry.config(show="" if self._show_key else "•")

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 4 — PERFIL
    # ══════════════════════════════════════════════════════════════════════════
    def _step_profile(self, frame):
        self._lbl(
            frame,
            "Tu nombre y email aparecerán en las cover letters generadas por IA.",
            color=MUTED,
        ).pack(pady=(0, 10))

        card = self._card(frame, padx=16, pady=14)
        card.pack(fill=tk.X, pady=(0, 10))

        self._name_var = tk.StringVar(value=self.data["name"])
        self._email_var = tk.StringVar(value=self.data["email"])

        for label, var in [("Nombre completo:", self._name_var), ("Email:", self._email_var)]:
            row = tk.Frame(card, bg=CARD)
            row.pack(fill=tk.X, pady=5)
            tk.Label(row, text=label, font=("Helvetica", 11), bg=CARD, fg=TEXT, width=18, anchor="w").pack(side=tk.LEFT)
            self._entry(row, var).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)

        card2 = self._card(frame, padx=16, pady=14)
        card2.pack(fill=tk.X)

        tk.Label(card2, text="CV (PDF):", font=("Helvetica", 11, "bold"), bg=CARD, fg=TEXT).pack(anchor="w")
        tk.Label(
            card2, text="Puedes subirlo ahora o más tarde desde la Web UI.",
            font=("Helvetica", 10), bg=CARD, fg=MUTED,
        ).pack(anchor="w", pady=(2, 6))

        cv_row = tk.Frame(card2, bg=CARD)
        cv_row.pack(fill=tk.X)

        self._cv_var = tk.StringVar(
            value=self.data["cv_path"] or "Sin seleccionar — opcional"
        )
        tk.Label(cv_row, textvariable=self._cv_var, font=("Helvetica", 10), bg=CARD, fg=MUTED,
                 anchor="w", wraplength=500, justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            cv_row, text="📂  Examinar",
            command=self._pick_cv,
            bg=CARD, fg=TEXT, relief=tk.FLAT, padx=10, pady=4,
            cursor="hand2", font=("Helvetica", 10),
        ).pack(side=tk.RIGHT)

    def _pick_cv(self):
        path = filedialog.askopenfilename(
            title="Selecciona tu CV",
            filetypes=[("PDF", "*.pdf"), ("Todos los archivos", "*.*")],
        )
        if path:
            self.data["cv_path"] = path
            self._cv_var.set(path)

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 5 — PREFERENCIAS DE BÚSQUEDA
    # ══════════════════════════════════════════════════════════════════════════
    def _step_preferences(self, frame):
        self._lbl(
            frame,
            "Define qué tipo de vacantes quieres que Job Tracker busque automáticamente.",
            color=MUTED,
        ).pack(pady=(0, 10))

        self._kw_var = tk.StringVar(value=self.data["keywords"])
        self._loc_var = tk.StringVar(value=self.data["locations"])
        self._remote_var = tk.BooleanVar(value=self.data["remote_only"])

        card = self._card(frame, padx=16, pady=12)
        card.pack(fill=tk.X, pady=(0, 8))
        tk.Label(card, text="Roles / Keywords (separados por coma):", font=("Helvetica", 11, "bold"), bg=CARD, fg=TEXT).pack(anchor="w")
        tk.Label(card, text='ej: "sysadmin, devops, linux administrator, cloud engineer"',
                 font=("Helvetica", 10), bg=CARD, fg=MUTED).pack(anchor="w", pady=(2, 6))
        self._entry(card, self._kw_var).pack(fill=tk.X, ipady=6)

        card2 = self._card(frame, padx=16, pady=12)
        card2.pack(fill=tk.X, pady=(0, 8))
        tk.Label(card2, text="Ubicaciones (separadas por coma):", font=("Helvetica", 11, "bold"), bg=CARD, fg=TEXT).pack(anchor="w")
        tk.Label(card2, text='ej: "remote, remoto, Ciudad de México"',
                 font=("Helvetica", 10), bg=CARD, fg=MUTED).pack(anchor="w", pady=(2, 6))
        self._entry(card2, self._loc_var).pack(fill=tk.X, ipady=6)

        card3 = self._card(frame, padx=16, pady=10)
        card3.pack(fill=tk.X)
        tk.Checkbutton(
            card3, text="  Solo vacantes remotas",
            variable=self._remote_var, onvalue=True, offvalue=False,
            font=("Helvetica", 11), bg=CARD, fg=TEXT,
            selectcolor=ENTRY, activebackground=CARD, activeforeground=TEXT,
        ).pack(anchor="w")

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 6 — INSTALACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    def _step_launch(self, frame):
        self._lbl(frame, "¡Todo listo para instalar!", size=15, bold=True).pack(pady=(8, 4))
        self._lbl(
            frame,
            "Al hacer clic en 'Instalar' se guardarán tus configuraciones y se levantará Job Tracker.",
            color=MUTED,
        ).pack(pady=(0, 8))

        card = self._card(frame, padx=16, pady=12)
        card.pack(fill=tk.X, pady=(0, 6))

        for label, value in [
            ("Proveedor IA:", self._get("provider")),
            ("Nombre:", self._get("name") or "(no especificado)"),
            ("Email:", self._get("email") or "(no especificado)"),
            ("CV:", Path(self.data.get("cv_path", "")).name if self.data.get("cv_path") else "(subir después)"),
        ]:
            row = tk.Frame(card, bg=CARD)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label, font=("Helvetica", 10, "bold"), bg=CARD, fg=MUTED, width=14, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, font=("Helvetica", 10), bg=CARD, fg=TEXT, anchor="w").pack(side=tk.LEFT)

        self._progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(frame, variable=self._progress_var, maximum=100).pack(fill=tk.X, pady=(4, 0))

        self._status_lbl = tk.Label(frame, text="", font=("Helvetica", 10), bg=BG, fg=MUTED)
        self._status_lbl.pack(anchor="w", pady=(2, 0))

        self._install_btn = tk.Button(
            frame, text="🚀  Instalar y Lanzar Job Tracker",
            command=self._do_install,
            bg=SUCCESS, fg="#000", activebackground="#16a34a",
            relief=tk.FLAT, padx=20, pady=10, cursor="hand2",
            font=("Helvetica", 12, "bold"),
        )
        self._install_btn.pack(pady=(10, 0))

        # Build output UI — shown only when docker compose build starts
        self._build_frame = tk.Frame(frame, bg=BG)

        self._build_banner = tk.Label(
            self._build_frame,
            text="⚠️  Construyendo por primera vez — esto puede tardar 2-5 minutos. NO CIERRES ESTA VENTANA.",
            bg="#f59e0b", fg="#000000", font=("Helvetica", 10, "bold"),
            wraplength=640, pady=8, padx=8,
        )
        self._build_banner.pack(fill=tk.X)

        self._build_pb = ttk.Progressbar(self._build_frame, mode="indeterminate")
        self._build_pb.pack(fill=tk.X, pady=(4, 4))

        log_frame = tk.Frame(self._build_frame, bg=BG)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self._build_log = tk.Text(
            log_frame, height=10, bg="#0a0f1a", fg=TEXT,
            font=("Courier", 9), state=tk.DISABLED, wrap=tk.WORD,
        )
        self._build_log.tag_configure("success", foreground=SUCCESS)
        self._build_log.tag_configure("error", foreground=ERROR)

        _sb = ttk.Scrollbar(log_frame, command=self._build_log.yview)
        self._build_log.configure(yscrollcommand=_sb.set)
        _sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._build_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _get(self, key):
        var_map = {
            "provider": "_provider_var",
            "name": "_name_var",
            "email": "_email_var",
            "keywords": "_kw_var",
            "locations": "_loc_var",
        }
        attr = var_map.get(key)
        if attr and hasattr(self, attr):
            return getattr(self, attr).get().strip()
        return self.data.get(key, "")

    def _set_status(self, msg, pct=None):
        self._status_lbl.config(text=msg)
        if pct is not None:
            self._progress_var.set(pct)
        self.update_idletasks()

    def _do_install(self):
        self._install_btn.config(state=tk.DISABLED, text="⏳  Instalando...")
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self):
        log_path = Path(sys.executable).parent / "install_debug.log"
        with open(log_path, "w") as f:
            f.write(f"frozen: {getattr(sys, 'frozen', False)}\n")
            f.write(f"executable: {sys.executable}\n")
            f.write(f"_BUNDLE_DIR: {_BUNDLE_DIR}\n")
            f.write(f"PROJECT_DIR: {PROJECT_DIR}\n")
            bundle_files = list(_BUNDLE_DIR.iterdir()) if _BUNDLE_DIR.exists() else []
            f.write(f"bundle files: {bundle_files}\n")
            f.write(f"docker-compose.yml in bundle: {(_BUNDLE_DIR / 'docker-compose.yml').exists()}\n")
        try:
            self.after(0, lambda: self._set_status("Extrayendo archivos del proyecto...", 5))
            _extract_project_files()

            self.after(0, lambda: self._set_status("Preparando directorios...", 10))
            DATA_DIR.mkdir(parents=True, exist_ok=True)

            self.after(0, lambda: self._set_status("Cifrando credenciales...", 22))
            api_key = self._get("api_key") or (getattr(self, "_key_var", None) and self._key_var.get().strip()) or ""
            provider = self._get("provider")
            env_key = AI_PROVIDERS.get(provider, {}).get("env_key", "GEMINI_API_KEY")

            encrypted = encrypt_value(api_key) if api_key else ""
            env_path = PROJECT_DIR / ".env"
            env_path.write_text(f"{env_key}={encrypted}\n")

            self.after(0, lambda: self._set_status("Guardando configuración...", 40))
            self._write_config()

            cv_src = self.data.get("cv_path", "")
            if cv_src and Path(cv_src).exists():
                self.after(0, lambda: self._set_status("Copiando CV...", 50))
                shutil.copy2(cv_src, DATA_DIR / "cv.pdf")

            self.after(0, lambda: self._set_status("Construyendo imagen Docker...", 60))
            self.after(0, self._show_build_ui)

            compose = _compose_cmd()
            process = subprocess.Popen(
                compose + ["up", "--build", "-d"],
                cwd=str(PROJECT_DIR),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                env=_docker_env(),
            )

            for line in process.stdout:
                l = line
                self.after(0, lambda l=l: self._append_build_log(l))

            returncode = process.wait()

            if returncode != 0:
                raise RuntimeError(
                    f"docker compose falló (código {returncode})\n\n"
                    "Asegúrate de que Docker Desktop esté ABIERTO y funcionando "
                    "(ícono de la ballena en la barra de tareas)."
                )

            self.after(0, lambda: self._set_status("Esperando que el servidor arranque...", 90))
            time.sleep(6)

            self.after(0, lambda: self._set_status("✅  Instalación completada", 100))
            self.after(0, self._on_success)

        except Exception as exc:
            err = str(exc)
            self.after(0, lambda: self._on_error(err))

    def _write_config(self):
        import yaml

        keywords = [k.strip() for k in self._get("keywords").split(",") if k.strip()]
        locations = [l.strip() for l in self._get("locations").split(",") if l.strip()]
        remote = getattr(self, "_remote_var", tk.BooleanVar(value=True)).get()
        name = self._get("name") or "Tu Nombre"
        email = self._get("email") or "tu@email.com"

        cfg = {
            "profile": {"name": name, "email": email, "phone": "", "cv_path": "data/cv.pdf"},
            "search": {
                "keywords": keywords,
                "locations": locations,
                "remote_preference": remote,
                "exclude_keywords": ["junior", "intern", "practicante", "becario", "security clearance"],
                "exclude_titles": [],
                "exclude_locations": [],
            },
            "email": {"smtp_server": "smtp.gmail.com", "smtp_port": 587, "sender": email, "app_password": ""},
            "cover_letter": {"language": "auto", "tone": "professional", "max_length": 400},
        }

        with open(PROJECT_DIR / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def _on_success(self):
        self._build_pb.stop()
        self._append_build_log("\n✅  Instalación completada con éxito.\n", "success")
        try:
            _create_shortcuts()
        except Exception:
            pass  # los accesos directos no son críticos
        self.btn_next.config(state=tk.NORMAL, command=self.destroy)
        webbrowser.open("http://localhost:8501")
        messagebox.showinfo(
            "¡Listo!",
            "Job Tracker está corriendo en:\n\nhttp://localhost:8501\n\n"
            "Se abrirá en tu navegador automáticamente.",
        )

    def _on_error(self, msg: str):
        self._install_btn.config(state=tk.NORMAL, text="🚀  Reintentar")
        if hasattr(self, "_build_pb"):
            try:
                self._build_pb.stop()
            except Exception:
                pass
        if hasattr(self, "_build_log"):
            self._append_build_log(f"\n❌  Error: {msg[:300]}\n", "error")
        messagebox.showerror(
            "Error en la instalación",
            f"Ocurrió un error:\n\n{msg}\n\n"
            "Verifica que Docker esté corriendo e inténtalo de nuevo.",
        )

    def _show_build_ui(self):
        if not self._build_frame.winfo_ismapped():
            self._build_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
            self.geometry("700x750")
        self._build_pb.start(10)

    def _append_build_log(self, text: str, tag: str = ""):
        self._build_log.config(state=tk.NORMAL)
        if tag:
            self._build_log.insert(tk.END, text, tag)
        else:
            self._build_log.insert(tk.END, text)
        self._build_log.see(tk.END)
        self._build_log.config(state=tk.DISABLED)


if __name__ == "__main__":
    app = InstallerApp()
    app.mainloop()

"""
Wizard de primer uso para Job Tracker.
Se muestra cuando la app detecta que aún no está configurada.
"""
import os
import sys
import shutil
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))

AI_PROVIDERS = {
    "Gemini Flash (Gratuito — Recomendado)": {
        "env_key": "GEMINI_API_KEY",
        "url": "https://aistudio.google.com/app/apikey",
        "help": "Obtén tu API key gratis en Google AI Studio. No requiere tarjeta.",
    },
    "Groq — Llama 3.3 70B (Gratuito)": {
        "env_key": "GROQ_API_KEY",
        "url": "https://console.groq.com/keys",
        "help": "Obtén tu API key gratis en Groq Console.",
    },
    "OpenRouter (Gratuito con límite)": {
        "env_key": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/keys",
        "help": "Crea cuenta gratuita en OpenRouter.",
    },
    "Claude / Anthropic (De pago)": {
        "env_key": "ANTHROPIC_API_KEY",
        "url": "https://console.anthropic.com/",
        "help": "Requiere cuenta con saldo en Anthropic.",
    },
}

TOTAL_STEPS = 4


def is_first_run() -> bool:
    """Retorna True si la app aún no tiene configuración básica completa."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return True

    content = env_path.read_text()
    has_key = any(
        f"{k}=" in content and len(content.split(f"{k}=", 1)[1].split("\n")[0].strip()) > 5
        for k in ["GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"]
    )
    if not has_key:
        return True

    try:
        import yaml
        with open(ROOT / "config.yaml", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        if cfg.get("profile", {}).get("name") in ("Tu Nombre", "", None):
            return True
    except Exception:
        return True

    return False


def run_wizard() -> bool:
    """
    Renderiza el wizard. Retorna True mientras el wizard está activo
    (para que app.py pueda llamar st.stop()).
    """
    if "wizard_step" not in st.session_state:
        st.session_state.wizard_step = 1

    step = st.session_state.wizard_step

    st.markdown(
        """
        <style>
        .wizard-header { font-size: 1.6rem; font-weight: 700; margin-bottom: 0.2rem; }
        .wizard-sub { color: #94a3b8; margin-bottom: 1.5rem; }
        .step-indicator { color: #6366f1; font-size: 0.9rem; font-weight: 600; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col_title, col_step = st.columns([4, 1])
    with col_title:
        st.markdown('<p class="wizard-header">💼 Configuración inicial de Job Tracker</p>', unsafe_allow_html=True)
    with col_step:
        st.markdown(
            f'<p class="step-indicator" style="text-align:right;margin-top:1rem">Paso {step} de {TOTAL_STEPS}</p>',
            unsafe_allow_html=True,
        )

    st.progress(step / TOTAL_STEPS)
    st.divider()

    if step == 1:
        _step_provider()
    elif step == 2:
        _step_profile()
    elif step == 3:
        _step_preferences()
    elif step == 4:
        _step_finish()

    return True


# ──────────────────────────────────────────────────────────────────────────────
# Paso 1 — Proveedor de IA
# ──────────────────────────────────────────────────────────────────────────────
def _step_provider():
    st.subheader("Proveedor de IA")
    st.caption("Job Tracker usa IA para analizar vacantes y generar cover letters.")

    provider = st.selectbox(
        "Elige un proveedor",
        list(AI_PROVIDERS.keys()),
        key="wiz_provider",
    )

    info = AI_PROVIDERS[provider]
    st.info(f"🔗 {info['help']}  →  [{info['url']}]({info['url']})")

    api_key = st.text_input(
        "API Key",
        type="password",
        key="wiz_api_key",
        help="Tu clave se guardará cifrada en disco.",
    )

    st.caption("🔒  La clave se almacena cifrada con AES-128 (Fernet).")

    st.divider()
    col_next, _ = st.columns([1, 3])
    with col_next:
        if st.button("Siguiente →", type="primary", disabled=not api_key.strip()):
            st.session_state.wiz_provider_saved = provider
            st.session_state.wiz_key_saved = api_key.strip()
            st.session_state.wizard_step = 2
            st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# Paso 2 — Perfil
# ──────────────────────────────────────────────────────────────────────────────
def _step_profile():
    st.subheader("Tu Perfil")
    st.caption("Tu nombre y email aparecerán en las cover letters generadas.")

    name = st.text_input("Nombre completo", key="wiz_name")
    email = st.text_input("Email", key="wiz_email")

    st.divider()
    st.markdown("**CV (PDF)** — opcional, también puedes subirlo desde la pestaña Config.")
    uploaded_cv = st.file_uploader("Sube tu CV", type=["pdf"], key="wiz_cv")

    col_back, col_next, _ = st.columns([1, 1, 3])
    with col_back:
        if st.button("← Atrás"):
            st.session_state.wizard_step = 1
            st.rerun()
    with col_next:
        if st.button("Siguiente →", type="primary", disabled=not (name.strip() and email.strip())):
            st.session_state.wiz_name_saved = name.strip()
            st.session_state.wiz_email_saved = email.strip()
            if uploaded_cv:
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                (DATA_DIR / "cv.pdf").write_bytes(uploaded_cv.read())
                st.session_state.wiz_cv_uploaded = True
            st.session_state.wizard_step = 3
            st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# Paso 3 — Preferencias de búsqueda
# ──────────────────────────────────────────────────────────────────────────────
def _step_preferences():
    st.subheader("Preferencias de búsqueda")
    st.caption("Define qué tipo de vacantes debe buscar Job Tracker automáticamente.")

    keywords_raw = st.text_input(
        "Roles / Keywords (separados por coma)",
        value="sysadmin, devops, linux administrator, cloud engineer",
        key="wiz_keywords",
        help='ej: "sysadmin, devops, cloud engineer"',
    )

    locations_raw = st.text_input(
        "Ubicaciones preferidas (separadas por coma)",
        value="remote, remoto",
        key="wiz_locations",
        help='ej: "remote, remoto, Ciudad de México"',
    )

    remote_only = st.checkbox("Solo vacantes remotas", value=True, key="wiz_remote")

    col_back, col_next, _ = st.columns([1, 1, 3])
    with col_back:
        if st.button("← Atrás"):
            st.session_state.wizard_step = 2
            st.rerun()
    with col_next:
        if st.button("Guardar y continuar →", type="primary"):
            st.session_state.wiz_keywords_saved = keywords_raw
            st.session_state.wiz_locations_saved = locations_raw
            st.session_state.wiz_remote_saved = remote_only
            st.session_state.wizard_step = 4
            st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# Paso 4 — Guardar y finalizar
# ──────────────────────────────────────────────────────────────────────────────
def _step_finish():
    st.subheader("Guardando configuración...")

    try:
        _save_all()
        st.success("✅  ¡Configuración guardada correctamente!")
        st.balloons()

        st.markdown("### Job Tracker está listo")
        st.markdown(
            "- Usa la pestaña **🔍 Scrape** para buscar vacantes ahora mismo.\n"
            "- El scheduler buscará vacantes automáticamente cada día.\n"
            "- Desde **⚙️ Config** puedes actualizar tu CV o cambiar keywords en cualquier momento."
        )

        if st.button("🚀  Ir a Job Tracker", type="primary"):
            st.session_state.wizard_done = True
            st.rerun()

    except Exception as exc:
        st.error(f"Error al guardar la configuración: {exc}")
        if st.button("← Reintentar"):
            st.session_state.wizard_step = 1
            st.rerun()


def _save_all():
    import yaml
    from cryptography.fernet import Fernet

    # Generar / leer clave de cifrado
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    key_path = DATA_DIR / "secret.key"
    if key_path.exists():
        key = key_path.read_bytes()
    else:
        key = Fernet.generate_key()
        key_path.write_bytes(key)

    # Cifrar y guardar .env
    api_key = st.session_state.get("wiz_key_saved", "")
    provider = st.session_state.get("wiz_provider_saved", list(AI_PROVIDERS.keys())[0])
    env_key = AI_PROVIDERS[provider]["env_key"]
    encrypted = "ENC:" + Fernet(key).encrypt(api_key.encode()).decode()

    env_path = ROOT / ".env"
    env_path.write_text(f"{env_key}={encrypted}\n")

    # Guardar config.yaml
    keywords = [k.strip() for k in st.session_state.get("wiz_keywords_saved", "").split(",") if k.strip()]
    locations = [l.strip() for l in st.session_state.get("wiz_locations_saved", "").split(",") if l.strip()]
    name = st.session_state.get("wiz_name_saved", "Tu Nombre")
    email = st.session_state.get("wiz_email_saved", "tu@email.com")
    remote = st.session_state.get("wiz_remote_saved", True)

    cfg = {
        "profile": {"name": name, "email": email, "phone": "", "cv_path": "data/cv.pdf"},
        "search": {
            "keywords": keywords or ["sysadmin", "devops"],
            "locations": locations or ["remote"],
            "remote_preference": remote,
            "exclude_keywords": ["junior", "intern", "practicante", "becario", "security clearance"],
            "exclude_titles": [],
            "exclude_locations": [],
        },
        "email": {"smtp_server": "smtp.gmail.com", "smtp_port": 587, "sender": email, "app_password": ""},
        "cover_letter": {"language": "auto", "tone": "professional", "max_length": 400},
    }

    with open(ROOT / "config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # Actualizar os.environ para que la sesión actual lo use sin reiniciar
    os.environ[env_key] = api_key

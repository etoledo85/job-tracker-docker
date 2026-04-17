import yaml
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def _load_env():
    """Carga .env si existe (sin dependencia de python-dotenv)."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def load_config() -> dict:
    _load_env()
    config_path = BASE_DIR / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Inyectar credenciales desde variables de entorno
    if not cfg["email"].get("app_password"):
        cfg["email"]["app_password"] = os.environ.get("GMAIL_APP_PASSWORD", "")
    if "anthropic" not in cfg:
        cfg["anthropic"] = {}
    if not cfg["anthropic"].get("api_key"):
        cfg["anthropic"]["api_key"] = os.environ.get("ANTHROPIC_API_KEY", "")
    # Gemini — se lee directo desde os.environ en ai_provider.py, pero lo
    # exponemos aquí para que load_config() sirva como punto único de diagnóstico
    if not os.environ.get("GEMINI_API_KEY"):
        gemini_key = cfg.get("gemini", {}).get("api_key", "")
        if gemini_key:
            os.environ["GEMINI_API_KEY"] = gemini_key

    return cfg

def get_cv_text() -> str:
    """Extract text from the user's CV PDF."""
    cfg = load_config()
    data_dir = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
    cv_filename = Path(cfg["profile"]["cv_path"]).name
    cv_path = data_dir / cv_filename

    if not cv_path.exists():
        return ""

    try:
        from pypdf import PdfReader
        reader = PdfReader(str(cv_path))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"[warning] No se pudo leer el CV: {e}")
        return ""

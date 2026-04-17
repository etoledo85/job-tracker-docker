"""
Interfaz unificada de IA. Prioridad: Gemini (gratis) → Claude (API key).
"""
import os


def complete_json(system: str, user: str, max_tokens: int = 4096) -> str:
    """Igual que complete() pero fuerza salida JSON válida."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if gemini_key:
        return _gemini(gemini_key, system, user, max_tokens, json_mode=True)
    if groq_key:
        return _groq(groq_key, system, user, max_tokens, json_mode=True)
    if openrouter_key:
        return _openrouter(openrouter_key, system, user, max_tokens, json_mode=True)
    if anthropic_key:
        return _claude(anthropic_key, system, user, max_tokens)

    raise _no_key_error()


def complete(system: str, user: str, max_tokens: int = 1500) -> str:
    """
    Envía un prompt al proveedor de IA disponible y retorna el texto generado.
    Prioridad: GEMINI_API_KEY → GROQ_API_KEY → OPENROUTER_API_KEY → ANTHROPIC_API_KEY
    """
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if gemini_key:
        return _gemini(gemini_key, system, user, max_tokens)
    if groq_key:
        return _groq(groq_key, system, user, max_tokens)
    if openrouter_key:
        return _openrouter(openrouter_key, system, user, max_tokens)
    if anthropic_key:
        return _claude(anthropic_key, system, user, max_tokens)

    raise _no_key_error()


def _no_key_error():
    return RuntimeError(
        "No hay API key configurada. Agrega una de estas en tu .env:\n"
        "  OPENROUTER_API_KEY — gratis: https://openrouter.ai\n"
        "  GROQ_API_KEY       — gratis: https://console.groq.com/keys\n"
        "  GEMINI_API_KEY     — gratis: https://aistudio.google.com/app/apikey\n"
        "  ANTHROPIC_API_KEY"
    )


def _gemini(api_key: str, system: str, user: str, max_tokens: int,
            json_mode: bool = False) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("google-genai no está instalado. Ejecuta: pip install google-genai")

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=max_tokens,
        **({"response_mime_type": "application/json"} if json_mode else {}),
    )
    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=user,
        config=config,
    )
    return response.text.strip()


def _groq(api_key: str, system: str, user: str, max_tokens: int,
          json_mode: bool = False) -> str:
    from groq import Groq
    client = Groq(api_key=api_key)
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        **kwargs,
    )
    return response.choices[0].message.content.strip()


_OPENROUTER_FREE_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "google/gemma-4-31b-it:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]


def _openrouter(api_key: str, system: str, user: str, max_tokens: int,
                json_mode: bool = False) -> str:
    from openai import OpenAI, RateLimitError
    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    last_err = None
    for model in _OPENROUTER_FREE_MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                **kwargs,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"Todos los modelos gratuitos de OpenRouter fallaron: {last_err}")


def _claude(api_key: str, system: str, user: str, max_tokens: int) -> str:
    import anthropic
    from src.config import load_config
    cfg = load_config()
    model = cfg.get("anthropic", {}).get("model", "claude-sonnet-4-6")
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text.strip()

"""
Genera cover letters personalizadas usando Claude.
"""
import re
from pathlib import Path
from datetime import datetime
from src.config import load_config, get_cv_text
from src.ai_provider import complete as ai_complete
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY

import os
BASE_DIR = Path(__file__).parent.parent
_data_dir = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
OUTPUT_DIR = _data_dir / "cover_letters"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def detect_language(text: str) -> str:
    """Detecta si el texto es principalmente español o inglés."""
    spanish_markers = ["empresa", "experiencia", "requisitos", "responsabilidades",
                       "conocimientos", "años", "puesto", "trabajo", "equipo"]
    english_markers = ["experience", "requirements", "responsibilities",
                       "skills", "team", "company", "position", "job"]
    text_lower = text.lower()
    es_score = sum(1 for m in spanish_markers if m in text_lower)
    en_score = sum(1 for m in english_markers if m in text_lower)
    return "es" if es_score >= en_score else "en"


def generate_cover_letter(job_id: int, job_title: str, company: str,
                           description: str, url: str) -> str:
    """Genera y guarda una cover letter. Retorna el path del archivo."""
    cfg = load_config()
    cv_text = get_cv_text()
    profile = cfg["profile"]
    cl_cfg = cfg.get("cover_letter", {})

    # Detectar idioma
    lang_pref = cl_cfg.get("language", "auto")
    if lang_pref == "auto":
        lang = detect_language(description or job_title)
    else:
        lang = lang_pref

    max_words = cl_cfg.get("max_length", 400)

    if lang == "es":
        system_prompt = f"""Eres un experto en recursos humanos y redacción profesional.
Tu tarea es escribir una cover letter (carta de presentación) altamente personalizada y convincente.

PERFIL DEL CANDIDATO:
{cv_text if cv_text else f"Sysadmin/Administrador de Servidores con 14 años de experiencia. Nombre: {profile['name']}. Email: {profile['email']}"}

INSTRUCCIONES:
- Escribe la carta en español, tono profesional pero no robótico
- Máximo {max_words} palabras
- Conecta directamente las habilidades del candidato con los requisitos del puesto
- NO uses frases genéricas como "me apasiona" o "soy muy trabajador"
- Incluye 1-2 logros o datos concretos del CV si están disponibles
- Termina con un llamado a la acción claro
- NO incluyas fecha ni dirección postal, solo el cuerpo de la carta"""
    else:
        system_prompt = f"""You are an expert HR professional and professional writer.
Your task is to write a highly personalized and compelling cover letter.

CANDIDATE PROFILE:
{cv_text if cv_text else f"Sysadmin/Server Administrator with 14 years of experience. Name: {profile['name']}. Email: {profile['email']}"}

INSTRUCTIONS:
- Write in English, professional but human tone
- Maximum {max_words} words
- Directly connect the candidate's skills to the job requirements
- Avoid generic phrases like "I am passionate about" or "I am a hard worker"
- Include 1-2 concrete achievements or metrics from the CV if available
- End with a clear call to action
- Do NOT include date or postal address, just the letter body"""

    user_message = f"""Puesto: {job_title}
Empresa: {company}
URL: {url}

Descripción de la vacante:
{description[:2500] if description else "No disponible"}

Escribe la cover letter ahora:"""

    try:
        letter_text = ai_complete(system_prompt, user_message, max_tokens=1024)
    except Exception as e:
        raise RuntimeError(f"Error generando cover letter: {e}")

    # Guardar como PDF
    safe_company = re.sub(r"[^\w\s-]", "", company).strip().replace(" ", "_")[:30]
    safe_title = re.sub(r"[^\w\s-]", "", job_title).strip().replace(" ", "_")[:30]
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{date_str}_{job_id}_{safe_company}_{safe_title}.pdf"
    output_path = OUTPUT_DIR / filename

    _save_as_pdf(output_path, job_title, company, url, letter_text)

    return str(output_path)


def _save_as_pdf(output_path: Path, job_title: str, company: str, url: str, letter_text: str):
    """Genera un PDF con formato profesional para la cover letter."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        leftMargin=1.1 * inch,
        rightMargin=1.1 * inch,
        topMargin=1.0 * inch,
        bottomMargin=1.0 * inch,
    )

    styles = getSampleStyleSheet()

    style_meta = ParagraphStyle(
        "Meta",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#666666"),
        leading=12,
        alignment=TA_LEFT,
    )
    style_body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=11,
        leading=18,
        alignment=TA_JUSTIFY,
        spaceAfter=10,
    )

    story = []

    # Metadata de la vacante (pequeña, al inicio)
    story.append(Paragraph(f"<b>Posición:</b> {job_title}", style_meta))
    story.append(Paragraph(f"<b>Empresa:</b> {company}", style_meta))
    story.append(Paragraph(f"<b>URL:</b> {url}", style_meta))
    story.append(Spacer(1, 0.35 * inch))

    # Cuerpo de la carta — párrafo a párrafo
    for para in letter_text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        # Convertir **negrita** a tags de ReportLab
        para = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", para)
        para = para.replace("\n", " ")
        story.append(Paragraph(para, style_body))

    doc.build(story)

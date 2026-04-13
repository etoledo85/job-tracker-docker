"""
Analiza el fit entre el CV del candidato y una vacante específica.
Genera recomendaciones de tailoring para mejorar el match ATS.
Genera CVs personalizados por vacante en PDF.
"""
import os
import re
import json
from pathlib import Path
from src.config import load_config, get_cv_text


def analyze_fit(job_title: str, company: str, description: str) -> dict:
    """
    Compara el CV del candidato contra la descripción de la vacante.
    Retorna un dict con: match_score, matched_keywords, missing_keywords,
    reword_suggestions, cover_letter_angle.
    """
    cfg = load_config()
    cv_text = get_cv_text()

    if not cv_text:
        raise RuntimeError("No se pudo leer el CV. Verifica que data/cv.pdf exista.")

    if not description:
        raise RuntimeError("Esta vacante no tiene descripción. Ejecuta el scraper con fetch de descripciones.")

    system_prompt = """You are an expert ATS (Applicant Tracking System) analyst and resume coach.
Your job is to compare a candidate's CV against a job description and return a structured JSON analysis.

IMPORTANT: Return ONLY valid JSON, no markdown, no preamble. The JSON must follow this exact schema:
{
  "match_score": <integer 0-100>,
  "matched_keywords": ["keyword1", "keyword2", ...],
  "missing_keywords": ["keyword1", "keyword2", ...],
  "reword_suggestions": [
    {"cv_phrase": "original phrase in CV", "suggested": "reworded to match JD language"},
    ...
  ],
  "critical_gaps": ["gap1", "gap2"],
  "cover_letter_angle": "One sentence describing the strongest angle to emphasize in the cover letter",
  "overall_verdict": "brief 2-sentence assessment"
}

Rules:
- match_score: realistic ATS keyword match estimate (0=no match, 100=perfect)
- matched_keywords: exact skills/technologies/certs present in BOTH the JD and CV
- missing_keywords: important skills/technologies in JD that are NOT in the CV
- reword_suggestions: specific phrases from the CV that could be reworded to use JD terminology
- critical_gaps: 1-3 must-have requirements the candidate clearly lacks
- Be honest and specific, not generic"""

    user_message = f"""JOB TITLE: {job_title}
COMPANY: {company}

JOB DESCRIPTION:
{description[:3000]}

CANDIDATE CV:
{cv_text[:3000]}

Analyze the fit and return the JSON:"""

    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            model = cfg.get("anthropic", {}).get("model", "claude-sonnet-4-6")
            message = client.messages.create(
                model=model,
                max_tokens=1500,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )
            raw = message.content[0].text.strip()
        else:
            import subprocess
            full_prompt = f"{system_prompt}\n\n{user_message}"
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions"],
                input=full_prompt,
                capture_output=True, text=True, timeout=120,
                env={**os.environ}
            )
            if result.returncode != 0:
                raise RuntimeError(f"claude CLI error: {result.stderr[:300]}")
            raw = result.stdout.strip()
            if not raw:
                raise RuntimeError("claude CLI no devolvió texto")

        # Limpiar posible markdown fence
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        return json.loads(raw)

    except json.JSONDecodeError as e:
        raise RuntimeError(f"Respuesta de Claude no es JSON válido: {e}\nRaw: {raw[:300]}")
    except Exception as e:
        raise RuntimeError(f"Error en análisis de fit: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# CV PERSONALIZADO
# ─────────────────────────────────────────────────────────────────────────────

CV_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "tailored_cvs"
CV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_tailored_cv(job_id: int, job_title: str, company: str,
                          description: str, url: str,
                          tailor_result: dict) -> str:
    """
    Genera un CV personalizado para la vacante aplicando los rewording
    suggestions del análisis ATS. Retorna el path del PDF generado.
    """
    cfg = load_config()
    cv_text = get_cv_text()
    if not cv_text:
        raise RuntimeError("No se pudo leer el CV. Verifica que data/cv.pdf exista.")

    reword = tailor_result.get("reword_suggestions", [])
    missing = tailor_result.get("missing_keywords", [])
    angle = tailor_result.get("cover_letter_angle", "")
    score = tailor_result.get("match_score", 0)

    reword_block = "\n".join(
        f'- REEMPLAZA: "{s["cv_phrase"]}"\n  CON: "{s["suggested"]}"'
        for s in reword
    ) if reword else "Ninguna sugerencia."

    missing_block = ", ".join(missing) if missing else "Ninguna."

    system_prompt = """You are a professional resume writer and ATS optimization expert.
Your task is to rewrite a candidate's CV for a specific job application.

RULES:
- Keep ALL facts, dates, companies, titles, and metrics exactly as in the original — do NOT invent experience
- Apply the rewording suggestions to match the job description's language
- Weave in missing keywords ONLY where they are truthfully supported by the candidate's experience
- Preserve the original CV structure and sections
- Output the full rewritten CV text (no PDF formatting, plain text with clear sections)
- Use the same section headers as the original CV
- Maintain professional English throughout
- Do NOT add skills or technologies the candidate does not have"""

    user_message = f"""JOB: {job_title} @ {company}
ATS MATCH SCORE (before tailoring): {score}/100
STRATEGIC ANGLE: {angle}

REWORDING SUGGESTIONS TO APPLY:
{reword_block}

MISSING KEYWORDS TO WEAVE IN (only where truthfully applicable):
{missing_block}

ORIGINAL CV:
{cv_text}

Write the full tailored CV now:"""

    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            model = cfg.get("anthropic", {}).get("model", "claude-sonnet-4-6")
            message = client.messages.create(
                model=model,
                max_tokens=3000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )
            cv_tailored = message.content[0].text.strip()
        else:
            import subprocess
            full_prompt = f"{system_prompt}\n\n{user_message}"
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions"],
                input=full_prompt,
                capture_output=True, text=True, timeout=180,
                env={**os.environ}
            )
            if result.returncode != 0:
                raise RuntimeError(f"claude CLI error: {result.stderr[:300]}")
            cv_tailored = result.stdout.strip()
            if not cv_tailored:
                raise RuntimeError("claude CLI no devolvió texto")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error generando CV tailored: {e}")

    # Guardar PDF
    from datetime import datetime
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    safe_company = re.sub(r"[^\w\s-]", "", company).strip().replace(" ", "_")[:25]
    safe_title   = re.sub(r"[^\w\s-]", "", job_title).strip().replace(" ", "_")[:25]
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{date_str}_{job_id}_CV_{safe_company}_{safe_title}.pdf"
    output_path = CV_OUTPUT_DIR / filename

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    s_name    = ParagraphStyle("Name",    fontSize=16, fontName="Helvetica-Bold",
                               leading=20, alignment=TA_CENTER, spaceAfter=2)
    s_contact = ParagraphStyle("Contact", fontSize=8,  fontName="Helvetica",
                               leading=12, alignment=TA_CENTER, spaceAfter=6,
                               textColor=colors.HexColor("#444444"))
    s_section = ParagraphStyle("Section", fontSize=10, fontName="Helvetica-Bold",
                               leading=14, spaceBefore=10, spaceAfter=3,
                               textColor=colors.HexColor("#1a1a1a"))
    s_body    = ParagraphStyle("Body",    fontSize=9,  fontName="Helvetica",
                               leading=13, spaceAfter=4)
    s_bullet  = ParagraphStyle("Bullet",  fontSize=9,  fontName="Helvetica",
                               leading=13, spaceAfter=3, leftIndent=12,
                               bulletIndent=0)
    s_note    = ParagraphStyle("Note",    fontSize=7,  fontName="Helvetica-Oblique",
                               textColor=colors.HexColor("#888888"),
                               leading=10, spaceAfter=6, alignment=TA_CENTER)

    story = []

    # Watermark note
    story.append(Paragraph(
        f"CV tailored for: {job_title} @ {company} | {date_str}",
        s_note
    ))

    # Parsear y renderizar el CV tailored
    lines = cv_tailored.split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 0.05 * inch))
            continue

        # Detectar nombre (primera línea no vacía con solo mayúsculas o nombre completo)
        if re.match(r'^[A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]{5,40}$', stripped) and len(stripped.split()) <= 4:
            story.append(Paragraph(stripped, s_name))
        # Sección header (todo mayúsculas o con patrón de sección)
        elif (stripped.isupper() and len(stripped) > 3) or re.match(
            r'^(PROFESSIONAL SUMMARY|TECHNICAL SKILLS|PROFESSIONAL EXPERIENCE|'
            r'KEY PROJECTS|EDUCATION|CERTIFICATIONS|EARLIER EXPERIENCE|'
            r'RESUMEN|EXPERIENCIA|HABILIDADES|EDUCACIÓN)', stripped, re.I
        ):
            story.append(HRFlowable(width="100%", thickness=0.5,
                                    color=colors.HexColor("#cccccc"), spaceAfter=2))
            story.append(Paragraph(stripped, s_section))
        # Bullet points (▸ o - o •)
        elif stripped.startswith(("▸", "•", "-", "–")):
            text = stripped.lstrip("▸•-– ").strip()
            text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
            story.append(Paragraph(f"▸ {text}", s_bullet))
        # Contact line o subtitle (contiene @ o · o |)
        elif any(c in stripped for c in ["@", "·", " | ", "linkedin", "+52", "C1"]):
            story.append(Paragraph(stripped, s_contact))
        else:
            text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", stripped)
            story.append(Paragraph(text, s_body))

    doc.build(story)
    return str(output_path)

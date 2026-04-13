"""
Envío de cover letters por Gmail SMTP.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from src.config import load_config


def _extract_pdf_text(path: Path) -> str:
    """Extrae el texto de un PDF de cover letter."""
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return "\n\n".join(page.extract_text() for page in reader.pages).strip()

BASE_DIR = Path(__file__).parent.parent


def send_application(to_email: str, job_title: str, company: str,
                     cover_letter_path: str, subject: str = None) -> bool:
    """
    Envía la cover letter por email.
    Retorna True si fue exitoso.
    """
    cfg = load_config()
    email_cfg = cfg["email"]
    profile = cfg["profile"]

    sender = email_cfg["sender"]
    app_password = email_cfg.get("app_password", "")

    if not app_password:
        raise ValueError(
            "No hay App Password configurado en config.yaml.\n"
            "Ve a myaccount.google.com/security → Contraseñas de aplicaciones"
        )

    # Leer cover letter
    cl_path = Path(cover_letter_path)
    if not cl_path.exists():
        raise FileNotFoundError(f"Cover letter no encontrada: {cover_letter_path}")

    letter_body = _extract_pdf_text(cl_path)

    # Asunto del email
    if not subject:
        subject = f"Aplicación – {job_title} | {profile['name']}"

    # Construir email (mixed para admitir múltiples adjuntos)
    msg = MIMEMultipart("mixed")
    msg["From"] = f"{profile['name']} <{sender}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    # Cuerpo en texto plano
    msg.attach(MIMEText(letter_body, "plain", "utf-8"))

    # Adjuntar cover letter como PDF
    with open(cl_path, "rb") as f:
        cl_attachment = MIMEBase("application", "pdf")
        cl_attachment.set_payload(f.read())
    encoders.encode_base64(cl_attachment)
    cl_attachment.add_header(
        "Content-Disposition",
        f'attachment; filename="CoverLetter_{profile["name"].replace(" ", "_")}.pdf"'
    )
    msg.attach(cl_attachment)

    # Adjuntar CV si existe
    cv_path = BASE_DIR / cfg["profile"]["cv_path"]
    if cv_path.exists():
        with open(cv_path, "rb") as f:
            attachment = MIMEBase("application", "pdf")
            attachment.set_payload(f.read())
        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition",
            f'attachment; filename="{profile["name"].replace(" ", "_")}_CV.pdf"'
        )
        msg.attach(attachment)

    # Enviar
    with smtplib.SMTP(email_cfg["smtp_server"], email_cfg["smtp_port"]) as server:
        server.ehlo()
        server.starttls()
        server.login(sender, app_password)
        server.sendmail(sender, to_email, msg.as_string())

    return True


def send_self_copy(job_title: str, company: str, cover_letter_path: str,
                   target_email: str = None) -> bool:
    """
    Envía una copia de la cover letter a tu propio correo (para registro).
    """
    cfg = load_config()
    sender = cfg["email"]["sender"]
    subject = f"[Job Tracker] Cover Letter enviada: {job_title} @ {company}"
    if target_email:
        subject += f" → {target_email}"

    return send_application(
        to_email=sender,
        job_title=job_title,
        company=company,
        cover_letter_path=cover_letter_path,
        subject=subject,
    )

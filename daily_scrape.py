#!/usr/bin/env python3
"""
Scrape diario automático con email resumen.
Ejecutado por cron cada mañana.
"""
import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from src.database import init_db, upsert_job, get_jobs
from src.config import load_config
from src.email_sender import send_self_copy

SOURCES = [
    "remotive", "wwr", "linkedin", "computrabajo", "occ",
    "remoteok", "himalayas", "getonboard", "jobicy", "glassdoor",
]


def run_scrape(cfg):
    keywords = cfg["search"]["keywords"]
    locations = cfg["search"]["locations"]
    exclude = cfg["search"].get("exclude_keywords", [])
    exclude_locations = cfg["search"].get("exclude_locations", [])
    exclude_titles = [t.lower() for t in cfg["search"].get("exclude_titles", [])]
    exclude_us_cities = [c.lower() for c in cfg["search"].get("exclude_us_cities", [])]

    from src.scrapers.remotive import RemotiveScraper
    from src.scrapers.weworkremotely import WeWorkRemotelyScraper
    from src.scrapers.linkedin import LinkedInScraper
    from src.scrapers.computrabajo import ComputrabajoScraper
    from src.scrapers.occ import OCCScraper
    from src.scrapers.remoteok import RemoteOKScraper
    from src.scrapers.himalayas import HimalayasScraper
    from src.scrapers.getonboard import GetOnBoardScraper
    from src.scrapers.jobicy import JobicyScraper
    from src.scrapers.glassdoor import GlassdoorScraper

    scrapers_map = {
        "remotive":    RemotiveScraper,
        "wwr":         WeWorkRemotelyScraper,
        "linkedin":    LinkedInScraper,
        "computrabajo": ComputrabajoScraper,
        "occ":         OCCScraper,
        "remoteok":    RemoteOKScraper,
        "himalayas":   HimalayasScraper,
        "getonboard":  GetOnBoardScraper,
        "jobicy":      JobicyScraper,
        "glassdoor":   GlassdoorScraper,
    }

    new_jobs = []
    stats = {}

    for name in SOURCES:
        ScraperClass = scrapers_map.get(name)
        if not ScraperClass:
            continue

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Scraping {name}...")
        # Glassdoor es lento (Playwright por keyword); limitar a keywords principales
        kw = ["sysadmin", "systems administrator", "linux administrator", "infrastructure engineer"] if name == "glassdoor" else keywords
        scraper = ScraperClass(keywords=kw, locations=locations)

        try:
            jobs = scraper.scrape()
        except Exception as e:
            print(f"  ERROR {name}: {e}")
            stats[name] = {"found": 0, "new": 0, "error": str(e)}
            continue

        new_count = 0
        for job in jobs:
            title_lower = job.title.lower()
            combined = f"{job.title} {job.description}".lower()
            loc_lower = (job.location or "").lower()

            if not any(kw.lower() in title_lower for kw in keywords):
                continue
            if any(title_lower == t or title_lower.startswith(t) for t in exclude_titles):
                continue
            if any(kw.lower() in combined for kw in exclude):
                continue
            if not job.remote and exclude_locations:
                if any(el.lower() in loc_lower for el in exclude_locations):
                    continue
            if "only" in loc_lower and not any(
                ok in loc_lower for ok in ["mexico only", "méxico only", "latam only",
                                           "worldwide", "remote only"]
            ):
                continue
            if exclude_us_cities and any(city in loc_lower for city in exclude_us_cities):
                continue

            is_new, job_id = upsert_job(job)
            if is_new:
                new_count += 1
                new_jobs.append({
                    "id": job_id,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "source": name,
                    "remote": job.remote,
                    "salary": job.salary or "",
                })

        stats[name] = {"found": len(jobs), "new": new_count}
        print(f"  → {len(jobs)} encontradas, {new_count} nuevas")

    return new_jobs, stats


def build_email(new_jobs, stats, date_str):
    total_new = len(new_jobs)

    if total_new == 0:
        subject = f"Job Tracker {date_str} — Sin vacantes nuevas"
        body = (
            f"<h2>Job Tracker — {date_str}</h2>"
            f"<p>El scrape diario no encontró vacantes nuevas que pasen los filtros.</p>"
            f"{_stats_table(stats)}"
        )
        return subject, body

    subject = f"Job Tracker {date_str} — {total_new} vacante{'s' if total_new > 1 else ''} nueva{'s' if total_new > 1 else ''}"

    rows = ""
    for j in new_jobs:
        remote_tag = "🌐 Remote" if j["remote"] else j["location"]
        salary = f" | {j['salary']}" if j["salary"] else ""
        rows += (
            f"<tr>"
            f"<td style='padding:6px 10px;'><b>#{j['id']}</b></td>"
            f"<td style='padding:6px 10px;'>{j['title']}</td>"
            f"<td style='padding:6px 10px;'>{j['company']}</td>"
            f"<td style='padding:6px 10px;'>{remote_tag}{salary}</td>"
            f"<td style='padding:6px 10px;color:#888;'>{j['source']}</td>"
            f"</tr>"
        )

    body = f"""
<h2 style='color:#0a84ff;'>Job Tracker — {date_str}</h2>
<p>Se encontraron <b>{total_new} vacantes nuevas</b> que pasaron todos los filtros:</p>

<table border='0' cellspacing='0' cellpadding='0'
       style='border-collapse:collapse;width:100%;font-family:monospace;font-size:13px;'>
  <thead>
    <tr style='background:#f0f0f0;'>
      <th style='padding:6px 10px;text-align:left;'>ID</th>
      <th style='padding:6px 10px;text-align:left;'>Título</th>
      <th style='padding:6px 10px;text-align:left;'>Empresa</th>
      <th style='padding:6px 10px;text-align:left;'>Ubicación</th>
      <th style='padding:6px 10px;text-align:left;'>Fuente</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>

<p style='margin-top:20px;'>Para analizar una vacante:<br>
<code>python main.py tailor &lt;id&gt;</code><br>
<code>python main.py show &lt;id&gt;</code></p>

{_stats_table(stats)}
"""
    return subject, body


def _stats_table(stats):
    rows = ""
    for name, s in stats.items():
        if "error" in s:
            rows += f"<tr><td style='padding:3px 8px;'>{name}</td><td style='color:red;padding:3px 8px;'>ERROR: {s['error'][:60]}</td></tr>"
        else:
            rows += f"<tr><td style='padding:3px 8px;'>{name}</td><td style='padding:3px 8px;'>{s['found']} encontradas / {s['new']} nuevas</td></tr>"
    return f"""
<details style='margin-top:20px;'>
  <summary style='color:#888;cursor:pointer;'>Detalle por fuente</summary>
  <table style='font-size:12px;color:#555;margin-top:8px;'>
    <tbody>{rows}</tbody>
  </table>
</details>
"""


def send_summary(cfg, subject, body):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    email_cfg = cfg["email"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_cfg["sender"]
    msg["To"] = cfg["profile"]["email"]
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP(email_cfg["smtp_server"], email_cfg["smtp_port"]) as server:
        server.starttls()
        server.login(email_cfg["sender"], email_cfg["app_password"])
        server.send_message(msg)


if __name__ == "__main__":
    init_db()
    cfg = load_config()
    date_str = datetime.now().strftime("%Y-%m-%d")

    print(f"=== Job Tracker Daily Scrape — {date_str} ===")
    new_jobs, stats = run_scrape(cfg)

    total = len(new_jobs)
    print(f"\nTotal nuevas: {total}")

    subject, body = build_email(new_jobs, stats, date_str)

    try:
        send_summary(cfg, subject, body)
        print(f"Email enviado: {subject}")
    except Exception as e:
        print(f"ERROR enviando email: {e}")

    sys.exit(0)

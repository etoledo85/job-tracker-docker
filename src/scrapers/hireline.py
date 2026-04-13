"""
Hireline.io – bolsa tech enfocada en México y LATAM.
SSR, scraping con requests + BeautifulSoup.
Selectores: a.hl-vacancy-card con clases internas bien definidas.
"""
import re
import time
import random
from typing import List
from src.scrapers.base import BaseScraper
from src.database import Job

BASE_URL = "https://hireline.io"

SEARCH_TERMS = [
    "sysadmin",
    "linux",
    "infraestructura",
    "devops",
    "administrador sistemas",
]


class HirelineScraper(BaseScraper):
    name = "hireline"

    def scrape(self) -> List[Job]:
        from bs4 import BeautifulSoup

        jobs = []
        seen = set()

        for term in SEARCH_TERMS:
            time.sleep(random.uniform(1.5, 3.0))
            try:
                resp = self._get(
                    f"{BASE_URL}/mx/empleos",
                    params={"q": term, "remote": "1"},
                )
                resp.raise_for_status()
            except Exception as e:
                print(f"  [hireline] Error en '{term}': {e}")
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # Cada tarjeta es un <a class="hl-vacancy-card ...">
            cards = soup.select("a.hl-vacancy-card")

            for card in cards:
                try:
                    job_url = card.get("href", "")
                    if not job_url:
                        continue
                    if job_url.startswith("/"):
                        job_url = f"{BASE_URL}{job_url}"
                    job_url = job_url.split("?")[0]
                    if job_url in seen:
                        continue

                    # Título y empresa vienen juntos en .vacancy-title: "Job Title en Company"
                    title_el = card.select_one(".vacancy-title")
                    raw_title = title_el.get_text(strip=True) if title_el else ""

                    # Split "Título en Empresa" (la palabra "en" separa)
                    title = raw_title
                    company = "Unknown"
                    match = re.search(r'^(.+?)\s+en\s+(.+)$', raw_title, re.I)
                    if match:
                        title = match.group(1).strip()
                        company = match.group(2).strip()

                    if not title:
                        continue

                    # Ubicación
                    loc_el = card.select_one(".vacancy-location")
                    location_raw = loc_el.get_text(strip=True) if loc_el else ""
                    if re.search(r'remoto|remote|home\s*office', location_raw, re.I):
                        location = "Remote"
                    elif location_raw:
                        location = location_raw
                    else:
                        location = "México"

                    # Salario
                    salary_el = card.select_one(".vacancy-subtitle")
                    salary = salary_el.get_text(strip=True) if salary_el else ""
                    if salary.lower() == "sueldo oculto":
                        salary = ""

                    combined = f"{title} {company}".lower()
                    if not any(kw.lower() in combined for kw in self.keywords):
                        continue

                    seen.add(job_url)
                    jobs.append(Job(
                        title=title,
                        company=company,
                        location=location,
                        url=job_url,
                        source="hireline",
                        description="",
                        salary=salary,
                        date_posted="",
                        remote="remote" in location.lower(),
                    ))
                except Exception:
                    continue

        return jobs

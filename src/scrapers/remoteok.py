"""
RemoteOK – bolsa de trabajos remotos globales.
Extrae datos del JSON-LD embebido en cada fila.
"""
import json
import time
import random
from typing import List
from src.scrapers.base import BaseScraper
from src.database import Job

BASE_URL = "https://remoteok.com"

SEARCH_TAGS = [
    "devops+sysadmin",
    "linux+sysadmin",
    "linux+infrastructure",
    "vmware+sysadmin",
    "cloud+infrastructure",
]


class RemoteOKScraper(BaseScraper):
    name = "remoteok"

    def scrape(self) -> List[Job]:
        from playwright.sync_api import sync_playwright
        from bs4 import BeautifulSoup

        jobs = []
        seen = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )

            for tag in SEARCH_TAGS:
                time.sleep(random.uniform(3, 6))
                url = f"{BASE_URL}/remote-{tag}-jobs"
                page = ctx.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(3000)
                    html = page.content()
                except Exception as e:
                    print(f"  [remoteok] Error en '{tag}': {e}")
                    page.close()
                    continue
                page.close()

                soup = BeautifulSoup(html, "lxml")
                rows = soup.select("tr.job")

                for row in rows:
                    try:
                        # Extraer datos del JSON-LD
                        script = row.select_one('script[type="application/ld+json"]')
                        if not script:
                            continue

                        try:
                            data = json.loads(script.get_text())
                        except json.JSONDecodeError:
                            continue
                        title = data.get("title", "").strip()
                        company = data.get("hiringOrganization", {}).get("name", "Unknown").strip()
                        date_posted = data.get("datePosted", "")[:10]
                        desc = data.get("description", "")

                        # URL desde data-slug
                        slug = row.get("data-slug", "")
                        job_id = row.get("data-id", "")
                        job_url = f"{BASE_URL}/{slug}" if slug else f"{BASE_URL}/l/{job_id}"

                        if not job_url or job_url in seen:
                            continue

                        # Location
                        loc_el = row.select_one("[class*='location']")
                        location = loc_el.get_text(strip=True) if loc_el else "Remote"
                        location = location.replace("🌏", "").replace("🌎", "").strip() or "Worldwide"

                        # Salary
                        salary_el = row.select_one("[class*='salary']")
                        salary = salary_el.get_text(strip=True) if salary_el else ""

                        if not title:
                            continue

                        # Filtrar por keywords del config y antigüedad
                        combined = f"{title} {desc}".lower()
                        if not any(kw.lower() in combined for kw in self.keywords):
                            continue
                        if not self._is_recent(date_posted):
                            continue

                        seen.add(job_url)
                        jobs.append(Job(
                            title=title,
                            company=company,
                            location=location,
                            url=job_url,
                            source="remoteok",
                            description=str(desc)[:3000],
                            salary=salary,
                            date_posted=date_posted,
                            remote=True,
                        ))
                    except Exception:
                        continue

            browser.close()

        return jobs

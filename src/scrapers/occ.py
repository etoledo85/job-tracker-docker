"""
OCC Mundial – bolsa de trabajo mexicana, filtro home office/remoto.
Usa Playwright para renderizar el contenido dinámico.
"""
import time
import random
from typing import List
from src.scrapers.base import BaseScraper
from src.database import Job

BASE_URL = "https://www.occ.com.mx"


class OCCScraper(BaseScraper):
    name = "occ"

    def scrape(self) -> List[Job]:
        from playwright.sync_api import sync_playwright

        jobs = []
        seen = set()
        # Genera slugs únicos desde las keywords del config
        slugs = list(dict.fromkeys(self._slugify(kw) for kw in self.keywords))

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="es-MX",
            )

            for keyword in slugs:
                time.sleep(random.uniform(2, 4))
                # URL con filtro home office/remoto
                url = f"{BASE_URL}/empleos/de-{keyword}/tipo-home-office-remoto/"

                page = ctx.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(4000)
                except Exception as e:
                    print(f"  [occ] Error en '{keyword}': {e}")
                    page.close()
                    continue

                cards = page.query_selector_all("[data-id]")

                for card in cards:
                    try:
                        job_id = card.get_attribute("data-id")
                        if not job_id:
                            continue

                        url_job = f"{BASE_URL}/empleo/oferta/{job_id}/"
                        if url_job in seen:
                            continue

                        title_el = card.query_selector("h2")
                        company_el = card.query_selector("[class*='line-clamp-title']")
                        loc_el = card.query_selector("p.text-grey-900.m-0")
                        salary_el = card.query_selector("[class*='font-light'][class*='mb']")

                        title = title_el.inner_text().strip() if title_el else "Unknown"
                        company = company_el.inner_text().strip() if company_el else "Unknown"
                        location = loc_el.inner_text().strip() if loc_el else "México"
                        salary = salary_el.inner_text().strip() if salary_el else ""

                        if not title or title == "Unknown":
                            continue

                        # Validar keywords del config
                        combined = f"{title} {company}".lower()
                        if not any(kw.lower() in combined for kw in self.keywords):
                            continue

                        seen.add(url_job)
                        jobs.append(Job(
                            title=title,
                            company=company,
                            location=location,
                            url=url_job,
                            source="occ",
                            description="",
                            salary=salary,
                            date_posted="",
                            remote=True,
                        ))
                    except Exception:
                        continue

                page.close()

            browser.close()

        return jobs

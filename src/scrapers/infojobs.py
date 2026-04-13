"""
InfoJobs España – bolsa líder en España, buena para roles IT remoto EU.
Usa Playwright (anti-bot con captcha bloquea requests simples).
"""
import re
import time
import random
from typing import List
from src.scrapers.base import BaseScraper
from src.database import Job

BASE_URL = "https://www.infojobs.net"

IJ_KEYWORDS = [
    "administrador sistemas linux",
    "sysadmin",
    "administrador linux",
    "ingeniero infraestructura",
    "devops",
    "administrador vmware",
]


class InfoJobsScraper(BaseScraper):
    name = "infojobs"

    def scrape(self) -> List[Job]:
        from playwright.sync_api import sync_playwright

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
                viewport={"width": 1280, "height": 900},
                locale="es-ES",
            )

            for keyword in IJ_KEYWORDS:
                time.sleep(random.uniform(2, 4))
                url = (
                    f"{BASE_URL}/jobsearch/search-results/list.xhtml"
                    f"?keyword={keyword.replace(' ', '+')}"
                    f"&teleworkingIds=1&sortBy=PUBLICATION_DATE"
                )

                page = ctx.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(3000)
                except Exception as e:
                    print(f"  [infojobs] Error en '{keyword}': {e}")
                    page.close()
                    continue

                # Si hay captcha, saltar
                if page.query_selector("[class*='captcha'], #captcha-box"):
                    print(f"  [infojobs] Captcha detectado en '{keyword}', saltando.")
                    page.close()
                    continue

                items = page.query_selector_all("li.ij-OfferList-offerCardItem")

                for item in items:
                    try:
                        link_el = item.query_selector("a.ij-OfferCardContent-description-link")
                        if not link_el:
                            continue
                        href = link_el.get_attribute("href") or ""
                        if href.startswith("//"):
                            href = "https:" + href
                        job_url = href.split("?")[0]
                        if not job_url or job_url in seen:
                            continue

                        title_el = item.query_selector(".ij-OfferCardContent-description-title")
                        title = title_el.inner_text().strip() if title_el else link_el.inner_text().strip()
                        if not title:
                            continue

                        company_el = item.query_selector("a.ij-OfferCardContent-description-subtitle-link")
                        if company_el:
                            company = company_el.inner_text().strip()
                        else:
                            full = item.inner_text()
                            parts = [p.strip() for p in full.split("\n") if p.strip()]
                            company = parts[1] if len(parts) > 1 else "Unknown"

                        full_text = item.inner_text().lower()
                        location = "España"
                        if re.search(r'teletrabajo|remoto|home\s*office|remote', full_text, re.I):
                            location = "Remote"

                        combined = f"{title} {company}".lower()
                        if not any(kw.lower() in combined for kw in self.keywords):
                            continue

                        seen.add(job_url)
                        jobs.append(Job(
                            title=title,
                            company=company,
                            location=location,
                            url=job_url,
                            source="infojobs",
                            description="",
                            salary="",
                            date_posted="",
                            remote="remote" in location.lower() or "teletrabajo" in location.lower(),
                        ))
                    except Exception:
                        continue

                page.close()

            browser.close()

        return jobs

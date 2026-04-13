"""
Glassdoor – usa Playwright para evitar la protección anti-bot.
Busca vacantes remotas usando el formato SEO de URL de Glassdoor.
Lanza un browser nuevo por keyword para evitar detección secuencial.
"""
import time
import random
from typing import List
from src.scrapers.base import BaseScraper
from src.database import Job

BASE_URL = "https://www.glassdoor.com.mx"



def _build_url(keyword: str) -> str:
    """Construye la URL SEO de Glassdoor para búsqueda remota."""
    location = "remote"
    loc_len = len(location)
    kw_slug = keyword.replace(" ", "-")
    kw_len = len(keyword)
    kw_start = loc_len + 1
    kw_end = kw_start + kw_len
    return (
        f"{BASE_URL}/Empleo/{location}-{kw_slug}-empleos-"
        f"SRCH_IL.0,{loc_len}_IS11047_KO{kw_start},{kw_end}.htm"
    )


def _scrape_keyword(p, keyword: str, seen: set) -> List[Job]:
    """Abre un browser nuevo por keyword para evitar detección."""
    jobs = []
    url = _build_url(keyword)

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
    page = ctx.new_page()

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(6000)
    except Exception as e:
        print(f"  [glassdoor] Error en '{keyword}': {e}")
        browser.close()
        return jobs

    cards = page.query_selector_all("li[data-jobid]")

    if not cards:
        browser.close()
        return jobs

    for card in cards:
        try:
            link_el = card.query_selector("a[href*='job-listing']")
            if not link_el:
                continue
            href = link_el.get_attribute("href") or ""
            if not href.startswith("http"):
                href = BASE_URL + href
            href = href.split("?")[0]

            if href in seen:
                continue

            title_el = card.query_selector('[data-test="job-title"]')
            company_el = card.query_selector('[class*="EmployerName"]')
            loc_el = card.query_selector('[data-test="emp-location"]')
            salary_el = card.query_selector('[data-test="detailSalary"]')

            title = title_el.inner_text().strip() if title_el else "Unknown"
            company = company_el.inner_text().strip() if company_el else "Unknown"
            location = loc_el.inner_text().strip() if loc_el else "Remote"
            salary = salary_el.inner_text().strip() if salary_el else ""

            if not title or title == "Unknown":
                continue

            seen.add(href)
            jobs.append(Job(
                title=title,
                company=company,
                location=location,
                url=href,
                source="glassdoor",
                description="",
                salary=salary,
                date_posted="",
                remote=True,
            ))
        except Exception:
            continue

    browser.close()
    return jobs


class GlassdoorScraper(BaseScraper):
    name = "glassdoor"

    def scrape(self) -> List[Job]:
        from playwright.sync_api import sync_playwright

        jobs = []
        seen = set()

        with sync_playwright() as p:
            for keyword in self.keywords:
                time.sleep(random.uniform(10, 20))
                found = _scrape_keyword(p, keyword, seen)
                jobs.extend(found)

        return jobs

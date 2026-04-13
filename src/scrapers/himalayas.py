"""
Himalayas – bolsa de trabajos remotos globales.
Usa Playwright por ser una SPA en Next.js.
"""
import re
import time
import random
from typing import List
from src.scrapers.base import BaseScraper
from src.database import Job

BASE_URL = "https://himalayas.app"

_date_pat = re.compile(r'^\d+ (day|month|year|hour)s? ago$|^yesterday$', re.I)
_skip = {"View job", "Sign up to save this job", "Sign up"}


class HimalayasScraper(BaseScraper):
    name = "himalayas"

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
                viewport={"width": 1280, "height": 800},
                locale="es-MX",
            )

            # ── 1. Scrape listing pages ──────────────────────────────────────
            for keyword in self.keywords:
                time.sleep(random.uniform(2, 4))
                url = f"{BASE_URL}/jobs?q={keyword.replace(' ', '+')}"

                page = ctx.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(4000)
                except Exception as e:
                    print(f"  [himalayas] Error en '{keyword}': {e}")
                    page.close()
                    continue

                for article in page.query_selector_all("article"):
                    try:
                        link_el = article.query_selector("a[href*='/jobs/']")
                        if not link_el:
                            continue

                        href = (link_el.get_attribute("href") or "").split("?")[0]
                        job_url = f"{BASE_URL}{href}" if href.startswith("/") else href

                        if job_url in seen:
                            continue

                        text_lines = [
                            l.strip() for l in article.inner_text().split("\n")
                            if l.strip() and l.strip() not in _skip
                        ]

                        title = ""
                        company = ""
                        location = "Remote"
                        for line in text_lines:
                            if _date_pat.match(line):
                                continue
                            if not title and len(line) > 3:
                                title = line
                            elif title and not company and len(line) > 2:
                                company = line
                                break

                        if not title:
                            continue

                        full_text = article.inner_text().lower()
                        if "only" in full_text:
                            loc_match = re.search(r'([A-Za-z ]+) only', article.inner_text())
                            if loc_match:
                                location = loc_match.group(1).strip() + " only"
                        elif "worldwide" in full_text or "🌏" in full_text or "🌎" in full_text:
                            location = "Worldwide"

                        if not any(kw.lower() in title.lower() for kw in self.keywords):
                            continue

                        seen.add(job_url)
                        jobs.append(Job(
                            title=title,
                            company=company,
                            location=location,
                            url=job_url,
                            source="himalayas",
                            description="",
                            salary="",
                            date_posted="",
                            remote=True,
                        ))
                    except Exception:
                        continue

                page.close()

            # ── 2. Fetch description for each job ────────────────────────────
            print(f"  [himalayas] Obteniendo descripciones de {len(jobs)} vacantes...")
            for job in jobs:
                try:
                    time.sleep(random.uniform(1.5, 3.0))
                    page = ctx.new_page()
                    page.goto(job.url, wait_until="domcontentloaded", timeout=25000)
                    page.wait_for_timeout(3000)

                    description = ""

                    # Try structured sections first (Requirements, Responsibilities, etc.)
                    section_texts = []
                    for heading in page.query_selector_all("h2, h3"):
                        heading_text = heading.inner_text().strip()
                        if not heading_text:
                            continue
                        # Grab sibling/following content until next heading
                        sibling = heading.evaluate_handle(
                            "el => el.nextElementSibling"
                        )
                        sibling_text = ""
                        try:
                            sibling_text = sibling.as_element().inner_text().strip() if sibling.as_element() else ""
                        except Exception:
                            pass
                        if sibling_text:
                            section_texts.append(f"{heading_text}\n{sibling_text}")

                    if section_texts:
                        description = "\n\n".join(section_texts)

                    # Fallback: look for common description containers
                    if not description:
                        for selector in [
                            "[class*='description']",
                            "[class*='job-detail']",
                            "[class*='content']",
                            "main article",
                            "main section",
                        ]:
                            el = page.query_selector(selector)
                            if el:
                                text = el.inner_text().strip()
                                if len(text) > 100:
                                    description = text
                                    break

                    job.description = description[:5000] if description else ""
                    page.close()
                except Exception as e:
                    print(f"  [himalayas] No se pudo obtener descripción de {job.url}: {e}")
                    try:
                        page.close()
                    except Exception:
                        pass

            browser.close()

        return jobs

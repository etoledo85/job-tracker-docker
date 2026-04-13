"""
LinkedIn Jobs – usa la API pública de búsqueda (sin login).
Limitada pero funcional para descubrir vacantes.
"""
import time
from typing import List
from bs4 import BeautifulSoup
from src.scrapers.base import BaseScraper
from src.database import Job

LINKEDIN_SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
LINKEDIN_DETAIL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{}"

# Mapeo de nombres de ciudad a formato que usa LinkedIn
CITY_MAP = {
    "monterrey": "Monterrey, Nuevo León, México",
    "saltillo":  "Saltillo, Coahuila, México",
    "guadalajara": "Guadalajara, Jalisco, México",
    "cdmx": "Ciudad de México, México",
    "mexico": "México",
}

REMOTE_NAMES = {"remote", "remoto"}


class LinkedInScraper(BaseScraper):
    name = "linkedin"

    def _build_search_terms(self):
        """Genera combinaciones keyword × ubicación desde el config."""
        city_locs = [l for l in self.locations if l.lower() not in REMOTE_NAMES]
        has_remote = any(l.lower() in REMOTE_NAMES for l in self.locations)
        seen_pairs = set()
        terms = []
        for kw in self.keywords:
            for loc in city_locs:
                linkedin_loc = CITY_MAP.get(loc.lower(), loc)
                pair = (kw.lower(), linkedin_loc.lower())
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    terms.append((kw, linkedin_loc))
            if has_remote:
                pair = (kw.lower(), "")
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    terms.append((kw, ""))
        return terms

    def scrape(self) -> List[Job]:
        jobs = []
        seen = set()

        search_terms = self._build_search_terms()

        for keyword, location in search_terms:
            params = {
                "keywords": keyword,
                "location": location,
                "f_TPR": "r1209600",  # últimas 2 semanas
                "start": 0,
            }
            if not location:
                params["f_WT"] = "2"  # remote only

            try:
                resp = self._get(LINKEDIN_SEARCH, params=params)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
            except Exception as e:
                print(f"  [linkedin] Error buscando '{keyword}': {e}")
                continue

            cards = soup.find_all("li")
            for card in cards:
                try:
                    job_id_tag = card.find("div", {"data-entity-urn": True})
                    if not job_id_tag:
                        continue
                    urn = job_id_tag["data-entity-urn"]
                    job_id = urn.split(":")[-1]
                    url = f"https://www.linkedin.com/jobs/view/{job_id}"

                    if url in seen:
                        continue

                    title_tag = card.find("h3") or card.find("span", class_="sr-only")
                    title = title_tag.get_text(strip=True) if title_tag else "Unknown"

                    company_tag = card.find("h4") or card.find("a", {"data-tracking-control-name": True})
                    company = company_tag.get_text(strip=True) if company_tag else "Unknown"

                    location_tag = card.find("span", class_=lambda c: c and "location" in c.lower())
                    loc = location_tag.get_text(strip=True) if location_tag else location

                    is_remote = "remote" in loc.lower() or not location

                    # Fetch descripción
                    desc = self._fetch_description(job_id)

                    seen.add(url)
                    jobs.append(Job(
                        title=title,
                        company=company,
                        location=loc or location,
                        url=url,
                        source="linkedin",
                        description=desc,
                        remote=is_remote,
                    ))
                except Exception:
                    continue

            time.sleep(2)

        return jobs

    def _fetch_description(self, job_id: str) -> str:
        try:
            resp = self._get(LINKEDIN_DETAIL.format(job_id))
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            desc_div = soup.find("div", class_="description__text") or \
                       soup.find("div", {"class": lambda c: c and "show-more-less-html" in c})
            if desc_div:
                return desc_div.get_text(separator="\n", strip=True)[:3000]
        except Exception:
            pass
        return ""

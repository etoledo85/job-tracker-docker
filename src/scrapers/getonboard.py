"""
Get on Board (getonbrd.com) – bolsa LATAM, fuerte en Chile/MX.
Usa la API de búsqueda /api/v0/search/jobs.
published_at es Unix timestamp.
"""
import time
import random
from datetime import datetime, timezone, timedelta
from typing import List
from src.scrapers.base import BaseScraper
from src.database import Job

GOB_SEARCH = "https://www.getonbrd.com/api/v0/search/jobs"

# Keywords adaptadas para el mercado LATAM tech
SEARCH_TERMS = [
    "sysadmin",
    "linux administrator",
    "infrastructure engineer",
    "devops",
    "administrador sistemas",
    "administrador linux",
]


class GetOnBoardScraper(BaseScraper):
    name = "getonboard"

    def scrape(self) -> List[Job]:
        jobs = []
        seen = set()
        cutoff = datetime.now(timezone.utc) - timedelta(days=21)

        for term in SEARCH_TERMS:
            time.sleep(random.uniform(1.5, 3.0))
            try:
                resp = self._get(
                    GOB_SEARCH,
                    params={"query": term, "remote": "true", "page": 1, "per_page": 30},
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"  [getonboard] Error en '{term}': {e}")
                continue

            for item in data.get("data", []):
                try:
                    attrs = item.get("attributes", {})
                    links = item.get("links", {})

                    url = links.get("public_url", "")
                    if not url or url in seen:
                        continue

                    title = attrs.get("title", "").strip()
                    if not title:
                        continue

                    # Extraer empresa del slug de la URL
                    # Formato: /jobs/title-company-city  →  penúltimo segmento
                    slug = url.rstrip("/").split("/")[-1]
                    company = "Unknown"
                    if "-" in slug:
                        # El slug suele ser: rol-empresa-ciudad
                        parts = slug.split("-")
                        # Intentar extraer empresa: segmento entre el rol y la ciudad
                        company = parts[-2].capitalize() if len(parts) >= 2 else "Unknown"

                    remote = bool(attrs.get("remote", False))
                    countries = attrs.get("countries") or []
                    if remote or "Remote" in countries:
                        location = "Remote"
                    else:
                        location = ", ".join(countries) if countries else "LATAM"

                    # published_at es Unix timestamp
                    ts = attrs.get("published_at")
                    date_posted = ""
                    if ts:
                        try:
                            dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                            if dt < cutoff:
                                continue
                            date_posted = dt.strftime("%Y-%m-%d")
                        except Exception:
                            pass

                    desc = attrs.get("description", "") or ""
                    combined = f"{title} {desc}".lower()
                    if not any(kw.lower() in combined for kw in self.keywords):
                        continue

                    seen.add(url)
                    jobs.append(Job(
                        title=title,
                        company=company,
                        location=location,
                        url=url,
                        source="getonboard",
                        description=desc[:3000],
                        salary="",
                        date_posted=date_posted,
                        remote=remote,
                    ))
                except Exception:
                    continue

        return jobs

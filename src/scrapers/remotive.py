"""
Remotive.com – tiene API pública, perfecta para sysadmin/devops remoto.
"""
from typing import List
from src.scrapers.base import BaseScraper
from src.database import Job

CATEGORY_MAP = {
    "devops": "devops",
    "sysadmin": "devops",
    "systems administrator": "devops",
    "linux": "devops",
    "infrastructure": "devops",
}

REMOTIVE_API = "https://remotive.com/api/remote-jobs"


class RemotiveScraper(BaseScraper):
    name = "remotive"

    def scrape(self) -> List[Job]:
        jobs = []
        seen_urls = set()
        categories = ["devops"]

        for category in categories:
            try:
                resp = self._get(REMOTIVE_API, params={"category": category, "limit": 100})
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"  [remotive] Error en categoría {category}: {e}")
                continue

            for item in data.get("jobs", []):
                url = item.get("url", "")
                if not url or url in seen_urls:
                    continue

                title = item.get("title", "")
                company = item.get("company_name", "")
                desc = item.get("description", "")
                salary = item.get("salary", "")
                date_posted = item.get("publication_date", "")[:10]

                # Filtrar por relevancia y antigüedad
                combined = f"{title} {desc}".lower()
                relevant = any(kw.lower() in combined for kw in self.keywords)
                if not relevant:
                    continue
                if not self._is_recent(date_posted):
                    continue

                seen_urls.add(url)
                jobs.append(Job(
                    title=title,
                    company=company,
                    location="Remote",
                    url=url,
                    source="remotive",
                    description=desc[:3000],
                    salary=salary,
                    date_posted=date_posted,
                    remote=True,
                ))

        return jobs

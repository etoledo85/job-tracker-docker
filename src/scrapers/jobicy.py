"""
Jobicy.com — API pública de empleos remotos.
Devuelve hasta 50 jobs por request; filtramos por keywords en título y descripción.
"""
from typing import List
from src.scrapers.base import BaseScraper
from src.database import Job

JOBICY_API = "https://jobicy.com/api/v2/remote-jobs"


class JobicyScraper(BaseScraper):
    name = "jobicy"

    def scrape(self) -> List[Job]:
        jobs = []
        seen_urls = set()

        try:
            resp = self._get(JOBICY_API, params={"count": 50})
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  [jobicy] Error: {e}")
            return jobs

        for item in data.get("jobs", []):
            url = item.get("url", "")
            if not url or url in seen_urls:
                continue

            title = item.get("jobTitle", "")
            company = item.get("companyName", "")
            location = item.get("jobGeo", "Worldwide")
            description = item.get("jobDescription", "") or item.get("jobExcerpt", "")
            date_posted = item.get("pubDate", "")[:10]

            combined = f"{title} {description}".lower()
            if not any(kw.lower() in combined for kw in self.keywords):
                continue
            if not self._is_recent(date_posted, days=30):
                continue

            seen_urls.add(url)
            jobs.append(Job(
                title=title,
                company=company,
                location=location if location else "Worldwide",
                url=url,
                source="jobicy",
                description=description[:3000],
                salary="",
                date_posted=date_posted,
                remote=True,
            ))

        return jobs

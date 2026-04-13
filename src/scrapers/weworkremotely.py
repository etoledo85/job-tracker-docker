"""
WeWorkRemotely – RSS feed para trabajos remotos DevOps/Sysadmin.
"""
import xml.etree.ElementTree as ET
from typing import List
from src.scrapers.base import BaseScraper
from src.database import Job

WWR_FEEDS = [
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
    "https://weworkremotely.com/categories/remote-system-admin-jobs.rss",
]


class WeWorkRemotelyScraper(BaseScraper):
    name = "weworkremotely"

    def scrape(self) -> List[Job]:
        jobs = []
        seen = set()

        for feed_url in WWR_FEEDS:
            try:
                resp = self._get(feed_url)
                resp.raise_for_status()
                root = ET.fromstring(resp.text)
            except Exception as e:
                print(f"  [wwr] Error: {e}")
                continue

            channel = root.find("channel")
            if channel is None:
                continue

            for item in channel.findall("item"):
                url = (item.findtext("link") or "").strip()
                if not url or url in seen:
                    continue

                title = item.findtext("title") or ""
                # WWR title format: "Company: Job Title"
                if ": " in title:
                    company, title = title.split(": ", 1)
                else:
                    company = "Unknown"

                desc = item.findtext("description") or ""
                date_posted = item.findtext("pubDate", "")[:16]

                combined = f"{title} {desc}".lower()
                relevant = any(kw.lower() in combined for kw in self.keywords)
                if not relevant:
                    continue
                if not self._is_recent(date_posted):
                    continue

                seen.add(url)
                jobs.append(Job(
                    title=title.strip(),
                    company=company.strip(),
                    location="Remote",
                    url=url,
                    source="weworkremotely",
                    description=desc[:3000],
                    date_posted=date_posted,
                    remote=True,
                ))

        return jobs

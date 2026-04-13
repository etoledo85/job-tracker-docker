import re
import time
import random
import unicodedata
import requests
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List
from src.database import Job

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class BaseScraper:
    name: str = "base"

    def __init__(self, keywords: List[str], locations: List[str]):
        self.keywords = keywords
        self.locations = locations
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def scrape(self) -> List[Job]:
        raise NotImplementedError

    def _get(self, url: str, **kwargs) -> requests.Response:
        time.sleep(random.uniform(1.5, 3.5))
        return self.session.get(url, timeout=15, **kwargs)

    def _is_recent(self, date_str: str, days: int = 14) -> bool:
        """True si date_str está dentro de los últimos `days` días. Si no hay fecha, incluye por defecto."""
        if not date_str:
            return True
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = parsedate_to_datetime(date_str)
            except Exception:
                return True
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= datetime.now(timezone.utc) - timedelta(days=days)

    def _slugify(self, text: str) -> str:
        """Convierte texto a slug URL-friendly (minúsculas, espacios→guiones, sin acentos)."""
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ascii", "ignore").decode("ascii")
        text = re.sub(r"[^\w\s-]", "", text.lower())
        return re.sub(r"[\s_]+", "-", text).strip("-")

    def _is_relevant(self, text: str, exclude: List[str] = None) -> bool:
        text_lower = text.lower()
        if exclude:
            for kw in exclude:
                if kw.lower() in text_lower:
                    return False
        return True

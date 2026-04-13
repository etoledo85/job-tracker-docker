"""
Wellfound (AngelList Talent) – startups tech global.
ESTADO: protegido con DataDome anti-bot. Scraper deshabilitado.
Alternativa: buscar manualmente en wellfound.com/jobs o via LinkedIn.
"""
from typing import List
from src.scrapers.base import BaseScraper
from src.database import Job


class WellfoundScraper(BaseScraper):
    name = "wellfound"

    def scrape(self) -> List[Job]:
        print("  [wellfound] Bloqueado por DataDome anti-bot. Saltando.")
        return []

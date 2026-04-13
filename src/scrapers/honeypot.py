"""
Honeypot.io – PLATAFORMA CERRADA (mayo 2023, migró a XING/New Work SE).
Este scraper está deshabilitado; retorna lista vacía con aviso.
"""
from typing import List
from src.scrapers.base import BaseScraper
from src.database import Job


class HoneypotScraper(BaseScraper):
    name = "honeypot"

    def scrape(self) -> List[Job]:
        print("  [honeypot] Plataforma cerrada en 2023. Fuente deshabilitada.")
        return []

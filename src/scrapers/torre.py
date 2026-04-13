"""
Torre.ai – bolsa LATAM.
ESTADO: búsqueda pública requiere login desde 2024. Scraper deshabilitado.
Alternativa: usar Get on Board o LinkedIn para LATAM.
"""
from typing import List
from src.scrapers.base import BaseScraper
from src.database import Job


class TorreScraper(BaseScraper):
    name = "torre"

    def scrape(self) -> List[Job]:
        print("  [torre] Búsqueda pública requiere login (cambiaron en 2024). Saltando.")
        return []

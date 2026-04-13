"""
Computrabajo México – bolsa de trabajo latinoamericana.
"""
from typing import List
from bs4 import BeautifulSoup
from src.scrapers.base import BaseScraper
from src.database import Job

BASE_URL = "https://www.computrabajo.com.mx"

REMOTE_NAMES = {"remote", "remoto"}


class ComputrabajoScraper(BaseScraper):
    name = "computrabajo"

    def _build_queries(self):
        """Genera combinaciones keyword-slug × ciudad desde el config."""
        city_locs = [l.lower() for l in self.locations if l.lower() not in REMOTE_NAMES]
        seen_pairs = set()
        queries = []
        for kw in self.keywords:
            slug = self._slugify(kw)
            # Por cada ciudad del config
            for city in city_locs:
                pair = (slug, city)
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    queries.append((slug, city))
            # Búsqueda nacional/remoto (sin ciudad)
            pair = (slug, "")
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                queries.append((slug, ""))
        return queries

    def scrape(self) -> List[Job]:
        jobs = []
        seen = set()

        for role, city in self._build_queries():
            if city:
                url = f"{BASE_URL}/trabajo-de-{role}-en-{city}"
            else:
                url = f"{BASE_URL}/trabajo-de-{role}"

            try:
                resp = self._get(url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
            except Exception as e:
                print(f"  [computrabajo] Error en {url}: {e}")
                continue

            articles = soup.select("article[data-id]")

            for art in articles:
                try:
                    # Título y URL
                    title_tag = art.select_one("h2 a.js-o-link")
                    if not title_tag:
                        continue
                    title = title_tag.get_text(strip=True)
                    href = title_tag.get("href", "")
                    if not href.startswith("http"):
                        href = BASE_URL + href
                    # Limpiar tracking param del href
                    href = href.split("#")[0]

                    if href in seen:
                        continue

                    # Empresa
                    company_tag = art.select_one("p.fs16 a.fc_base")
                    company = company_tag.get_text(strip=True) if company_tag else "Unknown"
                    # Limpiar rating numérico al inicio (ej. "4.3Empresa")
                    if company and company[0].isdigit():
                        import re
                        company = re.sub(r"^\d+\.\d+", "", company).strip()

                    # Ubicación: segundo p.fs16, primer span
                    loc_paras = art.select("p.fs16")
                    loc = city.capitalize()
                    for p in loc_paras:
                        span = p.find("span")
                        if span and not p.find("a"):
                            loc = span.get_text(strip=True)
                            break

                    # Remoto
                    work_mode = art.select_one("div.fs13 span")
                    work_text = work_mode.get_text(strip=True).lower() if work_mode else ""
                    is_remote = "remoto" in work_text or "home office" in work_text

                    # Fecha
                    date_tag = art.select_one("p.fc_aux")
                    date_posted = date_tag.get_text(strip=True) if date_tag else ""

                    desc = self._fetch_description(href)

                    seen.add(href)
                    jobs.append(Job(
                        title=title,
                        company=company,
                        location=loc,
                        url=href,
                        source="computrabajo",
                        description=desc,
                        date_posted=date_posted,
                        remote=is_remote,
                    ))
                except Exception:
                    continue

        return jobs

    def _fetch_description(self, url: str) -> str:
        try:
            resp = self._get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            box = (
                soup.select_one("div.box_detail_offer")
                or soup.select_one("section#offerdesc")
                or soup.select_one("[class*='description']")
            )
            if box:
                return box.get_text(separator="\n", strip=True)[:3000]
        except Exception:
            pass
        return ""

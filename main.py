#!/usr/bin/env python3
"""
Job Tracker CLI – Automatiza tu búsqueda de trabajo
Uso: python main.py [COMMAND]
"""
import sys
import os
from pathlib import Path

# Asegurar que el directorio del proyecto esté en el path
sys.path.insert(0, str(Path(__file__).parent))

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich import print as rprint

from src.database import init_db, upsert_job, get_jobs, get_job, update_job, get_stats, VALID_STATUSES
from src.config import load_config

app = typer.Typer(help="Job Tracker – Búsqueda automatizada de vacantes")
console = Console()

STATUS_COLORS = {
    "new": "bright_cyan",
    "reviewing": "yellow",
    "applied": "green",
    "interview": "bright_green",
    "rejected": "red",
    "offer": "bold green",
    "discarded": "dim",
}

STATUS_EMOJI = {
    "new": "🆕",
    "reviewing": "👀",
    "applied": "📤",
    "interview": "🎯",
    "rejected": "❌",
    "offer": "🎉",
    "discarded": "🗑",
}


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Job Tracker – automatiza tu búsqueda de trabajo."""
    init_db()
    if ctx.invoked_subcommand is None:
        rprint(Panel.fit(
            "[bold cyan]Job Tracker[/bold cyan] – Automatiza tu búsqueda de empleo\n\n"
            "  [green]python main.py scrape[/green]         Buscar nuevas vacantes\n"
            "  [green]python main.py list[/green]           Ver vacantes guardadas\n"
            "  [green]python main.py show <id>[/green]      Ver detalle de una vacante\n"
            "  [green]python main.py tailor <id>[/green]    Analizar fit CV vs vacante (ATS score)\n"
            "  [green]python main.py cv <id>[/green]        Generar CV personalizado para la vacante\n"
            "  [green]python main.py generate <id>[/green]  Generar cover letter personalizada\n"
            "  [green]python main.py apply <id>[/green]     Generar + enviar cover letter\n"
            "  [green]python main.py status <id>[/green]    Actualizar estado\n"
            "  [green]python main.py stats[/green]          Ver estadísticas\n",
            title="[bold]Comandos disponibles[/bold]",
            border_style="cyan"
        ))


@app.command()
def scrape(
    sources: str = typer.Option("all", "--sources", "-s",
                                help="Fuentes: all, remotive, wwr, linkedin, computrabajo, glassdoor, "
                                     "torre, getonboard, wellfound, hireline, honeypot, infojobs")
):
    """Busca nuevas vacantes en todas las bolsas configuradas."""
    init_db()
    cfg = load_config()
    keywords = cfg["search"]["keywords"]
    locations = cfg["search"]["locations"]
    exclude = cfg["search"].get("exclude_keywords", [])
    exclude_locations = cfg["search"].get("exclude_locations", [])
    exclude_titles = [t.lower() for t in cfg["search"].get("exclude_titles", [])]
    exclude_us_cities = [c.lower() for c in cfg["search"].get("exclude_us_cities", [])]

    from src.scrapers.remotive import RemotiveScraper
    from src.scrapers.weworkremotely import WeWorkRemotelyScraper
    from src.scrapers.linkedin import LinkedInScraper
    from src.scrapers.computrabajo import ComputrabajoScraper
    from src.scrapers.glassdoor import GlassdoorScraper
    from src.scrapers.occ import OCCScraper
    from src.scrapers.remoteok import RemoteOKScraper
    from src.scrapers.himalayas import HimalayasScraper
    from src.scrapers.torre import TorreScraper
    from src.scrapers.getonboard import GetOnBoardScraper
    from src.scrapers.wellfound import WellfoundScraper
    from src.scrapers.hireline import HirelineScraper
    from src.scrapers.honeypot import HoneypotScraper
    from src.scrapers.infojobs import InfoJobsScraper

    scrapers_map = {
        "remotive": RemotiveScraper,
        "wwr": WeWorkRemotelyScraper,
        "linkedin": LinkedInScraper,
        "computrabajo": ComputrabajoScraper,
        "glassdoor": GlassdoorScraper,
        "occ": OCCScraper,
        "remoteok": RemoteOKScraper,
        "himalayas": HimalayasScraper,
        # Tier 1 – agregados
        "torre": TorreScraper,
        "getonboard": GetOnBoardScraper,
        "wellfound": WellfoundScraper,
        # Tier 2 – agregados
        "hireline": HirelineScraper,
        "honeypot": HoneypotScraper,
        "infojobs": InfoJobsScraper,
    }

    DEFAULT_SOURCES = [
        "remotive", "wwr", "linkedin", "computrabajo", "occ",
        "remoteok", "himalayas",
        "torre", "getonboard", "wellfound",
        "hireline", "honeypot", "infojobs",
    ]

    if sources == "all":
        active_names = DEFAULT_SOURCES
        active = [scrapers_map[n] for n in active_names]
    else:
        names = [s.strip() for s in sources.split(",")]
        active = [scrapers_map[n] for n in names if n in scrapers_map]
        active_names = names

    total_new = 0
    total_found = 0

    for ScraperClass, name in zip(active, active_names):
        console.rule(f"[cyan]{name.upper()}[/cyan]")
        scraper = ScraperClass(keywords=keywords, locations=locations)

        with console.status(f"Buscando en {name}..."):
            try:
                jobs = scraper.scrape()
            except Exception as e:
                console.print(f"  [red]Error:[/red] {e}")
                continue

        new_count = 0
        for job in jobs:
            title_lower = job.title.lower()
            combined = f"{job.title} {job.description}".lower()
            loc_lower = (job.location or "").lower()

            # 1. El título debe contener al menos una keyword relevante
            if not any(kw.lower() in title_lower for kw in keywords):
                continue

            # 2. Títulos de nivel incorrecto (Systems Administrator I, etc.)
            if any(title_lower == t or title_lower.startswith(t) for t in exclude_titles):
                continue

            # 3. Keywords excluidas en título/descripción
            if any(kw.lower() in combined for kw in exclude):
                continue

            # 4. Ubicaciones excluidas (presencial CDMX y zonas adyacentes)
            if not job.remote and exclude_locations:
                if any(el.lower() in loc_lower for el in exclude_locations):
                    continue

            # 5. Restricciones geográficas duras (X only = no acepta desde MX)
            if "only" in loc_lower and not any(
                ok in loc_lower for ok in ["mexico only", "méxico only", "latam only",
                                           "worldwide", "remote only"]
            ):
                continue

            # 6. Presencial USA (ciudad+estado = on-site, no remoto real para MX)
            if exclude_us_cities and any(city in loc_lower for city in exclude_us_cities):
                continue

            is_new, job_id = upsert_job(job)
            if is_new:
                new_count += 1
                console.print(f"  [green]+[/green] [{job_id}] {job.title} @ {job.company} – {job.location}")

        total_new += new_count
        total_found += len(jobs)
        console.print(f"  → {len(jobs)} encontradas, [bold green]{new_count} nuevas[/bold green]")

    console.rule()
    console.print(f"\n[bold]Total:[/bold] {total_found} vacantes procesadas, "
                  f"[bold green]{total_new} nuevas[/bold green] guardadas.")
    if total_new > 0:
        console.print("Ejecuta [cyan]python main.py list[/cyan] para verlas.")


@app.command(name="list")
def list_jobs(
    status: str = typer.Option(None, "--status", "-s", help="Filtrar por estado"),
    limit: int = typer.Option(30, "--limit", "-n"),
    remote_only: bool = typer.Option(False, "--remote", "-r", help="Solo remotas"),
):
    """Lista las vacantes guardadas."""
    init_db()
    jobs = get_jobs(status=status, limit=limit)

    if remote_only:
        jobs = [j for j in jobs if j["remote"]]

    if not jobs:
        msg = "No hay vacantes"
        if status:
            msg += f" con estado '{status}'"
        console.print(f"[yellow]{msg}.[/yellow]")
        raise typer.Exit()

    table = Table(title=f"Vacantes ({len(jobs)})", border_style="cyan", show_lines=False)
    table.add_column("ID", style="dim", width=5)
    table.add_column("Título", min_width=25)
    table.add_column("Empresa", min_width=20)
    table.add_column("Ubicación", min_width=15)
    table.add_column("Fuente", width=14)
    table.add_column("Estado", width=12)
    table.add_column("Fecha", width=10)

    for job in jobs:
        st = job["status"]
        color = STATUS_COLORS.get(st, "white")
        emoji = STATUS_EMOJI.get(st, "")
        remote_tag = " 🌐" if job["remote"] else ""
        date = (job["date_found"] or "")[:10]

        table.add_row(
            str(job["id"]),
            job["title"],
            job["company"],
            job["location"] + remote_tag,
            job["source"],
            f"[{color}]{emoji} {st}[/{color}]",
            date,
        )

    console.print(table)
    console.print(f"\n[dim]Estados: {', '.join(VALID_STATUSES)}[/dim]")
    console.print("[dim]python main.py show <id> para ver detalles[/dim]")


@app.command()
def show(job_id: int):
    """Muestra el detalle completo de una vacante."""
    init_db()
    job = get_job(job_id)
    if not job:
        console.print(f"[red]Vacante #{job_id} no encontrada.[/red]")
        raise typer.Exit(1)

    st = job["status"]
    color = STATUS_COLORS.get(st, "white")
    remote_str = "Sí 🌐" if job["remote"] else "No"

    console.print(Panel(
        f"[bold]{job['title']}[/bold]\n"
        f"Empresa:    {job['company']}\n"
        f"Ubicación:  {job['location']} | Remoto: {remote_str}\n"
        f"Fuente:     {job['source']}\n"
        f"URL:        [link={job['url']}]{job['url']}[/link]\n"
        f"Salario:    {job['salary'] or 'No especificado'}\n"
        f"Publicado:  {job['date_posted'] or 'Desconocido'}\n"
        f"Estado:     [{color}]{STATUS_EMOJI.get(st,'')} {st}[/{color}]\n"
        f"Cover:      {job['cover_letter_path'] or 'No generada'}\n"
        f"Notas:      {job['notes'] or '-'}",
        title=f"[cyan]Vacante #{job_id}[/cyan]",
        border_style="cyan"
    ))

    if job["description"]:
        show_desc = Confirm.ask("¿Mostrar descripción completa?", default=False)
        if show_desc:
            console.print(Panel(job["description"][:3000], title="Descripción", border_style="dim"))

    # Sugerir acciones
    console.print("\n[dim]Acciones:[/dim]")
    console.print(f"  [green]python main.py generate {job_id}[/green]  → Generar cover letter")
    console.print(f"  [green]python main.py apply {job_id}[/green]     → Generar + enviar")
    console.print(f"  [green]python main.py status {job_id}[/green]    → Cambiar estado")


@app.command()
def generate(job_id: int):
    """Genera una cover letter personalizada para una vacante."""
    init_db()
    job = get_job(job_id)
    if not job:
        console.print(f"[red]Vacante #{job_id} no encontrada.[/red]")
        raise typer.Exit(1)

    from src.cover_letter import generate_cover_letter

    console.print(f"Generando cover letter para: [cyan]{job['title']} @ {job['company']}[/cyan]")

    with console.status("Consultando a Claude..."):
        try:
            path = generate_cover_letter(
                job_id=job_id,
                job_title=job["title"],
                company=job["company"],
                description=job["description"],
                url=job["url"],
            )
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

    update_job(job_id, cover_letter_path=path, status="reviewing")

    console.print(f"\n[bold green]Cover letter generada:[/bold green] {path}")
    console.print("\n--- PREVIEW ---")
    from pypdf import PdfReader
    reader = PdfReader(path)
    letter = "\n\n".join(page.extract_text() for page in reader.pages)
    console.print(Panel(letter, border_style="green"))

    edit = Confirm.ask("¿Deseas editar la cover letter antes de enviar?", default=False)
    if edit:
        console.print(f"Edita el archivo en: [cyan]{path}[/cyan]")
        console.print("Cuando termines, ejecuta: [cyan]python main.py apply {job_id}[/cyan]")
    else:
        send_now = Confirm.ask("¿Enviar ahora por email?", default=False)
        if send_now:
            _do_send(job_id, job, path)


@app.command()
def apply(job_id: int):
    """Genera (o reutiliza) cover letter y la envía por email."""
    init_db()
    job = get_job(job_id)
    if not job:
        console.print(f"[red]Vacante #{job_id} no encontrada.[/red]")
        raise typer.Exit(1)

    path = job["cover_letter_path"]

    if not path or not Path(path).exists():
        console.print("No hay cover letter. Generando una nueva...")
        from src.cover_letter import generate_cover_letter
        with console.status("Consultando a Claude..."):
            try:
                path = generate_cover_letter(
                    job_id=job_id,
                    job_title=job["title"],
                    company=job["company"],
                    description=job["description"],
                    url=job["url"],
                )
            except Exception as e:
                console.print(f"[red]Error generando cover letter:[/red] {e}")
                raise typer.Exit(1)
        update_job(job_id, cover_letter_path=path)

    # Mostrar preview
    from pypdf import PdfReader
    reader = PdfReader(path)
    letter = "\n\n".join(page.extract_text() for page in reader.pages)
    console.print(Panel(letter, title="[cyan]Cover Letter[/cyan]", border_style="cyan"))

    _do_send(job_id, job, path)


def _do_send(job_id: int, job, path: str):
    """Maneja el flujo de envío de email."""
    from src.email_sender import send_application, send_self_copy
    cfg = load_config()

    console.print("\n[bold]Enviar cover letter:[/bold]")
    to_email = Prompt.ask("Email del reclutador/empresa (o Enter para enviarte una copia)")

    if not to_email:
        to_email = cfg["profile"]["email"]
        console.print(f"[yellow]Enviando copia a tu propio correo: {to_email}[/yellow]")

    subject = Prompt.ask(
        "Asunto del email",
        default=f"Aplicación – {job['title']} | {cfg['profile']['name']}"
    )

    if not Confirm.ask(f"¿Confirmar envío a [cyan]{to_email}[/cyan]?", default=True):
        console.print("[yellow]Envío cancelado.[/yellow]")
        return

    with console.status("Enviando..."):
        try:
            send_application(
                to_email=to_email,
                job_title=job["title"],
                company=job["company"],
                cover_letter_path=path,
                subject=subject,
            )
        except Exception as e:
            console.print(f"[red]Error enviando email:[/red] {e}")
            return

    update_job(job_id, status="applied")
    console.print(f"[bold green]Email enviado correctamente a {to_email}[/bold green]")
    console.print(f"Estado actualizado a: [green]applied[/green]")


@app.command()
def status(
    job_id: int,
    new_status: str = typer.Argument(None, help=f"Nuevo estado: {', '.join(VALID_STATUSES)}")
):
    """Actualiza el estado de una vacante."""
    init_db()
    job = get_job(job_id)
    if not job:
        console.print(f"[red]Vacante #{job_id} no encontrada.[/red]")
        raise typer.Exit(1)

    if not new_status:
        console.print(f"Estado actual: [cyan]{job['status']}[/cyan]")
        console.print(f"Estados válidos: {', '.join(VALID_STATUSES)}")
        new_status = Prompt.ask("Nuevo estado")

    if new_status not in VALID_STATUSES:
        console.print(f"[red]Estado inválido.[/red] Válidos: {', '.join(VALID_STATUSES)}")
        raise typer.Exit(1)

    notes = Prompt.ask("Notas (opcional, Enter para omitir)", default="")
    update_kwargs = {"status": new_status}
    if notes:
        update_kwargs["notes"] = notes
    update_job(job_id, **update_kwargs)

    color = STATUS_COLORS.get(new_status, "white")
    console.print(f"[bold]Vacante #{job_id}[/bold] → [{color}]{new_status}[/{color}]")


@app.command()
def tailor(job_id: int):
    """Analiza el fit CV vs vacante y sugiere ajustes para mejorar el match ATS."""
    init_db()
    job = get_job(job_id)
    if not job:
        console.print(f"[red]Vacante #{job_id} no encontrada.[/red]")
        raise typer.Exit(1)

    if not job["description"]:
        console.print(f"[red]Vacante #{job_id} no tiene descripción. Intenta re-scrapear o agrégala manualmente.[/red]")
        raise typer.Exit(1)

    console.print(f"Analizando fit para: [cyan]{job['title']} @ {job['company']}[/cyan]")

    from src.cv_tailor import analyze_fit

    with console.status("Consultando a Claude..."):
        try:
            result = analyze_fit(
                job_title=job["title"],
                company=job["company"],
                description=job["description"],
            )
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

    score = result.get("match_score", 0)
    if score >= 70:
        score_color = "bold green"
    elif score >= 45:
        score_color = "yellow"
    else:
        score_color = "red"

    # Score banner
    console.print(Panel(
        f"[{score_color}]ATS Match Score: {score}/100[/{score_color}]\n\n"
        f"[dim]{result.get('overall_verdict', '')}[/dim]",
        title=f"[cyan]CV Tailor — #{job_id}[/cyan]",
        border_style="cyan"
    ))

    # Keywords match
    matched = result.get("matched_keywords", [])
    missing = result.get("missing_keywords", [])
    critical = result.get("critical_gaps", [])

    if matched:
        console.print(f"\n[bold green]Keywords que YA tienes ({len(matched)}):[/bold green]")
        console.print("  " + "  |  ".join(f"[green]{k}[/green]" for k in matched))

    if missing:
        console.print(f"\n[bold yellow]Keywords que FALTAN en tu CV ({len(missing)}):[/bold yellow]")
        console.print("  " + "  |  ".join(f"[yellow]{k}[/yellow]" for k in missing))

    if critical:
        console.print(f"\n[bold red]Gaps críticos:[/bold red]")
        for gap in critical:
            console.print(f"  [red]✗[/red] {gap}")

    # Reword suggestions
    suggestions = result.get("reword_suggestions", [])
    if suggestions:
        from rich.table import Table as RichTable
        tbl = RichTable(title="Sugerencias de rewording", border_style="dim", show_lines=True)
        tbl.add_column("Tu CV dice", style="dim", min_width=30)
        tbl.add_column("Cámbialo por", style="bold", min_width=30)
        for s in suggestions:
            tbl.add_row(s.get("cv_phrase", ""), s.get("suggested", ""))
        console.print()
        console.print(tbl)

    # Cover letter angle
    angle = result.get("cover_letter_angle", "")
    if angle:
        console.print(f"\n[bold]Ángulo para cover letter:[/bold] [italic]{angle}[/italic]")

    # Guardar resultado en notas
    notes_summary = f"[Tailor] Score: {score}/100. Gaps: {', '.join(critical) if critical else 'ninguno crítico'}."
    existing_notes = job["notes"] or ""
    if "[Tailor]" in existing_notes:
        # Reemplazar análisis previo
        import re
        new_notes = re.sub(r"\[Tailor\].*?(?=\n|$)", notes_summary, existing_notes).strip()
    else:
        new_notes = (existing_notes + "\n" + notes_summary).strip()
    update_job(job_id, notes=new_notes)

    console.print(f"\n[dim]Análisis guardado en notas de la vacante.[/dim]")
    console.print(f"[dim]Siguiente paso:[/dim] [green]python main.py generate {job_id}[/green] → cover letter optimizada")


@app.command()
def cv(job_id: int):
    """Genera un CV personalizado (PDF) optimizado para una vacante específica."""
    init_db()
    job = get_job(job_id)
    if not job:
        console.print(f"[red]Vacante #{job_id} no encontrada.[/red]")
        raise typer.Exit(1)

    if not job["description"]:
        console.print(f"[red]Vacante #{job_id} sin descripción. Ejecuta tailor primero.[/red]")
        raise typer.Exit(1)

    console.print(f"Generando CV personalizado para: [cyan]{job['title']} @ {job['company']}[/cyan]")

    from src.cv_tailor import analyze_fit, generate_tailored_cv

    with console.status("Analizando fit con Claude..."):
        try:
            tailor_result = analyze_fit(
                job_title=job["title"],
                company=job["company"],
                description=job["description"],
            )
        except Exception as e:
            console.print(f"[red]Error en análisis:[/red] {e}")
            raise typer.Exit(1)

    score = tailor_result.get("match_score", 0)
    console.print(f"ATS score base: [bold]{score}/100[/bold] → generando CV optimizado...")

    with console.status("Escribiendo CV tailored con Claude..."):
        try:
            path = generate_tailored_cv(
                job_id=job_id,
                job_title=job["title"],
                company=job["company"],
                description=job["description"],
                url=job["url"],
                tailor_result=tailor_result,
            )
        except Exception as e:
            console.print(f"[red]Error generando CV:[/red] {e}")
            raise typer.Exit(1)

    console.print(f"\n[bold green]CV personalizado generado:[/bold green] {path}")
    console.print(f"[dim]Optimizado para ATS de {job['company']} — no envíes este CV a otras empresas.[/dim]")


@app.command()
def stats():
    """Muestra estadísticas de tu búsqueda de trabajo."""
    init_db()
    data = get_stats()

    if not data:
        console.print("[yellow]No hay datos aún. Ejecuta 'python main.py scrape' primero.[/yellow]")
        return

    table = Table(title="Estadísticas de búsqueda", border_style="cyan")
    table.add_column("Estado", min_width=12)
    table.add_column("Cantidad", justify="right")
    table.add_column("Barra", min_width=20)

    total = sum(data.values())
    for st in VALID_STATUSES:
        count = data.get(st, 0)
        if count == 0:
            continue
        color = STATUS_COLORS.get(st, "white")
        emoji = STATUS_EMOJI.get(st, "")
        bar_len = int((count / total) * 20) if total > 0 else 0
        bar = "█" * bar_len

        table.add_row(
            f"[{color}]{emoji} {st}[/{color}]",
            f"[{color}]{count}[/{color}]",
            f"[{color}]{bar}[/{color}]",
        )

    table.add_row("[bold]TOTAL[/bold]", f"[bold]{total}[/bold]", "")
    console.print(table)


if __name__ == "__main__":
    app()

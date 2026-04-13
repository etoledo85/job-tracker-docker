# Job Tracker

Automatiza la búsqueda de trabajo: scraping multi-fuente, análisis ATS con IA, generación de cover letters y CVs personalizados por vacante.

## Características

- **Scraping** de 9 bolsas de trabajo: LinkedIn, Himalayas, RemoteOK, We Work Remotely, Remotive, Computrabajo, OCC, GetOnBoard, Hireline
- **Filtros inteligentes**: geográficos, de nivel, de rol y de stack tecnológico para eliminar vacantes irrelevantes antes de guardarlas
- **Análisis ATS** con Claude — score de match, keywords faltantes, gaps críticos y sugerencias de rewording
- **Cover letter personalizada** generada con IA en el idioma de la vacante (ES/EN auto-detectado)
- **CV personalizado por vacante** — aplica rewording ATS sin inventar experiencia
- **Scrape diario automático** via systemd timer con resumen por email
- **CLI completa** con Rich para gestionar el pipeline completo desde la terminal

## Instalación

```bash
git clone https://github.com/etoledo85/job-tracker.git
cd job-tracker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Crea el archivo `.env` con tus credenciales:

```bash
cp .env.example .env
# Edita .env con tu Gmail App Password y opcionalmente tu Anthropic API key
```

Inicializa la base de datos:

```bash
python main.py
```

## Configuración

Edita `config.yaml`:

```yaml
profile:
  name: "Tu Nombre"
  email: "tu@email.com"

search:
  keywords:
    - "sysadmin"
    - "linux administrator"
    # ...
  remote_preference: true
  exclude_locations:
    - "Ciudad de México"
    # ...
  exclude_keywords:
    - "junior"
    - "clearance"
    # ...
```

Las credenciales van en `.env` (nunca en `config.yaml`):

```env
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
ANTHROPIC_API_KEY=sk-ant-...   # opcional, usa Claude Code si no se define
```

## Uso

```bash
# Buscar vacantes en todas las fuentes
python main.py scrape

# Buscar solo en fuentes específicas
python main.py scrape --sources linkedin,himalayas,remoteok

# Ver vacantes guardadas
python main.py list
python main.py list --status new
python main.py list --remote

# Ver detalle de una vacante
python main.py show 42

# Analizar fit CV vs vacante (ATS score)
python main.py tailor 42

# Generar CV personalizado para la vacante
python main.py cv 42

# Generar cover letter
python main.py generate 42

# Generar + enviar cover letter por email
python main.py apply 42

# Cambiar estado de una vacante
python main.py status 42 applied

# Estadísticas del pipeline
python main.py stats
```

### Estados de vacante

| Estado | Descripción |
|---|---|
| `new` | Recién encontrada, sin revisar |
| `reviewing` | En análisis |
| `applied` | Aplicación enviada |
| `interview` | En proceso de entrevistas |
| `offer` | Oferta recibida |
| `rejected` | Rechazada |
| `discarded` | Descartada manualmente |

## Scrape diario automático

Configura el timer de systemd para recibir un email cada mañana con las vacantes nuevas:

```bash
mkdir -p ~/.config/systemd/user
# Copia job-tracker.service y job-tracker.timer a ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now job-tracker.timer

# Verificar
systemctl --user list-timers job-tracker.timer
```

El email incluye título, empresa, ubicación y fuente de cada vacante nueva que pasa los filtros.

## Fuentes de scraping

| Fuente | Método | Estado |
|---|---|---|
| LinkedIn | Playwright | ✅ Activo |
| Himalayas | Playwright | ✅ Activo |
| RemoteOK | Playwright + BS4 | ✅ Activo |
| We Work Remotely | RSS | ✅ Activo |
| Remotive | API pública | ✅ Activo |
| Computrabajo | Playwright + BS4 | ✅ Activo |
| OCC | Playwright + BS4 | ✅ Activo |
| GetOnBoard | API pública | ✅ Activo |
| Hireline | requests + BS4 | ✅ Activo |
| Torre | — | ⚠️ Login requerido |
| Wellfound | — | ⚠️ Anti-bot (DataDome) |
| InfoJobs | — | ⚠️ CAPTCHA |
| Honeypot | — | ❌ Plataforma cerrada (2023) |

## Stack

- **Python 3.11+**
- **Claude** (Anthropic) — análisis ATS, cover letters, CV tailoring
- **Playwright** — scraping de SPAs con JS
- **BeautifulSoup4 + lxml** — parsing HTML
- **SQLite** — base de datos local de vacantes
- **ReportLab** — generación de PDFs
- **Rich + Typer** — CLI interactiva
- **systemd** — automatización del scrape diario

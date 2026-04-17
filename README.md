# Job Tracker

Automatiza tu búsqueda de trabajo: scraping de 14 bolsas de empleo, análisis ATS con IA, cover letters y CVs personalizados por vacante — todo en un contenedor Docker.

## Inicio rápido

### 1. Requisitos

- Docker + Docker Compose
- Una API key gratuita de IA (elige una):
  - **OpenRouter** (recomendado) → https://openrouter.ai
  - **Gemini** → https://aistudio.google.com/app/apikey
  - **Anthropic** → https://console.anthropic.com/settings/keys

### 2. Configuración

```bash
git clone <repo>
cd job-tracker-docker

# Credenciales
cp .env.example .env
# Edita .env con tu API key de IA y opcionalmente Gmail App Password

# Perfil de búsqueda
# Edita config.yaml con tu nombre, email y keywords de búsqueda
```

### 3. Sube tu CV

```bash
mkdir -p data
cp /ruta/a/tu/cv.pdf data/cv.pdf
```

### 4. Levanta el stack

```bash
docker compose up -d web scheduler
```

Abre **http://localhost:8501** en tu browser. Listo.

---

## Uso

### Web UI (recomendado)

Abre http://localhost:8501:

| Tab | Función |
|-----|---------|
| 💼 Vacantes | Ver, filtrar y gestionar vacantes. Cambiar estado. |
| 🔍 Scrape | Lanzar scrape manual de las fuentes que elijas. |
| 🤖 IA | Análisis ATS, generar cover letter y CV personalizado. |
| ⚙️ Config | Subir CV, ver configuración activa. |

### CLI (opcional)

```bash
# Scrape manual
docker compose run --rm job-tracker python main.py scrape

# Ver vacantes
docker compose run --rm job-tracker python main.py list

# Analizar fit CV vs vacante
docker compose run --rm job-tracker python main.py tailor <id>

# Generar cover letter
docker compose run --rm job-tracker python main.py generate <id>

# Ver estadísticas
docker compose run --rm job-tracker python main.py stats
```

---

## Configuración

### `.env`

```env
# IA — elige uno (OpenRouter es gratuito sin tarjeta)
OPENROUTER_API_KEY=sk-or-...
GEMINI_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...

# Email — para recibir resumen diario de vacantes nuevas (opcional)
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

Para Gmail App Password: https://myaccount.google.com/apppasswords

### `config.yaml`

```yaml
profile:
  name: "Tu Nombre"
  email: "tu@email.com"
  phone: "+52 ..."
  cv_path: "data/cv.pdf"

search:
  keywords:
    - "sysadmin"
    - "linux administrator"
    - "devops engineer"
    # agrega los roles que buscas
  locations:
    - "remote"
    - "remoto"
    - "Tu Ciudad"
  remote_preference: true
  exclude_keywords:
    - "junior"
    - "intern"
    # filtra lo que no te interesa
```

---

## Fuentes de scraping

| Fuente | Método | Estado |
|--------|--------|--------|
| Remotive | API pública | ✅ |
| We Work Remotely | RSS | ✅ |
| RemoteOK | Playwright | ✅ |
| Himalayas | API + Playwright | ✅ |
| LinkedIn | Playwright | ✅ |
| Computrabajo | Playwright | ✅ |
| OCC | Playwright | ✅ |
| GetOnBoard | API pública | ✅ |
| Jobicy | API pública | ✅ |
| Glassdoor | Playwright | ✅ |
| Hireline | requests + BS4 | ✅ |
| Torre | — | ⚠️ Login requerido |
| Wellfound | — | ⚠️ Anti-bot |
| InfoJobs | — | ⚠️ CAPTCHA |

---

## Proveedores de IA soportados

El sistema detecta automáticamente qué key tienes configurada (prioridad de izquierda a derecha):

```
GEMINI_API_KEY → OPENROUTER_API_KEY → GROQ_API_KEY → ANTHROPIC_API_KEY
```

OpenRouter tiene modelos gratuitos con fallback automático entre ellos.

---

## Stack

- **Docker + Playwright/Chromium** — scraping de SPAs
- **Python 3.12** — backend
- **SQLite** — base de datos local (persiste en Docker volume)
- **Streamlit** — Web UI
- **ReportLab** — generación de PDFs
- **APScheduler-style scheduler** — scrape diario a las 08:00

---

## Estructura de datos

Las vacantes tienen los siguientes estados:

| Estado | Descripción |
|--------|-------------|
| `new` | Recién encontrada |
| `reviewing` | En análisis |
| `applied` | Aplicación enviada |
| `interview` | En entrevistas |
| `offer` | Oferta recibida |
| `rejected` | Rechazada |
| `discarded` | Descartada |

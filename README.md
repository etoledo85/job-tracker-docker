# Job Tracker

Automatiza tu búsqueda de trabajo: scraping de 14 bolsas de empleo, análisis ATS con IA, cover letters y CVs personalizados por vacante — todo en un contenedor Docker.

## Instalación rápida (script automático)

El script instala Docker, clona el proyecto, te guía por la configuración y levanta todo automáticamente.

**Linux / macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/etoledo85/job-tracker-docker/master/install.sh | bash
```

O si ya tienes el repositorio clonado:
```bash
bash install.sh
```

**Windows** (PowerShell como Administrador):
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\install.ps1
```

> El script detecta tu sistema operativo, instala Docker si no está, y te hace preguntas simples para configurar todo.

---

## Instalación manual (paso a paso)

### Paso 1 — Instala Docker

Si no lo tienes: https://docs.docker.com/get-docker/

Verifica que funcione:

```bash
docker --version
docker compose version
```

---

### Paso 2 — Obtén una API key gratuita de IA

Elige **una** de estas opciones (no necesitas tarjeta de crédito):

| Proveedor | Plan gratuito | Link |
|-----------|--------------|------|
| **Gemini** (recomendado) | 1,500 req/día | https://aistudio.google.com/app/apikey |
| **OpenRouter** | Créditos gratis al registrarse | https://openrouter.ai |

---

### Paso 3 — Clona el repositorio

```bash
git clone https://github.com/etoledo85/job-tracker-docker.git
cd job-tracker-docker
```

---

### Paso 4 — Configura tus credenciales y perfil

**4a. Copia el archivo de entorno y agrega tu API key:**

```bash
cp .env.example .env
```

Abre `.env` y rellena al menos una key:

```env
GEMINI_API_KEY=AIza...          # si usas Gemini
OPENROUTER_API_KEY=sk-or-...    # si usas OpenRouter
```

**4b. Edita `config.yaml` con tu perfil de búsqueda:**

```yaml
profile:
  name: "Tu Nombre"
  email: "tu@email.com"
  phone: "+52 ..."

search:
  keywords:
    - "sysadmin"
    - "devops engineer"
    - "linux administrator"
  locations:
    - "remote"
    - "remoto"
  exclude_keywords:
    - "junior"
    - "intern"
```

**4c. Sube tu CV:**

```bash
cp /ruta/a/tu/cv.pdf data/cv.pdf
```

---

### Paso 5 — Levanta el stack

```bash
docker compose up -d
```

Abre **http://localhost:8501** en tu browser. Listo. 🎉

La primera vez Docker descarga la imagen (~1.5 GB por Playwright/Chromium). Ten paciencia.

---

## Uso

### Web UI

| Tab | Función |
|-----|---------|
| 💼 Vacantes | Ver, filtrar y gestionar vacantes. Cambiar estado. |
| 🔍 Scrape | Lanzar scrape manual de las fuentes que elijas. |
| 🤖 IA | Análisis ATS, generar cover letter y CV personalizado. |
| ⚙️ Config | Subir CV, ver configuración activa. |

El scheduler corre automáticamente todos los días a las 08:00 y llena la DB con nuevas vacantes.

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

## Variables de entorno (`.env`)

```env
# IA — elige al menos una
GEMINI_API_KEY=AIza...
OPENROUTER_API_KEY=sk-or-...
ANTHROPIC_API_KEY=sk-ant-...

# Email — resumen diario de vacantes nuevas (opcional)
# Genera tu App Password en: https://myaccount.google.com/apppasswords
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

El sistema usa la primera key que encuentre en este orden: `GEMINI → OPENROUTER → GROQ → ANTHROPIC`.

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

## Estados de una vacante

| Estado | Descripción |
|--------|-------------|
| `new` | Recién encontrada |
| `reviewing` | En análisis |
| `applied` | Aplicación enviada |
| `interview` | En entrevistas |
| `offer` | Oferta recibida |
| `rejected` | Rechazada |
| `discarded` | Descartada |

---

## Stack

- **Docker + Playwright/Chromium** — scraping de SPAs con JS
- **Python 3.12** — backend
- **SQLite** — base de datos local (persiste en Docker volume)
- **Streamlit** — Web UI
- **ReportLab** — generación de PDFs
- **APScheduler** — scrape diario automático

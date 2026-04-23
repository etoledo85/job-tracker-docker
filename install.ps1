# ─────────────────────────────────────────────────────────────────────────────
#  Job Tracker — Instalación automática (Windows)
#  Ejecutar con: powershell -ExecutionPolicy Bypass -File install.ps1
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"
$REPO_URL = "https://github.com/etoledo85/job-tracker-docker.git"
$INSTALL_DIR = "$env:USERPROFILE\job-tracker"

# ── Helpers de color ──────────────────────────────────────────────────────────
function Write-Step  { param($msg) Write-Host "`n── $msg ──" -ForegroundColor Cyan }
function Write-Ok    { param($msg) Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "⚠  $msg" -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "✗ Error: $msg" -ForegroundColor Red; exit 1 }
function Write-Info  { param($msg) Write-Host "  $msg" }
function Write-Line  { Write-Host "─────────────────────────────────────────" -ForegroundColor Blue }
function Ask-User    { param($prompt) Write-Host "▶ $prompt " -ForegroundColor Cyan -NoNewline; return Read-Host }

# ── Cabecera ──────────────────────────────────────────────────────────────────
Clear-Host
Write-Host ""
Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║       JOB TRACKER — Instalador       ║" -ForegroundColor Cyan
Write-Host "  ║   Automatiza tu búsqueda de empleo   ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Info "  Este script instalará todo lo necesario y"
Write-Info "  configurará el sistema paso a paso."
Write-Host ""
Write-Info "  Tiempo estimado: 10–20 minutos"
Write-Line
Write-Host ""
Ask-User "¿Listo para comenzar? Presiona ENTER para continuar..." | Out-Null

# ── Verificar Windows 10/11 ───────────────────────────────────────────────────
Write-Step "Verificando versión de Windows"
$winVer = [System.Environment]::OSVersion.Version
if ($winVer.Major -lt 10) {
    Write-Err "Necesitas Windows 10 o superior para usar Docker Desktop."
}
Write-Ok "Windows $($winVer.Major).$($winVer.Minor) detectado"

# ── Verificar/habilitar WSL2 ──────────────────────────────────────────────────
Write-Step "Verificando WSL2 (requerido por Docker Desktop)"

$wslFeature = Get-WindowsOptionalFeature -Online -FeatureName "Microsoft-Windows-Subsystem-Linux" -ErrorAction SilentlyContinue
$vmFeature  = Get-WindowsOptionalFeature -Online -FeatureName "VirtualMachinePlatform" -ErrorAction SilentlyContinue

$needsReboot = $false

if ($wslFeature.State -ne "Enabled") {
    Write-Info "Habilitando Subsistema de Windows para Linux (WSL)..."
    dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Out-Null
    $needsReboot = $true
    Write-Ok "WSL habilitado"
} else {
    Write-Ok "WSL ya está habilitado"
}

if ($vmFeature.State -ne "Enabled") {
    Write-Info "Habilitando Plataforma de Máquina Virtual..."
    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Out-Null
    $needsReboot = $true
    Write-Ok "Plataforma Virtual habilitada"
} else {
    Write-Ok "Plataforma Virtual ya está habilitada"
}

if ($needsReboot) {
    Write-Host ""
    Write-Warn "Se habilitaron características que requieren reiniciar Windows."
    Write-Warn "Después de reiniciar, vuelve a ejecutar este script para continuar."
    Write-Host ""
    Ask-User "¿Reiniciar ahora? (s/n) [s]: " | ForEach-Object {
        if ($_ -eq "" -or $_ -match "^[sS]") {
            Restart-Computer -Force
        } else {
            Write-Warn "Reinicia manualmente cuando puedas y vuelve a ejecutar el script."
            exit 0
        }
    }
}

# Configurar WSL2 como versión por defecto
wsl --set-default-version 2 2>$null | Out-Null

# ── Verificar/instalar winget ─────────────────────────────────────────────────
Write-Step "Verificando gestor de paquetes (winget)"
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Info "winget no encontrado. Abriendo Microsoft Store para instalarlo..."
    Start-Process "ms-windows-store://pdp/?productid=9NBLGGH4NNS1"
    Write-Host ""
    Write-Warn "Instala 'Instalador de aplicaciones' desde la Store y presiona ENTER."
    Ask-User "Presiona ENTER cuando hayas instalado winget..." | Out-Null
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Err "winget sigue sin estar disponible. Reinicia la terminal e intenta de nuevo."
    }
}
Write-Ok "winget disponible"

# ── Instalar Git ──────────────────────────────────────────────────────────────
Write-Step "Verificando Git"
if (Get-Command git -ErrorAction SilentlyContinue) {
    Write-Ok "Git ya está instalado ($(git --version))"
} else {
    Write-Info "Instalando Git para Windows..."
    winget install --id Git.Git -e --source winget --silent --accept-package-agreements --accept-source-agreements
    # Recargar PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
    Write-Ok "Git instalado"
}

# ── Instalar Docker Desktop ───────────────────────────────────────────────────
Write-Step "Verificando Docker Desktop"
if (Get-Command docker -ErrorAction SilentlyContinue) {
    try {
        docker info 2>$null | Out-Null
        Write-Ok "Docker Desktop ya está corriendo"
    } catch {
        Write-Warn "Docker está instalado pero no está corriendo."
        Write-Info "Abre Docker Desktop desde el menú de inicio y espera al ícono de la ballena."
        Ask-User "Presiona ENTER cuando Docker Desktop esté corriendo..." | Out-Null
    }
} else {
    Write-Info "Instalando Docker Desktop..."
    Write-Info "Esto puede tardar varios minutos..."
    winget install --id Docker.DockerDesktop -e --source winget --silent --accept-package-agreements --accept-source-agreements

    Write-Host ""
    Write-Warn "Docker Desktop fue instalado. Debes abrirlo manualmente:"
    Write-Info "1. Busca 'Docker Desktop' en el menú de inicio"
    Write-Info "2. Ábrelo y acepta los términos de servicio"
    Write-Info "3. Espera a que el ícono de la ballena aparezca en la barra de tareas"
    Write-Host ""

    # Recargar PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")

    Ask-User "Presiona ENTER cuando Docker Desktop esté corriendo..." | Out-Null

    # Verificar que Docker responda
    $attempts = 0
    while ($attempts -lt 12) {
        try {
            docker info 2>$null | Out-Null
            break
        } catch {
            $attempts++
            Write-Info "Esperando a Docker... ($($attempts * 5)s)"
            Start-Sleep -Seconds 5
        }
    }
    if ($attempts -ge 12) {
        Write-Err "Docker no respondió. Asegúrate de que Docker Desktop esté corriendo e intenta de nuevo."
    }
    Write-Ok "Docker Desktop está corriendo"
}

# ── Clonar el repositorio ─────────────────────────────────────────────────────
Write-Step "Descargando Job Tracker"

if ((Test-Path "docker-compose.yml") -and (Test-Path "config.yaml")) {
    Write-Ok "Ya estás dentro del directorio del proyecto"
    $INSTALL_DIR = (Get-Location).Path
} elseif (Test-Path $INSTALL_DIR) {
    Write-Ok "El directorio $INSTALL_DIR ya existe"
    Set-Location $INSTALL_DIR
} else {
    Write-Info "Clonando repositorio en $INSTALL_DIR ..."
    git clone $REPO_URL $INSTALL_DIR
    Set-Location $INSTALL_DIR
    Write-Ok "Repositorio descargado"
}

# ── Configuración del perfil ──────────────────────────────────────────────────
Write-Step "Configuración de tu perfil"
Write-Host ""
Write-Info "Necesito algunos datos tuyos para personalizar la búsqueda."
Write-Info "Puedes cambiarlos después editando config.yaml"
Write-Host ""

$USER_NAME = ""
while ([string]::IsNullOrWhiteSpace($USER_NAME)) {
    $USER_NAME = Ask-User "Tu nombre completo:"
    if ([string]::IsNullOrWhiteSpace($USER_NAME)) { Write-Warn "El nombre no puede estar vacío." }
}

$USER_EMAIL = ""
while ($USER_EMAIL -notmatch "^[^@]+@[^@]+\.[^@]+$") {
    $USER_EMAIL = Ask-User "Tu email:"
    if ($USER_EMAIL -notmatch "^[^@]+@[^@]+\.[^@]+$") { Write-Warn "Email inválido. Ejemplo: nombre@gmail.com" }
}

$USER_PHONE = Ask-User "Tu teléfono (con código de país, ej: +52 811 123 4567):"
$USER_CITY  = Ask-User "Tu ciudad (ej: Monterrey, Ciudad de México, Buenos Aires):"

# ── Keywords de búsqueda ──────────────────────────────────────────────────────
Write-Step "¿Qué tipo de trabajo buscas?"
Write-Host ""
Write-Info "Escribe los puestos o roles que te interesan."
Write-Info "Ejemplos: 'sysadmin', 'devops engineer', 'desarrollador python'"
Write-Host ""
Write-Info "Ingresa uno por línea. Escribe 'listo' cuando termines."
Write-Host ""

$KEYWORDS = @()
while ($true) {
    $kw = Ask-User "Keyword (o 'listo' para terminar):"
    if ($kw -match "^listo$" -or $kw -match "^LISTO$") { break }
    if (-not [string]::IsNullOrWhiteSpace($kw)) {
        $KEYWORDS += $kw
        Write-Ok "Agregado: $kw"
    }
}

if ($KEYWORDS.Count -eq 0) {
    Write-Warn "No ingresaste keywords. Se usará 'remote work' como predeterminado."
    $KEYWORDS = @("remote work")
}

# ── Preferencia remoto ────────────────────────────────────────────────────────
Write-Host ""
$remoteResp = Ask-User "¿Prefieres trabajo remoto? (s/n) [s]:"
$REMOTE_BOOL = if ($remoteResp -match "^[nN]") { "false" } else { "true" }

# ── Proveedor de IA ───────────────────────────────────────────────────────────
Write-Step "Configuración de Inteligencia Artificial"
Write-Host ""
Write-Info "La IA analiza las vacantes, adapta tu CV y genera cover letters."
Write-Info "Elige tu proveedor (ambos tienen versión gratuita sin tarjeta):"
Write-Host ""
Write-Host "  1) Gemini   — https://aistudio.google.com/app/apikey"
Write-Info "     1,500 solicitudes gratuitas por día. El más recomendado."
Write-Host ""
Write-Host "  2) OpenRouter — https://openrouter.ai"
Write-Info "     Créditos gratuitos al registrarse. Acceso a múltiples modelos."
Write-Host ""

$AI_CHOICE = Ask-User "Elige (1 o 2) [1]:"
if ([string]::IsNullOrWhiteSpace($AI_CHOICE)) { $AI_CHOICE = "1" }

$AI_KEY_VAR   = ""
$AI_KEY_VALUE = ""

if ($AI_CHOICE -eq "2") {
    Write-Host ""
    Write-Info "Pasos para obtener tu API key de OpenRouter:"
    Write-Info "1. Ve a https://openrouter.ai"
    Write-Info "2. Crea una cuenta gratuita"
    Write-Info "3. En 'API Keys', crea una nueva key"
    Write-Host ""
    Start-Process "https://openrouter.ai"
    $AI_KEY_VAR = "OPENROUTER_API_KEY"
} else {
    Write-Host ""
    Write-Info "Pasos para obtener tu API key de Gemini:"
    Write-Info "1. Ve a https://aistudio.google.com/app/apikey"
    Write-Info "2. Inicia sesión con tu cuenta de Google"
    Write-Info "3. Haz clic en 'Create API key'"
    Write-Host ""
    Start-Process "https://aistudio.google.com/app/apikey"
    $AI_KEY_VAR = "GEMINI_API_KEY"
}

while ([string]::IsNullOrWhiteSpace($AI_KEY_VALUE)) {
    $AI_KEY_VALUE = Ask-User "Pega tu API key aquí:"
    if ([string]::IsNullOrWhiteSpace($AI_KEY_VALUE)) { Write-Warn "La API key no puede estar vacía." }
}
Write-Ok "API key guardada"

# ── CV ────────────────────────────────────────────────────────────────────────
Write-Step "Tu Currículum Vitae (CV)"
Write-Host ""
Write-Info "El sistema necesita tu CV en formato PDF."
Write-Info "Escribe la ruta completa. Ejemplo:"
Write-Info "  C:\Users\TuNombre\Documents\mi-cv.pdf"
Write-Host ""
Write-Info "O presiona ENTER para omitir (puedes subirlo desde la Web UI después)."
Write-Host ""

$CV_COPIED = $false
$CV_PATH = Ask-User "Ruta a tu CV (.pdf):"

if (-not [string]::IsNullOrWhiteSpace($CV_PATH)) {
    if (Test-Path $CV_PATH) {
        if (-not (Test-Path "data")) { New-Item -ItemType Directory -Path "data" | Out-Null }
        Copy-Item $CV_PATH "data\cv.pdf" -Force
        Write-Ok "CV copiado correctamente"
        $CV_COPIED = $true
    } else {
        Write-Warn "No encontré el archivo en esa ruta. Podrás subirlo desde la Web UI después."
    }
} else {
    Write-Warn "Sin CV por ahora. Podrás subirlo desde la Web UI en la pestaña ⚙️ Config."
}

# ── Generar archivos de configuración ─────────────────────────────────────────
Write-Step "Creando archivos de configuración"

# .env
$envContent = @"
# Generado por install.ps1 el $(Get-Date -Format "yyyy-MM-dd")

# ── API Key de IA ──────────────────────────────────────────────────────────────
${AI_KEY_VAR}=${AI_KEY_VALUE}

# ── Email (opcional) ──────────────────────────────────────────────────────────
# Para recibir un resumen diario de vacantes nuevas.
# Genera tu App Password en: https://myaccount.google.com/apppasswords
GMAIL_APP_PASSWORD=
"@
$envContent | Set-Content ".env" -Encoding UTF8
Write-Ok ".env creado"

# config.yaml
$keywordsYaml = ($KEYWORDS | ForEach-Object { "    - `"$_`"" }) -join "`n"

$configContent = @"
profile:
  name: "$USER_NAME"
  email: "$USER_EMAIL"
  phone: "$USER_PHONE"
  cv_path: "data/cv.pdf"

search:
  keywords:
$keywordsYaml
  locations:
    - "$USER_CITY"
    - "remote"
    - "remoto"
  remote_preference: $REMOTE_BOOL
  exclude_keywords:
    - "junior"
    - "intern"
    - "practicante"
    - "becario"
    - "security clearance"

email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  sender: "$USER_EMAIL"
  app_password: ""

cover_letter:
  language: "auto"
  tone: "professional"
  max_length: 400
"@
$configContent | Set-Content "config.yaml" -Encoding UTF8
Write-Ok "config.yaml creado"

# ── Construir y levantar contenedores ─────────────────────────────────────────
Write-Step "Construyendo y levantando Job Tracker"
Write-Host ""
Write-Info "Esto puede tardar varios minutos la primera vez."
Write-Info "Se descarga la imagen con Playwright y Chromium (~1.5 GB)."
Write-Host ""

docker compose build --quiet
docker compose up -d web scheduler
Write-Host ""
Write-Ok "Contenedores levantados"

# ── Esperar a que la Web UI esté lista ────────────────────────────────────────
Write-Step "Verificando que la Web UI esté disponible"
Write-Info "Esperando a que el servidor arranque..."

$maxWait = 60
$waited  = 0
$ready   = $false

while ($waited -lt $maxWait) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8501" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 3
    $waited += 3
    Write-Host "  Esperando... ($waited`s)" -NoNewline -ForegroundColor Cyan
    Write-Host "`r" -NoNewline
}
Write-Host ""

if ($ready) {
    Write-Ok "Web UI lista"
} else {
    Write-Warn "El servidor tardó más de lo esperado. Intenta abrir http://localhost:8501 en un momento."
}

# ── Abrir browser ─────────────────────────────────────────────────────────────
Start-Process "http://localhost:8501"

# ── Resumen final ─────────────────────────────────────────────────────────────
Write-Line
Write-Host ""
Write-Host "  ¡Instalación completada exitosamente!" -ForegroundColor Green
Write-Host ""
Write-Host "  Web UI:      " -NoNewline; Write-Host "http://localhost:8501" -ForegroundColor Cyan
Write-Host "  Directorio:  " -NoNewline; Write-Host $INSTALL_DIR -ForegroundColor Cyan
Write-Host ""
if (-not $CV_COPIED) {
    Write-Warn "Pendiente: Sube tu CV desde la Web UI → pestaña ⚙️ Config"
    Write-Host ""
}
Write-Info "Comandos útiles (en PowerShell, dentro del directorio del proyecto):"
Write-Info "  docker compose up -d      # Iniciar"
Write-Info "  docker compose down       # Detener"
Write-Info "  docker compose logs -f    # Ver logs"
Write-Host ""
Write-Line

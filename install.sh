#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  Job Tracker — Instalación automática (Linux / macOS)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_URL="https://github.com/etoledo85/job-tracker-docker.git"
INSTALL_DIR="$HOME/job-tracker"

# ── Colores ───────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
  BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; BLUE=''; CYAN=''; BOLD=''; NC=''
fi

step()  { echo -e "\n${BLUE}${BOLD}── $1 ──${NC}"; }
ok()    { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $1"; }
err()   { echo -e "${RED}✗ Error:${NC} $1"; exit 1; }
ask()   { echo -ne "${CYAN}▶ $1${NC} "; }
info()  { echo -e "  $1"; }
line()  { echo -e "${BLUE}─────────────────────────────────────────${NC}"; }

# ── Cabecera ──────────────────────────────────────────────────────────────────
clear
echo -e "${BOLD}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║       JOB TRACKER — Instalador       ║"
echo "  ║   Automatiza tu búsqueda de empleo   ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"
echo "  Este script instalará todo lo necesario y"
echo "  configurará el sistema paso a paso."
echo ""
echo "  Tiempo estimado: 5–15 minutos"
echo "  (dependiendo de tu conexión a internet)"
line
echo ""
ask "¿Listo para comenzar? Presiona ENTER para continuar..."
read -r

# ── Detectar sistema operativo ────────────────────────────────────────────────
step "Detectando tu sistema operativo"
OS=""
DISTRO=""

if [[ "$OSTYPE" == "darwin"* ]]; then
  OS="macos"
  ok "macOS detectado"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
  OS="linux"
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO="${ID_LIKE:-$ID}"
    ok "Linux detectado: $PRETTY_NAME"
  else
    err "No se pudo identificar tu distribución de Linux."
  fi
else
  err "Sistema operativo no soportado. Usa Linux o macOS."
fi

# ── Verificar permisos ────────────────────────────────────────────────────────
if [[ "$OS" == "linux" ]] && [[ $EUID -ne 0 ]]; then
  # Verificar que sudo esté disponible
  if ! command -v sudo &>/dev/null; then
    err "Este script necesita 'sudo'. Instálalo o ejecuta como root."
  fi
fi

# ── Instalar Git ──────────────────────────────────────────────────────────────
step "Verificando Git"
if command -v git &>/dev/null; then
  ok "Git ya está instalado ($(git --version))"
else
  info "Instalando Git..."
  if [[ "$OS" == "macos" ]]; then
    if command -v brew &>/dev/null; then
      brew install git
    else
      warn "Homebrew no encontrado. Instalando Xcode Command Line Tools..."
      xcode-select --install 2>/dev/null || true
      info "Si se abrió una ventana de instalación, complétala y vuelve a ejecutar este script."
      exit 0
    fi
  elif echo "$DISTRO" | grep -qiE "debian|ubuntu"; then
    sudo apt-get update -qq && sudo apt-get install -y git
  elif echo "$DISTRO" | grep -qiE "fedora|rhel|centos"; then
    sudo dnf install -y git
  elif echo "$DISTRO" | grep -qiE "arch|manjaro"; then
    sudo pacman -Sy --noconfirm git
  else
    err "No sé cómo instalar Git en tu sistema. Instálalo manualmente y vuelve a ejecutar."
  fi
  ok "Git instalado"
fi

# ── Instalar Docker ───────────────────────────────────────────────────────────
step "Verificando Docker"
if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
  ok "Docker ya está instalado ($(docker --version))"
else
  info "Docker no encontrado. Comenzando instalación..."
  echo ""

  if [[ "$OS" == "macos" ]]; then
    echo "  En macOS necesitas instalar Docker Desktop."
    echo ""
    echo "  1. Abriremos la página de descarga en tu navegador"
    echo "  2. Descarga e instala Docker Desktop"
    echo "  3. Ábrelo desde tus Aplicaciones y espera a que el ícono"
    echo "     de la ballena aparezca en la barra superior"
    echo ""
    ask "Presiona ENTER para abrir la página de descarga..."
    read -r
    open "https://www.docker.com/products/docker-desktop/"
    echo ""
    warn "Completa la instalación de Docker Desktop y luego continúa."
    ask "Cuando Docker esté corriendo, presiona ENTER..."
    read -r
    # Verificar que Docker esté corriendo
    until docker info &>/dev/null 2>&1; do
      warn "Docker aún no está listo. Espera unos segundos..."
      sleep 5
    done
    ok "Docker Desktop está corriendo"

  elif [[ "$OS" == "linux" ]]; then
    info "Instalando Docker usando el script oficial de Docker..."
    echo ""
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sudo sh /tmp/get-docker.sh
    rm /tmp/get-docker.sh

    # Agregar el usuario actual al grupo docker
    sudo usermod -aG docker "$USER"
    ok "Docker instalado"
    echo ""
    warn "IMPORTANTE: Se te agregó al grupo 'docker'."
    warn "Los cambios aplican en la próxima sesión. Por ahora usaremos sudo para Docker."
    echo ""

    # Iniciar y habilitar Docker
    sudo systemctl enable docker --now &>/dev/null || true
  fi
fi

# Función helper para ejecutar docker con o sin sudo
docker_cmd() {
  if [[ "$OS" == "linux" ]] && ! groups | grep -q docker; then
    sudo docker "$@"
  else
    docker "$@"
  fi
}

# ── Clonar el repositorio ─────────────────────────────────────────────────────
step "Descargando Job Tracker"

if [ -f "docker-compose.yml" ] && [ -f "config.yaml" ]; then
  ok "Ya estás dentro del directorio del proyecto"
  INSTALL_DIR="$(pwd)"
elif [ -d "$INSTALL_DIR" ]; then
  ok "El directorio $INSTALL_DIR ya existe"
  cd "$INSTALL_DIR"
else
  info "Clonando repositorio en $INSTALL_DIR ..."
  git clone "$REPO_URL" "$INSTALL_DIR"
  cd "$INSTALL_DIR"
  ok "Repositorio descargado"
fi

# ── Configuración del perfil ──────────────────────────────────────────────────
step "Configuración de tu perfil"
echo ""
info "Necesito algunos datos tuyos para personalizar la búsqueda."
info "Puedes cambiarlos después editando config.yaml"
echo ""

ask "Tu nombre completo:"
read -r USER_NAME
while [ -z "$USER_NAME" ]; do
  warn "El nombre no puede estar vacío."
  ask "Tu nombre completo:"
  read -r USER_NAME
done

ask "Tu email:"
read -r USER_EMAIL
while [[ ! "$USER_EMAIL" =~ ^[^@]+@[^@]+\.[^@]+$ ]]; do
  warn "Email inválido. Ejemplo: nombre@gmail.com"
  ask "Tu email:"
  read -r USER_EMAIL
done

ask "Tu teléfono (con código de país, ej: +52 811 123 4567):"
read -r USER_PHONE

ask "Tu ciudad (ej: Monterrey, Ciudad de México, Buenos Aires):"
read -r USER_CITY

# ── Keywords de búsqueda ──────────────────────────────────────────────────────
step "¿Qué tipo de trabajo buscas?"
echo ""
info "Escribe los puestos o roles que te interesan."
info "Ejemplos: 'sysadmin', 'devops engineer', 'desarrollador python'"
echo ""
info "Ingresa uno por línea. Escribe 'listo' cuando termines."
echo ""

KEYWORDS=()
while true; do
  ask "Keyword (o 'listo' para terminar):"
  read -r kw
  if [[ "$kw" == "listo" || "$kw" == "Listo" || "$kw" == "LISTO" ]]; then
    break
  elif [ -n "$kw" ]; then
    KEYWORDS+=("$kw")
    ok "Agregado: $kw"
  fi
done

if [ ${#KEYWORDS[@]} -eq 0 ]; then
  warn "No ingresaste keywords. Se usará 'remote work' como predeterminado."
  KEYWORDS=("remote work")
fi

# ── Preferencia de trabajo remoto ─────────────────────────────────────────────
echo ""
ask "¿Prefieres trabajo remoto? (s/n) [s]:"
read -r REMOTE_PREF
REMOTE_PREF="${REMOTE_PREF:-s}"
if [[ "$REMOTE_PREF" =~ ^[sS] ]]; then
  REMOTE_BOOL="true"
else
  REMOTE_BOOL="false"
fi

# ── Proveedor de IA ───────────────────────────────────────────────────────────
step "Configuración de Inteligencia Artificial"
echo ""
info "La IA analiza las vacantes, adapta tu CV y genera cover letters."
info "Elige tu proveedor (ambos tienen versión gratuita sin tarjeta):"
echo ""
echo "  1) Gemini   — https://aistudio.google.com/app/apikey"
echo "     1,500 solicitudes gratuitas por día. El más recomendado."
echo ""
echo "  2) OpenRouter — https://openrouter.ai"
echo "     Créditos gratuitos al registrarse. Acceso a múltiples modelos."
echo ""

ask "Elige (1 o 2) [1]:"
read -r AI_CHOICE
AI_CHOICE="${AI_CHOICE:-1}"

AI_KEY_VAR=""
AI_KEY_VALUE=""

case "$AI_CHOICE" in
  2)
    echo ""
    info "Pasos para obtener tu API key de OpenRouter:"
    info "1. Ve a https://openrouter.ai"
    info "2. Crea una cuenta gratuita"
    info "3. En 'API Keys', crea una nueva key"
    echo ""
    ask "Pega tu OpenRouter API key aquí:"
    read -r AI_KEY_VALUE
    AI_KEY_VAR="OPENROUTER_API_KEY"
    ;;
  *)
    echo ""
    info "Pasos para obtener tu API key de Gemini:"
    info "1. Ve a https://aistudio.google.com/app/apikey"
    info "2. Inicia sesión con tu cuenta de Google"
    info "3. Haz clic en 'Create API key'"
    echo ""
    ask "Pega tu Gemini API key aquí:"
    read -r AI_KEY_VALUE
    AI_KEY_VAR="GEMINI_API_KEY"
    ;;
esac

while [ -z "$AI_KEY_VALUE" ]; do
  warn "La API key no puede estar vacía."
  ask "Pega tu API key aquí:"
  read -r AI_KEY_VALUE
done
ok "API key guardada"

# ── CV ────────────────────────────────────────────────────────────────────────
step "Tu Currículum Vitae (CV)"
echo ""
info "El sistema necesita tu CV en formato PDF para analizar vacantes"
info "y generar documentos personalizados."
echo ""
info "Escribe la ruta completa a tu CV. Ejemplos:"
info "  /home/usuario/Documentos/mi-cv.pdf"
info "  /Users/nombre/Desktop/cv.pdf"
echo ""
info "O presiona ENTER para omitir (podrás subirlo desde la Web UI después)."
echo ""

CV_COPIED=false
ask "Ruta a tu CV:"
read -r CV_PATH

if [ -n "$CV_PATH" ]; then
  # Expandir ~ si se usa
  CV_PATH="${CV_PATH/#\~/$HOME}"
  if [ -f "$CV_PATH" ]; then
    mkdir -p data
    cp "$CV_PATH" data/cv.pdf
    ok "CV copiado correctamente"
    CV_COPIED=true
  else
    warn "No encontré el archivo en esa ruta. Podrás subirlo desde la Web UI después."
  fi
else
  warn "Sin CV por ahora. Podrás subirlo desde la Web UI en la pestaña ⚙️ Config."
fi

# ── Generar archivos de configuración ─────────────────────────────────────────
step "Creando archivos de configuración"

# Generar .env
cat > .env << EOF
# Generado por install.sh el $(date '+%Y-%m-%d')

# ── API Key de IA ──────────────────────────────────────────────────────────────
${AI_KEY_VAR}=${AI_KEY_VALUE}

# ── Email (opcional) ──────────────────────────────────────────────────────────
# Para recibir un resumen diario de vacantes nuevas.
# Genera tu App Password en: https://myaccount.google.com/apppasswords
GMAIL_APP_PASSWORD=
EOF
ok ".env creado"

# Generar keywords YAML
KEYWORDS_YAML=""
for kw in "${KEYWORDS[@]}"; do
  KEYWORDS_YAML+="    - \"$kw\"\n"
done

# Generar config.yaml
cat > config.yaml << EOF
profile:
  name: "$USER_NAME"
  email: "$USER_EMAIL"
  phone: "$USER_PHONE"
  cv_path: "data/cv.pdf"

search:
  keywords:
$(for kw in "${KEYWORDS[@]}"; do echo "    - \"$kw\""; done)
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
EOF
ok "config.yaml creado"

# ── Construir y levantar contenedores ─────────────────────────────────────────
step "Construyendo y levantando Job Tracker"
echo ""
info "Esto puede tardar varios minutos la primera vez."
info "Se descarga la imagen con Playwright y Chromium (~1.5 GB)."
echo ""

docker_cmd compose build --quiet
docker_cmd compose up -d web scheduler
echo ""
ok "Contenedores levantados"

# ── Verificar que la Web UI esté lista ────────────────────────────────────────
step "Verificando que la Web UI esté disponible"
info "Esperando a que el servidor arranque..."
MAX_WAIT=60
WAITED=0
until curl -sf http://localhost:8501 &>/dev/null; do
  sleep 3
  WAITED=$((WAITED + 3))
  if [ $WAITED -ge $MAX_WAIT ]; then
    warn "El servidor tardó más de lo esperado. Intenta abrir http://localhost:8501 en un momento."
    break
  fi
  echo -ne "  ${CYAN}●${NC} ${WAITED}s...\r"
done
echo ""

# ── Abrir browser ─────────────────────────────────────────────────────────────
URL="http://localhost:8501"
if [[ "$OS" == "macos" ]]; then
  open "$URL" 2>/dev/null || true
elif command -v xdg-open &>/dev/null; then
  xdg-open "$URL" 2>/dev/null || true
fi

# ── Resumen final ─────────────────────────────────────────────────────────────
line
echo ""
echo -e "${GREEN}${BOLD}  ¡Instalación completada exitosamente!${NC}"
echo ""
echo "  Web UI:      ${CYAN}http://localhost:8501${NC}"
echo "  Directorio:  ${CYAN}$INSTALL_DIR${NC}"
echo ""
if ! $CV_COPIED; then
  echo -e "  ${YELLOW}Pendiente:${NC} Sube tu CV desde la Web UI → pestaña ⚙️ Config"
  echo ""
fi
echo "  Comandos útiles:"
echo "    docker compose up -d      # Iniciar"
echo "    docker compose down       # Detener"
echo "    docker compose logs -f    # Ver logs"
echo ""
line

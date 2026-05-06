#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE="$SCRIPT_DIR/.gallery.env"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is not installed or not in PATH."
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  cat > "$ENV_FILE" <<'EOF'
export GALLERY_USERNAME='your_username'
export GALLERY_PASSWORD='your_password'
export GALLERY_PATH='/absolute/path/to/your/gallery'
export GALLERY_PORT='8080'
EOF

  echo "Created $ENV_FILE with placeholder values."

  echo "Update $ENV_FILE with real values, then run ./start_server.sh again."
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating virtual environment in $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

if [[ ! -f "$REQUIREMENTS_FILE" ]]; then
  echo "Error: requirements.txt not found in $SCRIPT_DIR."
  exit 1
fi

if ! python -c "import PIL" >/dev/null 2>&1; then
  echo "Installing Python dependencies from requirements.txt..."
  python -m pip install --upgrade pip
  python -m pip install -r "$REQUIREMENTS_FILE"
fi

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

# Central runtime config for server.py.
# You can override these with environment variables before running the script.
DEFAULT_GALLERY_PATH="/absolute/path/to/my/gallery"
DEFAULT_GALLERY_PORT="8080"

# Accept credentials and runtime config via env vars or positional args.
# Positional args are useful for quick local runs:
#   ./start_server.sh myuser mypassword /absolute/path/to/gallery 8080
if [[ -z "${GALLERY_USERNAME:-}" && "${1:-}" != "" ]]; then
  export GALLERY_USERNAME="$1"
fi

if [[ -z "${GALLERY_PASSWORD:-}" && "${2:-}" != "" ]]; then
  export GALLERY_PASSWORD="$2"
fi

if [[ -z "${GALLERY_PATH:-}" && "${3:-}" != "" ]]; then
  export GALLERY_PATH="$3"
fi

if [[ -z "${GALLERY_PORT:-}" && "${4:-}" != "" ]]; then
  export GALLERY_PORT="$4"
fi

export GALLERY_PATH="${GALLERY_PATH:-$DEFAULT_GALLERY_PATH}"
export GALLERY_PORT="${GALLERY_PORT:-$DEFAULT_GALLERY_PORT}"

if [[ -z "${GALLERY_USERNAME:-}" || -z "${GALLERY_PASSWORD:-}" ]]; then
  cat <<'EOF'
Error: Missing required credentials.
Set these env vars before starting:
  export GALLERY_USERNAME='your_username'
  export GALLERY_PASSWORD='your_password'
  export GALLERY_PATH='/absolute/path/to/gallery'
  export GALLERY_PORT='8080'

Or pass them as args:
  ./start_server.sh your_username your_password /absolute/path/to/gallery 8080
EOF
  exit 1
fi

if [[ "$GALLERY_PATH" == "/absolute/path/to/my/gallery" ]]; then
  cat <<'EOF'
Error: GALLERY_PATH is still the placeholder value.
Set a real absolute path in start_server.sh or export GALLERY_PATH before running.
EOF
  exit 1
fi

if [[ "$GALLERY_PATH" != /* ]]; then
  echo "Error: GALLERY_PATH must be an absolute path."
  exit 1
fi

if [[ ! "$GALLERY_PORT" =~ ^[0-9]+$ ]]; then
  echo "Error: GALLERY_PORT must be a numeric value."
  exit 1
fi

exec python server.py

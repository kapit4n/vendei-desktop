#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if ! python -c "import PySide6, sqlalchemy, pydantic" >/dev/null 2>&1; then
  pip install -r requirements.txt
fi

if [[ -z "${QT_QPA_PLATFORM:-}" ]]; then
  # If no display is available, fall back to offscreen (useful for SSH / CI).
  if [[ "${FORCE_OFFSCREEN:-0}" == "1" ]]; then
    export QT_QPA_PLATFORM=offscreen
  elif [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
    if [[ -z "${DISPLAY:-}" ]]; then
      export QT_QPA_PLATFORM=offscreen
    elif command -v xdpyinfo >/dev/null 2>&1; then
      # DISPLAY is set, but may be unusable in containers/sandboxes.
      if ! xdpyinfo >/dev/null 2>&1; then
        export QT_QPA_PLATFORM=offscreen
      fi
    fi
  fi
fi

exec python -m vendei_desktop

#!/usr/bin/env bash
set +e
set -o pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_DIR" || exit 1

echo "=================================================="
echo "SemantiK Architect WSL shell"
echo "PWD=$(pwd)"
echo "WSL=$(uname -a)"
echo "=================================================="

if [[ ! -f "manage.py" ]]; then
  echo "ERROR: manage.py not found in repo root: $(pwd)"
  exec bash -li
fi

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PYTHONDONTWRITEBYTECODE=1

VENV=""
if [[ -f ".venv/bin/activate" ]]; then
  VENV=".venv"
elif [[ -f "venv/bin/activate" ]]; then
  VENV="venv"
fi

if [[ -z "$VENV" ]]; then
  echo ""
  echo "[bootstrap] No virtual environment found."

  if command -v uv >/dev/null 2>&1; then
    echo "[bootstrap] Creating .venv with uv"
    uv venv .venv || {
      echo "ERROR: uv venv failed."
      exec bash -li
    }
    VENV=".venv"
  elif command -v python3 >/dev/null 2>&1; then
    echo "[bootstrap] uv not found; falling back to python3 -m venv .venv"
    python3 -m venv .venv || {
      echo "ERROR: python3 -m venv failed."
      exec bash -li
    }
    VENV=".venv"
  else
    echo "ERROR: neither uv nor python3 is available in WSL."
    exec bash -li
  fi
fi

# shellcheck disable=SC1090
source "${VENV}/bin/activate"

echo ""
echo "VENV_OK=${VIRTUAL_ENV}"
echo "PY=$(command -v python)"
python -V 2>/dev/null || true

if command -v uv >/dev/null 2>&1; then
  echo "UV=$(uv --version)"
else
  echo "UV=missing"
fi

echo ""
echo "[check] Python packages"
python -c 'import importlib.util as u; mods=("pgf","fastapi","arq"); missing=[m for m in mods if u.find_spec(m) is None]; print("CHECK_OK" if not missing else "MISSING=" + ",".join(missing))' 2>/dev/null
PKG_RC=$?

echo ""
echo "[check] GF runtime"
python -c 'import pgf; print("PGF_IMPORT_OK")' 2>/dev/null || echo "PGF_IMPORT_FAIL"

echo ""
echo "[check] backend stack"
python -c 'import fastapi, arq; print("BACKEND_IMPORT_OK")' 2>/dev/null || echo "BACKEND_IMPORT_FAIL"

if [[ $PKG_RC -ne 0 ]]; then
  echo ""
  echo "Suggested install:"
  echo "  uv pip install -e \".[api,dev,gf]\""
fi

echo ""
echo "Useful commands:"
echo "  python manage.py doctor"
echo "  python manage.py start"
echo "  python manage.py start-api"
echo "  python manage.py start-worker"
echo "  python manage.py build --langs en fr"
echo ""

exec bash -li
#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ENV_FILE="${PROJECT_ROOT}/config/app.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Env file not found: ${ENV_FILE}" >&2
  echo "Create it by copying config/app.env.example to config/app.env" >&2
  exit 1
fi

# Export variables from env file for the Python process
set -a
# shellcheck disable=SC1090
# Strip CRLF in case the file was edited/copied from Windows.
source <(sed 's/\r$//' "${ENV_FILE}")
set +a

PYTHON_BIN="python3"
if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
  PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
fi

LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "${LOG_DIR}"

cd "${PROJECT_ROOT}"
exec "${PYTHON_BIN}" -m msa3_flytime.main

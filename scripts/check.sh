#!/usr/bin/env sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
backend_root="$repository_root/backend"

if [ -x "$backend_root/.venv/bin/python" ]; then
    python_command="$backend_root/.venv/bin/python"
elif [ -x "$backend_root/.venv/Scripts/python.exe" ]; then
    python_command="$backend_root/.venv/Scripts/python.exe"
else
    python_command="python"
fi

cd "$backend_root"
"$python_command" -m pytest -m unit
"$python_command" -m ruff check .
"$python_command" -m compileall src

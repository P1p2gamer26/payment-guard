#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
.venv/Scripts/python -m pytest -q
echo OK

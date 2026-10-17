#!/usr/bin/env bash
# Uso en una consola Bash de PythonAnywhere:  bash ~/payment-guard/deploy/pythonanywhere.sh
set -e
cd ~/payment-guard && git pull -q
rm -rf ~/.cache/pip /tmp/pip-* 2>/dev/null || true
[ -d .venv ] || python3.13 -m venv --system-site-packages .venv
.venv/bin/pip install -q --no-cache-dir 'django==5.2.*' whitenoise
export DEBUG=0 DECISION_MODE=replay
.venv/bin/python manage.py migrate -v0
.venv/bin/python manage.py collectstatic --noinput -v0
.venv/bin/python manage.py shell -c "from guard.services import *; from guard.data import load_policy; from guard.models import DecisionRecord; DecisionRecord.objects.exists() or process_all(current_policy())"
touch /var/www/${USER,,}_pythonanywhere_com_wsgi.py 2>/dev/null || true
du -sh ~ ; echo "OK: recarga la web app en la pestaña Web"

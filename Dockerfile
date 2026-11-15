FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    DJANGO_DB_PATH=/data/db.sqlite3

WORKDIR /app

# Abhängigkeiten zuerst, damit die Schicht bei Codeänderungen im Cache bleibt
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# collectstatic braucht einen Schlüssel, der nur zur Buildzeit existiert und nirgends bleibt
RUN DJANGO_SECRET_KEY=nur-fuer-den-build python manage.py collectstatic --noinput \
    && useradd --system --create-home app \
    && mkdir /data && chown app:app /data

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Kein USER: der Entrypoint gibt Root nur im Home-Assistant-Add-on nicht ab (dort gehört /data root)
VOLUME /data
EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn zeiterfassung.wsgi:application --bind 0.0.0.0:8000 --workers 2 --access-logfile -"]

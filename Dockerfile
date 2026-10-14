FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY server.py .
COPY index.html .
COPY static/ ./static/

# N3: Datenverzeichnis + Non-root-User. Der Prozess läuft NICHT als root.
RUN mkdir -p /data \
    && useradd --system --uid 10001 --home-dir /app app \
    && chown -R app:app /app /data

ENV DATA_DIR=/data

USER app

EXPOSE 5000

# N3: HEALTHCHECK auf /api/stats (Python statt curl — kein Extra-Paket nötig).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/api/stats',timeout=5).status==200 else 1)"

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "server:app"]

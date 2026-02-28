FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        cron \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

ENV RQALPHA_IMAGE_BUNDLE_PATH=/opt/rqalpha/bundle
RUN mkdir -p /opt/rqalpha/bundle

COPY . /app
RUN mkdir -p /app/.gunicorn \
    && chmod +x /app/docker-entrypoint.sh

EXPOSE 54321
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn.docker.py", "wsgi:app"]

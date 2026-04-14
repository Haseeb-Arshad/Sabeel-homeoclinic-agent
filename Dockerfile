FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends --no-install-recommends \
        gcc \
        libffi-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && useradd --create-home --shell /bin/bash appuser

COPY --chown=appuser:appuser requirements.txt .
USER appuser

RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=appuser:appuser . .

RUN mkdir -p /app/static && chmod 755 /app/static

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

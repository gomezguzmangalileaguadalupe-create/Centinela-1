FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GRADIO_ANALYTICS_ENABLED=False \
    HF_HUB_DISABLE_TELEMETRY=1 \
    PORT=10000

WORKDIR /app

# Paquetes del sistema para audio, voz sintética y bibliotecas numéricas.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libespeak-ng1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 10000
CMD ["python", "app.py"]

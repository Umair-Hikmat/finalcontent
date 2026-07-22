FROM python:3.11-slim

# System deps: ffmpeg for MoviePy, fonts, build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fontconfig \
    libsm6 \
    libxext6 \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Writable dirs for Cloud Run (ephemeral filesystem is fine, /tmp is guaranteed writable)
RUN mkdir -p /app/data/projects /app/data/exports /app/assets/fonts /app/assets/audio/music /app/assets/audio/sfx \
    && chmod -R 777 /app/data /app/assets

ENV PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_CORS=false \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    PORT=8080

EXPOSE 8080

CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0"]

FROM python:3.11-slim

# Instalăm dependențele de sistem necesare pentru Prophet
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalăm toate librăriile necesare
RUN pip install --no-cache-dir \
    paho-mqtt \
    pandas \
    prophet \
    influxdb-client

# Copiem scripturile
COPY sonoff.py .
COPY forecast_service.py .

# Nu punem CMD aici, îl definim în docker-compose pentru fiecare serviciu
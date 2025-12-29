# Folosim o imagine de Python
FROM python:3.9-slim

# Instalăm unelte necesare pentru compilarea librăriilor de AI
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Setăm folderul de lucru în container
WORKDIR /app

# Copiem lista de dependințe și le instalăm
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiem restul codului din folderul local 'edge' în container
COPY . .

# Comanda care pornește scriptul tău de AI
CMD ["python", "forecast_service.py"]
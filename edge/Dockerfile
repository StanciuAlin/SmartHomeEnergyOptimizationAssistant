# Use a lightweight Python 11 image to keep the container size small
FROM python:3.11-slim

# Install system dependencies required for Prophet
# 'build-essential' is necessary because Prophet (and its dependency cmdstanpy) 
# requires a C++ compiler to compile the mathematical models.
# We clean up the apt lists afterwards to reduce image size.
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Install Python libraries
# --no-cache-dir: prevents pip from saving downloaded packages, keeping the image light.
# paho-mqtt: for MQTT communication (if needed)
# pandas: for data manipulation and time-series handling
# prophet: the core AI forecasting library
# influxdb-client: for reading/writing data to the InfluxDB container
RUN pip install --no-cache-dir \
    paho-mqtt \
    pandas \
    prophet \
    influxdb-client

# Copy the local Python script into the container's /app directory
COPY forecast_service.py .

# NOTE: No CMD instruction is used here because the startup command 
# is defined in the 'docker-compose.yml' file for better flexibility.
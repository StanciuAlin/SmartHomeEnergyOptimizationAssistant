# 🏠 Smart Home Energy Optimization Assistant

The project is an advanced IoT ecosystem designed for monitoring, simulating and forecasting energy consumption in a smart home. The system integrates **Sonoff POW** device emulators, an **MQTT** message broker, real-time data storage (**InfluxDB**) and artificial intelligence modules for forecasting (**Facebook Prophet**).

## System Architecture

The system is fully containerized using Docker and includes the following services defined in `docker-compose.yml`:

* **Edge Simulator (`sonoff_simulator`):** Emulates 10 `Sonoff POW R2` devices that transmit telemetry (power, voltage) via `MQTT`.
* **MQTT Broker (`mosquitto`):** Manages communication between sensors and the rest of the system using the `MQTT` protocol on port `1883`.
* **Database (`influxdb`):** Stores consumption data in a format optimized for time series (`InfluxDB v2.7`).
* **Forecast Service (`edge_forecast`):** A Python service that uses the _Prophet_ model to predict energy consumption over the next `6 hours`.
* **Logic Engine (`nodered_logic`):** Manages data flows and automation logic through _Node-RED_.
* **Visualization (`grafana`):** Dashboard for monitoring real-time data and predictions.

## 📂 Project Structure

```plaintext
Smart-Home-Energy/
├── edge/
│ ├── sonoff.py # Python script simulating Sonoff sockets (MQTT Client)
│ ├── forecast_service.py # Forecast service based on the Prophet model
│ └── requirements.txt # Required libraries (pandas, prophet, influxdb-client)
├── docker-compose.yml # Configuring the entire ecosystem using containers
├── mosquitto/
│ └── config/
│ └── mosquitto.conf # Configuring the MQTT broker
└── nodered/ # Business logic and dashboard (accessible on port 1880)
```

## 🛠️ Installation and Running

### 1. Prerequisites
Make sure you have installed:
* **Docker & Docker Compose:** To run the entire infrastructure as containers.
* **Python 3.11+:** Used inside containers for emulator and forecast service.

### 2. Launch the system
From the project root directory, run:
```bash
docker-compose up -d
```
_This command automatically starts Mosquitto (port 1883), InfluxDB (port 8086), Node-RED (port 1880), and Grafana (port 3000)._

### 3. Start the Sonoff Simulator
The simulator (`sonoff.py`) is automatically started by _Docker_. It publishes data about _power_ and _voltage_ on topics like `tele/sonoff_pow_XX/SENSOR`.

### 4. Run the AI ​​Module (Forecast)
The forecast service (`forecast_service.py`) is automatically run in the container.
The script takes historical data from _InfluxDB_ and generates predictions for the next `6 hours`.

### 5. Accessing the interfaces
* **Node-RED** to view data streams: `http://localhost:1880`
* **Grafana** for advanced dashboards: `http://localhost:3000`
  * _User_: `admin`
  * _Password_: `smartappliance`
* **InfluxDB UI** for real-time data storage: `http://localhost:8086`

## Configure Credentials (Default)
* **InfluxDB Org:** `ucv`
* **Bucket:** `energy_data`
* **Admin Token:** `201dcc33-81e8-4d1d-94c0-a9a00ddafcab`
* **MQTT Broker:** `mosquitto:1883`

## Technical Details
### Sonoff Simulation
Each emulated device sends data every `15 seconds`:
1. **Telemetry Topic:** `tele/sonoff_pow_XX/SENSOR`
2. **Simulated data:** Voltage (`228V` - `235V`) and Power (`0W` - `500W`).
3. **Auto-discovery:** Sends `MQTT Discovery` configurations to be automatically recognized by platforms like Home Assistant.

### Forecast Service (AI)
The forecast module runs periodically and performs the following steps:
1. Extracts the last `24 hours` of data from the `energy_data` bucket.
2. Trains the _Prophet_ model on the power data.
3. Generates predictions (`yhat`, `upper/lower bounds`) for the next `6 hours`.
4. Saves the results back to _InfluxDB_ in the `energy_forecast` measurement.

### Optimization outcomes
The `400W` threshold warning module is implemented at the `Node-RED` logic level. <br>
#### ⚡ Technical Details
* _Data Source_: The _Node-RED_ logic receives real-time messages via the `MQTT` protocol from the _Sonoff_ socket emulator. These messages are sent to the `tele/sonoff_pow_XX/SENSOR` topic and contain the `ENERGY.Power` field.
* _Trigger Threshold_: In _Node-RED_, there is a `Function` node that evaluates the numerical value of the power (`msg.payload.ENERGY.Power`).

* _Warning Logic_:
  * If the reported power is above `400W`, the flow routes the message to a notification node (for example, a visual element in the Dashboard or an audible alert).
  * Since the emulator generates random values ​​between `0.0W` and `500.0W`, the alert will be triggered frequently during the simulation to test the system's reaction.

#### 🛠️ Implementation in the Node-RED Flow

Within the _Node-RED_ interface (accessible at `http://localhost:1880`), this module is composed of:
1. _MQTT In Node_ listens to data from sockets.
2. _JSON Parser_ transforms the received text into a formatted object to extract the power value.
3. _Function Node_ checks the condition `payload.ENERGY.Power > 400`.
4. _UI Control_ sends a visual alert to the _Grafana_ and _Node-RED_ dashboard, warning the user that an appliance is consuming too much.

This functionality is part of the `Logic Engine` described in the project architecture, with the role of protecting the network or informing the user about high consumption in real time.

## 🧠 Algorithms Used
* **Prophet**: Used to capture seasonality in energy consumption and generate predictions based on the `24-hour` history.
* **Logic Engine**: Implemented in _Node-RED_ to process `MQTT` messages and store them in _InfluxDB_.

## 📊 Dashboard and Results
The system provides the following information:
* **Instantaneous consumption (W):** collected from the `10 emulated sockets`.
* **Comparative graph:** Current consumption data compared to the predicted values ​​(`predicted_value`).
* **Status monitoring:** The `online/offline` status of each device via `LWT`.


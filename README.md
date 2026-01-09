# 🏠 Smart Home Energy Optimization Assistant

The project is an advanced IoT ecosystem designed for monitoring, simulating and forecasting energy consumption in a smart home. The system integrates **Sonoff POW** device emulators, an **MQTT** message broker, real-time data storage (**InfluxDB**) and artificial intelligence modules for forecasting (**Facebook Prophet**).

## System Architecture

The system is fully containerized using Docker and includes the following services defined in `docker-compose.yml`:

- **Hardware Simulator (Wokwi):** Runs a MicroPython script on an ESP32 that simulates real consumption for 7 `Sonoff POW R2` devices with 2 of them controlled through potentiometers and transmits telemetry (power, voltage) via `MQTT`.
- **MQTT Broker (HiveMQ Cloud):** Manages secure (TLS) communication between sensors and the rest of the infrastructure.
- **Logic Engine (Node-RED):** Retrieves MQTT data, formats it for the database, and executes predictive protection commands (Edge AI).
- **Database (InfluxDB v2.7):** Stores consumption history and AI forecast results.
- **Forecasting Service (Edge AI):** A Python service using the Prophet model to predict energy consumption for the next 6 hours.
- **Visualization (Grafana):** An interactive control panel for monitoring data and manually controlling the appliances.

## 📂 Project Structure

```plaintext
Smart-Home-Energy/
├── edge/
│   ├── forecast_service.py   # Forecast service based on the Prophet model
│   ├── Dockerfile            # Python environment setup (with build-essential for Prophet)
│   └── requirements.txt      # Dependencies: pandas, prophet, influxdb-client
├── node_RED/
│   ├── flows.json            # MQTT processing logic and Edge AI control
├── wowki/
│   ├── main.py               # MicroPython code for ESP32 simulation
│   └── diagram.json          # Hardware connection schema in Wokwi
├── grafana/
│   └── Dashboard_JSON.json   # Grafana dashboard configuration
└── docker-compose.yml        # Orchestration of the entire ecosystem
```

## 🛠️ Installation and Running

### Prerequisites

Make sure you have installed:

- **Docker & Docker Compose:** To run the entire infrastructure as containers.
- **HiveMQ Cloud Account** (for the MQTT broker).
- **Python 3.11+:** Used inside containers for emulator and forecast service.

### Launch the system

### 1. Start the Backend Infrastructure (Docker)
From the project root directory, run:

```bash
docker-compose up -d
```

_This will automatically start InfluxDB, Node-RED, Grafana, and the Forecasting Service and will initialize the network and volumes for data persistence._

### 2. Launch the Hardware Simulator (Wokwi)

Once the infrastructure is active, start the data source:
* Open the Wokwi project link in your browser.
* Ensure the MQTT credentials in `main.py` match your **HiveMQ Cloud** details.
* Click the **Start Simulation** button. You should see the telemetry table appearing in the Wokwi console.

### 3. Configure Node-RED (Logic Engine)

* Access the interface at http://localhost:1880.
* Click the **Menu** (top right) -> **Import**.
* Select the `flows.json` file from the `node_RED/` folder.
* Click **Deploy**. Node-RED will now start processing MQTT messages and saving them to InfluxDB.

### 4. Connect to InfluxDB (Database)

* Access the UI at http://localhost:8086.
* Log in with the credentials: `admin` / `smartappliance`.
* Check the **Data Explorer** to ensure that buckets are created and telemetry is arriving in the `energy_usage` measurement.
* Note: The **Admin Token** is pre-configured to `201dcc33-81e8-4d1d-94c0-a9a00ddafcab`.

### 5. Configure Grafana (Visualization)

* Access Grafana at http://localhost:3000.
* Log in with admin / smartappliance.
* Import the Dashboard:
  * Go to **Dashboards** -> **New** -> **Import**.
  * Upload the `Dashboard Smart Home.json` file from the `grafana/` folder.
* **Select Data Source:** Ensure the dashboard is connected to your InfluxDB instance using the Flux query language.

## ⚡ Technical Details

### Sonoff Simulation

Each emulated device sends data every `5 seconds`:

1. **Telemetry Topic:** `tele/sonoff_pow_XX/SENSOR`
2. **Simulated data:** Voltage (`228V` - `235V`) and Power (`0W` - `500W`).
3. **Auto-discovery:** Sends MQTT Discovery configurations to be automatically recognized by platforms like Home Assistant.

### Forecasting Service (AI)

The forecast module runs periodically and performs the following steps:

1. Extracts the last **24 hours** of data from InfluxDB for each plug (`sonoff_pow_01`, `02`).
2. Trains the _Prophet_ model on the power data.
3. Generates predictions (`yhat`, `upper/lower bounds`) for the next **6 hours**.
4. Saves the results back to InfluxDB in the `energy_forecast` measurement.

### Optimization outcomes: Edge AI Control Logic (Node-RED)

The system includes an automated protection module:

* **Trigger Threshold:** `400W`.
* **Action:** Node-RED automatically sends an `OFF` command to the respective plug via MQTT to prevent overload. 

### Implementation in the Node-RED Flow

Within the **Node-RED** interface (accessible at `http://localhost:1880`), the system logic has been upgraded to a proactive Edge **AI Master Controller**:

**1. Telemetry Processing (Flow 1)**:

* **MQTT In Node:** Listens for real-time telemetry from all devices via `tele/+/SENSOR`.
* **Function Node (`GetEnergyUsage`):** Parses incoming data, extracts power values, and maps them to specific device IDs.
* **InfluxDB Out Node:** Stores formatted data into the `energy_usage` measurement for historical analysis and AI training.

**2. Predictive Control (Flow 2):**
* **InfluxDB In Node:** Periodically queries the latest AI predictions from the `energy_forecast` measurement.
* **Edge AI Function Node (`CheckAbove400W`):** Processes the forecast array. If the AI predicts that a specific device (e.g., `sonoff_pow_01`) will exceed **400W** in the next 6 hours, it triggers a preventive action.
* **MQTT Out Node:** Automatically sends an `OFF` command to the physical or emulated device before the overload occurs.
* **Alert Logging:** Simultaneously writes an `alert_active: 1` status to the `system_alerts` measurement in InfluxDB to notify the Grafana dashboard.

**3. Manual Overrides:**
* **HTTP In Nodes:** Accept `ON/OFF` requests from the Grafana dashboard's HTML buttons, allowing users to override the AI and control appliances manually via MQTT.

This **Logic Engine** acts as the central nervous system of the project, shifting from simple monitoring to autonomous grid protection using real-time predictive data.

## 🧠 Algorithms & Intelligence
* **Prophet (Meta):** Utilized by the `forecast_service` to perform time-series analysis on a per-device basis. It captures consumption patterns over a **24-hour history** to generate a **6-hour forecast**, including `upper` and `lower` confidence bounds.
* **Edge AI Logic:** Implemented within Node-RED to handle **Multi-Device Decision Making**. Unlike standard threshold alerts, this algorithm evaluates future-dated timestamps to mitigate risks before they manifest in the physical system.
* **Data Pipelining:** Uses **Flux (InfluxDB)** to aggregate, window, and pivot raw power data, ensuring the AI models receive clean, high-density information for training.

## 📊 Dashboard and Results

The Grafana interface provides:
* **Instantaneous Consumption:** Displayed via Gauge indicators.
* **AI Confidence Band:** Time Series graphs showing predicted values and the error margin (upper/lower bound).
* **Manual Control:** Interactive ON/OFF buttons that send HTTP commands to Node-RED, which are then converted into MQTT messages.
* **Alerts:** History of forced shut-off events generated by the AI.

## 🌟 Conclusion: The Future of Smart Energy Management
**Smart Home Energy Optimization Assistant** demonstrates the power of integrating **IoT, Edge Computing, and Artificial Intelligence** to transform a standard home into an intelligent, self-optimizing ecosystem. By moving beyond simple manual control and into the realm of **Predictive Analytics**, we achieve a system that doesn't just react to overconsumption but actively prevents it.

This "Optimization Assistant" is more than a technical showcase; it is a scalable foundation for a greener, smarter, and more responsive future in home automation.

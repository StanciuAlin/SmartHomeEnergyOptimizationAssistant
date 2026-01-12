"""
Project link https://wokwi.com/projects/451675699383008257
"""

import network
import time
from machine import Pin, ADC
import ujson
from umqtt.robust import MQTTClient
import ussl
import random

# --- MQTT Broker Configuration ---
# Using HiveMQ Cloud with SSL/TLS encryption on port 8883
MQTT_BROKER = "e1b9d425046b46d89b87f93fd80187c8.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "sefrem"
MQTT_PASSWORD = "Sefrem2021"

# --- Device State Management ---
# Global dictionary to track if each plug is logically ON or OFF.
# If OFF, power reporting will be forced to 0.0W.
device_states = {
    "sonoff_pow_01": True, "sonoff_pow_02": True, "sonoff_pow_03": True,
    "sonoff_pow_04": True, "sonoff_pow_05": True, "sonoff_pow_06": True, "sonoff_pow_07": True
}

# --- MQTT Callback Function ---
# This function triggers whenever a message is received on a subscribed topic


def mqtt_callback(topic, msg):
    # Decode incoming bytes to strings
    t = topic.decode().split('/')
    m = msg.decode().upper()

    # Expected topic format: cmnd/device_id/POWER
    if len(t) >= 2:
        d_id = t[1]
        if d_id in device_states:
            new_state_bool = (m == "ON")

            # FILTER: Only act if the received state is different from the current local state.
            # This prevents infinite loops or repetitive logging from retained MQTT messages.
            if device_states[d_id] == new_state_bool:
                return

            # Update local state
            old_state = "ON" if device_states[d_id] else "OFF"
            device_states[d_id] = new_state_bool

            # Print an aesthetic notification banner for the state change
            # Total width is 46 characters (2 for borders '|', 44 for content)
            print("\n" + "="*46)

            # {:^44} centers the title in the 44-character space
            print("|{:^47}|".format("🔔  Change Appliance State"))
            print("|" + "-"*44 + "|")

            # {:<34} aligns text to the left and pads with spaces to fill exactly the remaining space
            print("| Source:     {:<30} |".format("MQTT External Command"))
            print("| Device:     {:<30} |".format(d_id))

            # The transition uses specific widths for old and new states to keep the border fixed
            transition_str = "{:<3} -> {:<23}".format(old_state, m)
            print("| Transition: {:<23} |".format(transition_str))

            print("="*46 + "\n")

# --- Helper: Time Formatting ---


def format_time():
    t = time.localtime()
    return "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])


# --- Device Lists ---
# Physical inputs on ESP32 (Potentiometers)
HARDWARE_DEVICES = [
    {"id": "sonoff_pow_01", "pin": 34},
    {"id": "sonoff_pow_02", "pin": 35}
]

# Fully virtual devices using random data generation
SIMULATED_DEVICES = ["sonoff_pow_03", "sonoff_pow_04",
                     "sonoff_pow_05", "sonoff_pow_06", "sonoff_pow_07"]
ALL_IDS = ["sonoff_pow_01", "sonoff_pow_02", "sonoff_pow_03",
           "sonoff_pow_04", "sonoff_pow_05", "sonoff_pow_06", "sonoff_pow_07"]

# --- Analog Sensors Setup ---
# Initialize ADC (Analog to Digital Converter) for power simulation via knobs
pot1 = ADC(Pin(34))
pot1.atten(ADC.ATTN_11DB)  # Full range (0-3.3V)
pot2 = ADC(Pin(35))
pot2.atten(ADC.ATTN_11DB)

# --- Network & MQTT Initialization ---
print("Connecting to WiFi........ ", end="")
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
sta_if.connect('Wokwi-GUEST', '')
while not sta_if.isconnected():
    time.sleep(0.1)
print(" Connected")

# Client setup with SSL/TLS parameters
client = MQTTClient("wokwi-master", MQTT_BROKER, port=MQTT_PORT, user=MQTT_USER,
                    password=MQTT_PASSWORD, ssl=True, ssl_params={"server_hostname": MQTT_BROKER})
client.set_callback(mqtt_callback)
client.connect()
# Subscribe to command topics for all devices using a wildcard (+)
client.subscribe("cmnd/+/POWER")

# Initialize base power values for simulated devices to allow smooth transitions
simulated_values = {d: {'power': random.uniform(
    50, 300)} for d in SIMULATED_DEVICES}

print("\n[ACTIVE SYSTEM] Monitoring Smart Appliances\n")

# --- Main Operational Loop ---
while True:
    # Check for incoming MQTT messages (triggers the callback)
    client.check_msg()

    # Print Table Header to Console
    print("+" + "-"*20 + "+" + "-"*10 + "+" + "-"*12 + "+")
    print("| {:<18} | {:<8} | {:<10} |".format("DEVICE", "STATE", "POWER (W)"))
    print("+" + "-"*20 + "+" + "-"*10 + "+" + "-"*12 + "+")

    for d_id in ALL_IDS:
        power = 0.0
        voltage = 0.0

        # Only process data if the device is logically ON
        if device_states[d_id]:
            if d_id in ["sonoff_pow_01", "sonoff_pow_02"]:
                # Hardware mapping: Read ADC and scale to 0-500W
                pot = pot1 if d_id == "sonoff_pow_01" else pot2
                power = round((pot.read() / 4095.0) * 500.0, 1)
                voltage = round(228.0 + (pot.read() / 4095.0) * 7.0, 1)
            else:
                # Simulation mapping: Add random walk noise to the power value
                curr = simulated_values[d_id]['power']
                power = round(
                    max(0, min(500, curr + random.uniform(-15, 15))), 1)
                simulated_values[d_id]['power'] = power
                voltage = round(random.uniform(228, 234), 1)

        # --- Data Transmission ---
        # Construct JSON payload matching Tasmota/Sonoff format for InfluxDB compatibility
        payload = {"Time": format_time(), "ENERGY": {
            "Power": power, "Voltage": voltage}}
        client.publish("tele/{}/SENSOR".format(d_id), ujson.dumps(payload))

        # --- Console UI ---
        # Print a padded table row for the current device
        stare_str = "ON" if device_states[d_id] else "OFF"
        print("| {:<18} | {:<8} | {:>8.1f} W |".format(d_id, stare_str, power))

    # Table Footer
    print("+" + "-"*20 + "+" + "-"*10 + "+" + "-"*12 + "+")
    print("Last update: {}".format(format_time()))
    print("\n")

    # Wait 5 seconds before next telemetery cycle
    time.sleep(5)

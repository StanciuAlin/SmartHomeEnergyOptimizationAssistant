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

# MQTT Server Parameters - Your HiveMQ Cloud
MQTT_BROKER = "e1b9d425046b46d89b87f93fd80187c8.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "sefrem"
MQTT_PASSWORD = "Sefrem2021"

# Helper function to format time (MicroPython compatible)


def format_time():
    t = time.localtime()
    return f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}T{t[3]:02d}:{t[4]:02d}:{t[5]:02d}"


# Device Configuration
# Hardware devices (with potentiometers)
HARDWARE_DEVICES = [
    {"id": "sonoff_pow_01", "pin": 34, "client_id": "wokwi-sonoff-01"},
    {"id": "sonoff_pow_02", "pin": 35, "client_id": "wokwi-sonoff-02"}
]

# Simulated devices (no hardware, random data)
SIMULATED_DEVICES = [
    {"id": "sonoff_pow_03", "client_id": "wokwi-sonoff-03"},
    {"id": "sonoff_pow_04", "client_id": "wokwi-sonoff-04"},
    {"id": "sonoff_pow_05", "client_id": "wokwi-sonoff-05"},
    {"id": "sonoff_pow_06", "client_id": "wokwi-sonoff-06"},
    {"id": "sonoff_pow_07", "client_id": "wokwi-sonoff-07"}
]

ALL_DEVICES = HARDWARE_DEVICES + SIMULATED_DEVICES

# Initialize ADC for hardware potentiometers
pot1 = ADC(Pin(34))
pot1.atten(ADC.ATTN_11DB)  # 0-3.3V range

pot2 = ADC(Pin(35))
pot2.atten(ADC.ATTN_11DB)

print("Connecting to WiFi", end="")
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
sta_if.connect('Wokwi-GUEST', '')
while not sta_if.isconnected():
    print(".", end="")
    time.sleep(0.1)
print(" Connected!")

print("Connecting to MQTT server... ", end="")
# Use first device's client ID for MQTT connection
client = MQTTClient(
    "wokwi-sonoff-main",
    MQTT_BROKER,
    port=MQTT_PORT,
    user=MQTT_USER,
    password=MQTT_PASSWORD,
    ssl=True,
    ssl_params={"server_hostname": MQTT_BROKER}
)
client.connect()
print("Connected!")

# Send LWT (Last Will and Testament) for all devices
for device in ALL_DEVICES:
    client.publish(f"tele/{device['id']}/LWT", "Online", retain=True)

# Send Home Assistant Discovery Config (optional)
for device in ALL_DEVICES:
    discovery_topic = f"homeassistant/sensor/{device['id']}_power/config"
    discovery_payload = ujson.dumps({
        "name": f"Consum {device['id'].split('_')[-1]}",
        "state_topic": f"tele/{device['id']}/SENSOR",
        "value_template": "{{ value_json.ENERGY.Power }}",
        "unit_of_measurement": "W",
        "device_class": "power",
        "unique_id": f"{device['id']}_pw",
        "device": {"identifiers": [device['id']]}
    })
    client.publish(discovery_topic, discovery_payload, retain=True)

print(f"\n[DISCOVERY] Config sent for {len(ALL_DEVICES)} devices")
print("\nPublishing sensor data...")
print("Hardware devices: Rotate potentiometers to change power (0-500W)")
print("Simulated devices: Generating random power values\n")

# Track last values for simulated devices (for smoother transitions)
simulated_values = {}
for device in SIMULATED_DEVICES:
    simulated_values[device['id']] = {
        'power': random.uniform(0, 500),
        'voltage': random.uniform(228, 235)
    }

while True:
    for device in ALL_DEVICES:
        # Determine if hardware or simulated
        if device in HARDWARE_DEVICES:
            # Read from potentiometer
            pot_pin = pot1 if device['pin'] == 34 else pot2
            analog_value = pot_pin.read()

            # Map to 0-500W (0.1W precision)
            power = round((analog_value / 4095.0) * 500.0, 1)

            # Voltage varies slightly with power (228-235V)
            voltage = round(228.0 + (analog_value / 4095.0) * 7.0, 1)
        else:
            # Simulated device - generate realistic random values
            # Smooth transitions (change by max 10W per cycle)
            current_power = simulated_values[device['id']]['power']
            target_power = random.uniform(0, 500)
            power_change = random.uniform(-10, 10)
            new_power = max(0, min(500, current_power + power_change))

            # Voltage varies slightly
            voltage = round(random.uniform(228.0, 235.0), 1)

            # Update stored values
            simulated_values[device['id']]['power'] = new_power
            simulated_values[device['id']]['voltage'] = voltage

            power = round(new_power, 1)

        # Create sensor data matching sonoff.py structure
        sensor_data = {
            "Time": format_time(),
            "ENERGY": {
                "Total": 50.5,
                "Power": power,
                "Voltage": voltage
            }
        }

        # Publish to SENSOR topic (matching sonoff.py format)
        topic = f"tele/{device['id']}/SENSOR"
        message = ujson.dumps(sensor_data)
        client.publish(topic, message)

        # Print JSON for console (as requested)
        print(f"{device['id']}: {message}")

    print()  # Empty line between cycles
    time.sleep(5)  # Publish every 5 seconds

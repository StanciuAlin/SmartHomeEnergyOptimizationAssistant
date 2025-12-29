import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion  # Necesar pentru v2.0
import json
import time
import random
import os

# Configurații Broker
# BROKER = "broker.emqx.io"
# PORT = 1883

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Generăm 10 dispozitive Sonoff
devices = [f"sonoff_pow_{i:02d}" for i in range(1, 11)]


def send_discovery_config(client, device_id):
    """Trimite configurația pentru ca Home Assistant să recunoască dispozitivul."""
    # 1. Configurare Releu (Switch)
    discovery_topic = f"homeassistant/switch/{device_id}/config"
    payload = {
        "name": f"Priza {device_id.split('_')[-1]}",
        "state_topic": f"stat/{device_id}/POWER",
        "command_topic": f"cmnd/{device_id}/POWER",
        "availability_topic": f"tele/{device_id}/LWT",
        "payload_available": "Online",
        "payload_not_available": "Offline",
        "unique_id": f"{device_id}_relay",
        "device": {
            "identifiers": [device_id],
            "name": f"Sonoff {device_id}",
            "model": "Sonoff POW R2",
            "manufacturer": "Sonoff"
        }
    }
    client.publish(discovery_topic, json.dumps(payload), retain=True)

    # 2. Configurare Senzor Putere (W)
    sensor_topic = f"homeassistant/sensor/{device_id}_power/config"
    sensor_payload = {
        "name": f"Consum {device_id.split('_')[-1]}",
        "state_topic": f"tele/{device_id}/SENSOR",
        "value_template": "{{ value_json.ENERGY.Power }}",
        "unit_of_measurement": "W",
        "device_class": "power",
        "unique_id": f"{device_id}_pw",
        "device": {"identifiers": [device_id]}
    }
    client.publish(sensor_topic, json.dumps(sensor_payload), retain=True)
    print(f"[DISCOVERY] Configurație trimisă pentru {device_id}")


def on_message(client, userdata, msg):
    """Ascultă comenzile de la Home Assistant (ON/OFF)."""
    topic = msg.topic
    payload = msg.payload.decode()
    device_id = topic.split('/')[1]

    print(f"[COMMAND] {device_id} primit: {payload}")

    # Confirmăm starea către Home Assistant
    client.publish(f"stat/{device_id}/POWER", payload)


# Initializare Client
client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect(MQTT_HOST, MQTT_PORT, 60)

# Ne abonăm la topicurile de comandă pentru toate cele 10 prize
for device in devices:
    client.subscribe(f"cmnd/{device}/POWER")

client.loop_start()

# Pasul 1: Trimitem Discovery și LWT (Last Will and Testament)
for device in devices:
    send_discovery_config(client, device)
    client.publish(f"tele/{device}/LWT", "Online", retain=True)

print("\nDispozitivele ar trebui să apară acum în Home Assistant > Integrări > MQTT.")
print("Pornire trimitere telemetrie (senzori)...")

try:
    while True:
        for device in devices:
            # Generăm date false pentru senzori
            voltage = round(random.uniform(228.0, 235.0), 1)
            power = round(random.uniform(0.0, 500.0), 1)

            sensor_data = {
                "Time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "ENERGY": {
                    "Total": 50.5,
                    "Power": power,
                    "Voltage": voltage
                }
            }

            # Trimitem datele la senzori
            client.publish(f"tele/{device}/SENSOR", json.dumps(sensor_data))

        time.sleep(15)  # Trimitem date la fiecare 15 secunde
except KeyboardInterrupt:
    print("Deconectare...")
    for device in devices:
        client.publish(f"tele/{device}/LWT", "Offline", retain=True)
    client.loop_stop()
    client.disconnect()
    print("Deconectat.")

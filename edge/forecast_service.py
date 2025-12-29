import os
import time
import pandas as pd
from prophet import Prophet
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# 1. Configurare din variabilele de mediu
URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
TOKEN = os.getenv("INFLUXDB_TOKEN")
ORG = os.getenv("INFLUXDB_ORG")
BUCKET = os.getenv("INFLUXDB_BUCKET")

client = InfluxDBClient(url=URL, token=TOKEN, org=ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()


def get_data_and_forecast():
    # 2. Citirea datelor din InfluxDB (ultimele 24 ore)
    query = f'from(bucket: "{BUCKET}") |> range(start: -24h) |> filter(fn: (r) => r["_measurement"] == "energy_usage")'
    result = query_api.query_data_frame(query)

    if result.empty:
        print("Nu sunt suficiente date pentru predicție...")
        return

    # Pregătire date pentru Prophet (are nevoie de coloanele 'ds' și 'y')
    df = result[['_time', '_value']].rename(
        columns={'_time': 'ds', '_value': 'y'})
    df['ds'] = df['ds'].dt.tz_localize(None)

    # 3. Modelare cu Prophet
    model = Prophet(interval_width=0.95)
    model.fit(df)

    # Predicție pentru următoarele 6 ore
    future = model.make_future_dataframe(periods=6, freq='H')
    forecast = model.predict(future)

    # 4. Salvare predicție înapoi în InfluxDB
    for index, row in forecast.tail(6).iterrows():
        point = Point("energy_forecast") \
            .field("predicted_value", row['yhat']) \
            .time(row['ds'])
        write_api.write(bucket=BUCKET, record=point)

    print("Predicție realizată și salvată cu succes!")


# Buclă infinită care rulează predicția la fiecare 30 de minute
if __name__ == "__main__":
    while True:
        try:
            get_data_and_forecast()
        except Exception as e:
            print(f"Eroare: {e}")
        time.sleep(1800)

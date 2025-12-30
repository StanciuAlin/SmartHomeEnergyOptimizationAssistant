import os
import time
import pandas as pd
import warnings
from prophet import Prophet
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.warnings import MissingPivotFunction

# Dezactivăm avertismentul Pivot (îl rezolvăm oricum în query)
warnings.simplefilter("ignore", MissingPivotFunction)

# Configurații
URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
TOKEN = os.getenv("INFLUXDB_TOKEN")
ORG = os.getenv("INFLUXDB_ORG")
BUCKET = os.getenv("INFLUXDB_BUCKET")

client = InfluxDBClient(url=URL, token=TOKEN, org=ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()


def get_data_and_forecast():
    # Query cu pivot inclus pentru a crea coloana 'power'
    query = f'''
    from(bucket: "{BUCKET}") 
        |> range(start: -24h) 
        |> filter(fn: (r) => r["_measurement"] == "energy_usage")
        |> filter(fn: (r) => r["_field"] == "power")
        |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''

    # Obținem datele
    result = query_api.query_data_frame(query)

    # REPARARE EROARE: Verificăm dacă result este o listă (InfluxDB v2 face asta des)
    if isinstance(result, list):
        if not result:
            print("Lista de rezultate este goală. Aștept date...")
            return
        df = pd.concat(result)
    else:
        df = result

    # Verificăm dacă DataFrame-ul este gol
    if df.empty:
        print("Nu există date în DataFrame. Aștept colectarea datelor...")
        return

    # Verificăm dacă avem coloana 'power' în urma pivotării
    if 'power' not in df.columns:
        print("Coloana 'power' lipsește. Verifică datele din InfluxDB.")
        return

    # Pregătire pentru Prophet
    df = df[['_time', 'power']].rename(columns={'_time': 'ds', 'power': 'y'})
    df['ds'] = df['ds'].dt.tz_localize(None)

    # Modelare
    model = Prophet(interval_width=0.95)
    model.fit(df)

    # Predicție pentru 6 ore
    future = model.make_future_dataframe(periods=6, freq='H')
    forecast = model.predict(future)

    # Salvăm doar rândurile noi (viitorul)
    predictions = forecast.tail(6)

    for index, row in predictions.iterrows():
        point = Point("energy_forecast") \
            .field("predicted_value", float(row['yhat'])) \
            .field("upper_bound", float(row['yhat_upper'])) \
            .field("lower_bound", float(row['yhat_lower'])) \
            .time(row['ds'])
        write_api.write(bucket=BUCKET, record=point)

    print(f"[{time.strftime('%H:%M:%S')}] Predicție salvată cu succes.")


if __name__ == "__main__":
    while True:
        try:
            get_data_and_forecast()
        except Exception as e:
            print(f"Eroare în buclă: {e}")
        time.sleep(60)  # Rulează la 10 minute

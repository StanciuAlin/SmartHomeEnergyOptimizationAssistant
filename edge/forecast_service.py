import os
import time
import warnings
import logging
import pandas as pd
from prophet import Prophet
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.warnings import MissingPivotFunction

# Disable the Pivot warning from InfluxDB client (we handle it in the Flux query)
warnings.simplefilter("ignore", MissingPivotFunction)

# Disable logging for Prophet to keep the console clean
logging.getLogger('prophet').setLevel(logging.ERROR)
logging.getLogger('cmdstanpy').setLevel(logging.ERROR)

# --- Configuration via Environment Variables ---
URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
TOKEN = os.getenv("INFLUXDB_TOKEN")
ORG = os.getenv("INFLUXDB_ORG")
BUCKET = os.getenv("INFLUXDB_BUCKET")

# Initialize InfluxDB Client
client = InfluxDBClient(url=URL, token=TOKEN, org=ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()


def get_data_and_forecast():
    """
    Fetches historical energy data from InfluxDB, generates a forecast using Prophet,
    and writes the predicted values back to InfluxDB.
    """

    target_devices = ["sonoff_pow_01", "sonoff_pow_02"]

    for device_id in target_devices:
        # 1. Query modificat: Filtrăm datele special pentru acest DEVICE
        query = f'''
        from(bucket: "{BUCKET}") 
            |> range(start: -24h) 
            |> filter(fn: (r) => r["_measurement"] == "energy_usage")
            |> filter(fn: (r) => r["device"] == "{device_id}")
            |> filter(fn: (r) => r["_field"] == "power")
            |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''

        # Execute query and get result as a DataFrame
        result = query_api.query_data_frame(query)

        # REPAIR: InfluxDB v2 often returns a list of DataFrames; concatenate them if necessary
        if isinstance(result, list):
            if not result:
                print(
                    f"[{time.strftime('%H:%M:%S')}] Result list is empty. Waiting for data...")
                return
            df = pd.concat(result)
        else:
            df = result

        # Check if DataFrame contains data
        if df.empty:
            print(
                f"[{time.strftime('%H:%M:%S')}] No data found in DataFrame. Data collection in progress...")
            return

        # Check if the 'power' column exists after pivoting
        if 'power' not in df.columns:
            print(
                f"[{time.strftime('%H:%M:%S')}] Column 'power' is missing. Check InfluxDB data/fields.")
            return

        # --- Data Preparation for Prophet ---
        # Prophet requires columns 'ds' (datestamp) and 'y' (value to predict)
        df = df[['_time', 'power']].rename(
            columns={'_time': 'ds', 'power': 'y'})

        # Remove timezone information to avoid Prophet compatibility issues
        df['ds'] = df['ds'].dt.tz_localize(None)

        # Ensure we have enough data points (Prophet usually needs at least 2 points, but 15+ is better for stability)
        if len(df) < 16:
            print(
                f"[{time.strftime('%H:%M:%S')}] Not enough data points to train model.")
            return

        # --- Modeling ---
        # interval_width=0.95 sets the uncertainty interval (confidence range)
        model = Prophet(interval_width=0.95)
        model.fit(df)

        # Create a future dataframe for the next 6 hours
        future = model.make_future_dataframe(periods=6, freq='h')
        forecast = model.predict(future)

        # --- Filter for New Predictions Only ---
        # We only want to save data points that are in the future relative to our last real data point
        last_real_date = df['ds'].max()
        predictions = forecast[forecast['ds'] > last_real_date].copy()

        if predictions.empty:
            print(
                f"[{time.strftime('%H:%M:%S')}] No new prediction points generated.")
            return

        # --- Writing to InfluxDB ---
        for index, row in predictions.iterrows():
            point = Point("energy_forecast") \
                .tag("device", device_id) \
                .field("predicted_value", float(row['yhat'])) \
                .field("upper_bound", float(row['yhat_upper'])) \
                .field("lower_bound", float(row['yhat_lower'])) \
                .time(row['ds'])

            write_api.write(bucket=BUCKET, record=point)

        print(f"[{time.strftime('%H:%M:%S')}] Forecast saved successfully ({len(predictions)} new points) to InfluxDB.")


if __name__ == "__main__":
    print(f"Forecast service started. Monitoring {BUCKET} bucket...")
    while True:
        try:
            get_data_and_forecast()
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Error in main loop: {e}")

        # Run every 10 minutes (600 seconds)
        time.sleep(600)

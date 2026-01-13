import os
import time
import warnings
import logging
import pandas as pd
from prophet import Prophet
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.warnings import MissingPivotFunction

# Disable warnings and clean up console output
warnings.simplefilter("ignore", MissingPivotFunction)
logging.getLogger('prophet').setLevel(logging.ERROR)
logging.getLogger('cmdstanpy').setLevel(logging.ERROR)

# Config the InfluxDB connection using environment variables
URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
TOKEN = os.getenv("INFLUXDB_TOKEN")
ORG = os.getenv("INFLUXDB_ORG")
BUCKET = os.getenv("INFLUXDB_BUCKET")

client = InfluxDBClient(url=URL, token=TOKEN, org=ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()


def get_data_and_forecast():
    target_devices = ["sonoff_pow_01", "sonoff_pow_02"]

    for device_id in target_devices:
        query = f'''
            from(bucket: "{BUCKET}")
            |> range(start: -24h)
            |> filter(fn: (r) => r["_measurement"] == "energy_usage")
            |> filter(fn: (r) => r["_field"] == "power" or r["_field"] == "device_id")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            |> filter(fn: (r) => r["device_id"] == "{device_id}")
        '''

        df = query_api.query_data_frame(query)

        if isinstance(df, list):
            df = pd.concat(df) if df else pd.DataFrame()

        if df.empty:
            print(
                f"[{time.strftime('%H:%M:%S')}] No data found for {device_id}. Skipping forecast.")
            continue

        if 'power' not in df.columns:
            print(
                f"[{time.strftime('%H:%M:%S')}] 'power' data missing for {device_id}.")
            continue

        df_prophet = df[['_time', 'power']].rename(
            columns={'_time': 'ds', 'power': 'y'})
        df_prophet['ds'] = pd.to_datetime(
            df_prophet['ds']).dt.tz_localize(None)

        if len(df_prophet) < 3:  # Prophet needs at least 3 data points to function, preferably more for better accuracy (trend detection)
            print(
                f"[{time.strftime('%H:%M:%S')}] {device_id}: insufficient points ({len(df_prophet)}).")
            continue

        '''
        Prophet is a procedure for forecasting time series data based on an additive model where non-linear trends are fit with yearly, weekly, and daily seasonality, plus holiday effects. 
        It works best with time series that have strong seasonal effects and several seasons of historical data. Prophet is robust to missing data and shifts in the trend, and typically handles outliers well.
        '''

        model = Prophet(
            # Less sensitive to noise (decreased from 0.05)
            changepoint_prior_scale=0.01,
            uncertainty_samples=50,       # Enough samples for uncertainty estimation
            interval_width=0.95,          # 95% prediction intervals
            growth='linear'               # Linear growth model which fits power consumption better
        )
        model.fit(df_prophet)

        future = model.make_future_dataframe(periods=6, freq='h')
        forecast = model.predict(future)

        # Ensure no negative predictions (for power consumption)
        for col in ['yhat', 'yhat_upper', 'yhat_lower']:
            forecast[col] = forecast[col].clip(lower=0)

        last_real_date = df_prophet['ds'].max()
        predictions = forecast[forecast['ds'] > last_real_date].copy()

        # Write predictions back in InfluxDB
        for _, row in predictions.iterrows():
            point = Point("energy_forecast") \
                .field("device_id", device_id) \
                .field("predicted_value", float(row['yhat'])) \
                .field("upper_bound", float(row['yhat_upper'])) \
                .field("lower_bound", float(row['yhat_lower'])) \
                .time(row['ds'])  # InfluxDB will handle timezone correctly

            write_api.write(bucket=BUCKET, record=point)

        print(f"[{time.strftime('%H:%M:%S')}] SUCCESS forecasting for {device_id} ({len(predictions)} points).")


if __name__ == "__main__":
    print(f"Forecast Service is online on: {BUCKET}")
    while True:
        try:
            get_data_and_forecast()
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Error: {e}")
        # Run every 60 seconds and forecast for the next 6 hours
        # Forecast interval can be 300 seconds or more for production
        time.sleep(60)  # 60s for demo purposes

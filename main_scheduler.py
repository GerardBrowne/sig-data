import os
import time
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

# --- Load Configuration from .env file ---
load_dotenv()

# Sigen specific (used to pass to sigen_api_client functions)
SIGEN_STATION_ID = os.getenv("SIGEN_STATION_ID")
SIGEN_BASE_URL = os.getenv("SIGEN_BASE_URL", "https://api-eu.sigencloud.com")

# Weather specific (used to pass to weather_api_client functions)
WEATHER_LATITUDE = os.getenv("WEATHER_LATITUDE")
WEATHER_LONGITUDE = os.getenv("WEATHER_LONGITUDE")
WEATHER_TIMEZONE_STR = os.getenv("WEATHER_TIMEZONE", "Europe/Dublin") # For Open-Meteo API call

# Local timezone for date calculations (e.g., for "today", "yesterday")
LOCAL_TZ_STR = os.getenv("TIMEZONE", "Europe/Dublin") # Should match WEATHER_TIMEZONE_STR for consistency
try:
    LOCAL_TZ = pytz.timezone(LOCAL_TZ_STR)
except pytz.exceptions.UnknownTimeZoneError:
    print(f"MAIN_SCHEDULER CRITICAL Error: Unknown timezone '{LOCAL_TZ_STR}'. Please check .env. Exiting.")
    exit()

# --- Import your custom modules ---
# These should be in the same directory or your Python path
try:
    from auth_handler import get_active_sigen_access_token
    from sigen_api_client import (
        fetch_sigen_energy_flow,
        fetch_sigen_daily_consumption_stats,
        fetch_sigen_sunrise_sunset,
        fetch_sigen_station_info # Assuming you might want to add this
    )
    from weather_api_client import fetch_open_meteo_weather_data
    from influxdb_writer import (
        write_energy_flow_to_influxdb,
        write_daily_consumption_to_influxdb,
        write_sunrise_sunset_to_influxdb,
        write_weather_data_to_influxdb,
        # write_station_info_to_influxdb # If you implement this
    )
except ImportError as e:
    print(f"MAIN_SCHEDULER CRITICAL Error: Could not import one or more modules: {e}")
    print("Ensure auth_handler.py, sigen_api_client.py, weather_api_client.py, and influxdb_writer.py are present.")
    exit()

# --- Task Scheduling Intervals (examples) ---
# Weather will be fetched if current_minute % 15 == 2 (e.g., at :02, :17, :32, :47)
WEATHER_FETCH_MINUTE_MODULO = 15
WEATHER_FETCH_TRIGGER_MINUTE = 2

# Daily stats will be fetched if current_hour % 6 == 0 and current_minute == 5 (e.g., 00:05, 06:05, 12:05, 18:05)
DAILY_STATS_FETCH_HOUR_MODULO = 6
DAILY_STATS_FETCH_TRIGGER_MINUTE = 5

# Sunrise/sunset will be fetched if current_hour == 0 and current_minute == 3 (e.g., 00:03 daily)
SUNRISE_SUNSET_FETCH_TRIGGER_HOUR = 0
SUNRISE_SUNSET_FETCH_TRIGGER_MINUTE = 3


def run_tasks():
    """Main function to orchestrate fetching and writing data."""
    print(f"\n--- Main Scheduler Cycle Started ({datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}) ---")

    # 1. Get Active Sigen API Token
    # This function now handles loading, checking expiry, refreshing, or full re-auth
    active_sigen_token = get_active_sigen_access_token()

    if not active_sigen_token:
        print("MAIN_SCHEDULER: Failed to obtain Sigen API token. Skipping Sigen API calls for this cycle.")
    else:
        # --- 1a. Fetch Sigen Real-time Energy Flow Data (Every Run) ---
        print("\nFetching Sigen real-time energy flow data...")
        sigen_energy_payload = fetch_sigen_energy_flow(active_sigen_token, SIGEN_BASE_URL, SIGEN_STATION_ID)
        if sigen_energy_payload:
            write_energy_flow_to_influxdb(sigen_energy_payload, SIGEN_STATION_ID)
        else:
            print("No Sigen energy flow data fetched in this cycle.")

        current_time_local = datetime.now(LOCAL_TZ)

        # --- 1b. Fetch Sigen Daily Consumption Statistics (Periodically) ---
        if current_time_local.hour % DAILY_STATS_FETCH_HOUR_MODULO == 0 and current_time_local.minute == DAILY_STATS_FETCH_TRIGGER_MINUTE:
            print("\n--- Attempting to fetch Sigen daily consumption stats ---")
            today_api_str = current_time_local.strftime("%Y%m%d") # For "today so far"
            consumption_stats = fetch_sigen_daily_consumption_stats(active_sigen_token, SIGEN_BASE_URL, SIGEN_STATION_ID, today_api_str)
            if consumption_stats:
                write_daily_consumption_to_influxdb(consumption_stats, SIGEN_STATION_ID, current_time_local)
            # You might also want to fetch for "yesterday" if it's just past midnight
            if current_time_local.hour == 0 and current_time_local.minute == DAILY_STATS_FETCH_TRIGGER_MINUTE:
                 yesterday_obj_local = current_time_local - timedelta(days=1)
                 yesterday_api_str = yesterday_obj_local.strftime("%Y%m%d")
                 print(f"Fetching Sigen consumption stats for YESTERDAY: {yesterday_api_str}")
                 consumption_stats_yesterday = fetch_sigen_daily_consumption_stats(active_sigen_token, SIGEN_BASE_URL, SIGEN_STATION_ID, yesterday_api_str)
                 if consumption_stats_yesterday:
                     write_daily_consumption_to_influxdb(consumption_stats_yesterday, SIGEN_STATION_ID, yesterday_obj_local)
        else:
            print(f"\nSkipping Sigen daily consumption stats fetch (not scheduled minute/hour).")


        # --- 1c. Fetch Sigen Sunrise/Sunset Data (Periodically, e.g., once a day) ---
        if current_time_local.hour == SUNRISE_SUNSET_FETCH_TRIGGER_HOUR and current_time_local.minute == SUNRISE_SUNSET_FETCH_TRIGGER_MINUTE:
            print("\n--- Attempting to fetch daily sunrise/sunset data ---")
            today_for_sun_obj_local = datetime.now(LOCAL_TZ) # Get current day for sunrise/sunset
            sun_info = fetch_sigen_sunrise_sunset(active_sigen_token, SIGEN_BASE_URL, SIGEN_STATION_ID, today_for_sun_obj_local.strftime("%Y%m%d"))
            if sun_info:
                write_sunrise_sunset_to_influxdb(sun_info, SIGEN_STATION_ID, today_for_sun_obj_local)
        else:
            print(f"\nSkipping Sigen sunrise/sunset fetch (not scheduled time).")

        # Add fetch_sigen_station_info if desired, perhaps on a less frequent schedule too

    # --- 2. Fetch Open-Meteo Weather Data (Periodically) ---
    # This part does not depend on the Sigen token
    current_time_local_for_weather = datetime.now(LOCAL_TZ) # Get current time again for minute check
    if current_time_local_for_weather.minute % WEATHER_FETCH_MINUTE_MODULO == WEATHER_FETCH_TRIGGER_MINUTE:
        print("\n--- Attempting to fetch weather data ---")
        if WEATHER_LATITUDE and WEATHER_LONGITUDE:
            weather_data_response = fetch_open_meteo_weather_data(WEATHER_LATITUDE, WEATHER_LONGITUDE, WEATHER_TIMEZONE_STR)
            if weather_data_response:
                write_weather_data_to_influxdb(weather_data_response, SIGEN_STATION_ID) # Use station_id as a tag
            else:
                print("Failed to fetch weather data this cycle.")
        else:
            print("Weather latitude/longitude not configured in .env. Skipping weather fetch.")
    else:
        print(f"\nSkipping weather fetch (not scheduled minute).")

    print(f"\n--- Main Scheduler Cycle Finished ({datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}) ---")


if __name__ == "__main__":
    # Basic check for essential Sigen configurations from .env needed by sigen_api_client
    if not SIGEN_STATION_ID:
        print("MAIN_SCHEDULER CRITICAL Error: SIGEN_STATION_ID not found in .env file or environment.")
        print("Please configure this in your .env file.")
        exit()
    
    run_tasks()
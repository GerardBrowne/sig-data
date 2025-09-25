import os
import time
from datetime import datetime, timedelta, timezone
import pytz
from dotenv import load_dotenv
import json
from logger import get_logger

logger = get_logger(__name__)

# --- Load Configuration from .env file ---
load_dotenv()

# Sigen specific
SIGEN_STATION_ID = os.getenv("SIGEN_STATION_ID")
SIGEN_BASE_URL = os.getenv("SIGEN_BASE_URL", "https://api-eu.sigencloud.com")

# Weather specific
WEATHER_LATITUDE = os.getenv("WEATHER_LATITUDE")
WEATHER_LONGITUDE = os.getenv("WEATHER_LONGITUDE")
WEATHER_TIMEZONE_STR = os.getenv("WEATHER_TIMEZONE", "Europe/Dublin")

# Local timezone for date calculations
LOCAL_TZ_STR = os.getenv("TIMEZONE", "Europe/Dublin")
try:
    LOCAL_TZ = pytz.timezone(LOCAL_TZ_STR)
except pytz.exceptions.UnknownTimeZoneError:
    logger.critical(f"Unknown timezone '{LOCAL_TZ_STR}'. Please check .env. Exiting.")
    raise SystemExit(1)

# InfluxDB specific (ensure INFLUX_TOKEN is in .env for influxdb_writer.py)
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")

# --- Import your custom modules ---
try:
    from auth_handler import get_active_sigen_access_token
    from sigen_api_client import (
        fetch_sigen_energy_flow,
        fetch_sigen_daily_energy_summary,
        fetch_sigen_sunrise_sunset,
    )
    from weather_api_client import fetch_open_meteo_weather_data
    from influxdb_writer import (
        write_energy_flow_to_influxdb,
        write_sigen_daily_summary_to_influxdb,
        write_sunrise_sunset_to_influxdb,
        write_weather_data_to_influxdb,
    )
except ImportError as e:
    logger.critical(f"Could not import one or more modules: {e}")
    logger.critical("Ensure auth_handler.py, sigen_api_client.py, weather_api_client.py, and influxdb_writer.py are present and correct.")
    raise SystemExit(1)

# --- Task Scheduling Intervals (examples) ---
WEATHER_FETCH_MINUTE_MODULO = 15
WEATHER_FETCH_TRIGGER_MINUTE = 2

DAILY_REPORTS_TRIGGER_HOUR = 0
DAILY_REPORTS_TRIGGER_MINUTE = 10

SUNRISE_SUNSET_FETCH_TRIGGER_HOUR = 0
SUNRISE_SUNSET_FETCH_TRIGGER_MINUTE = 3

def fetch_and_store_specific_days_sigen_summary(sigen_api_token, target_date_local_obj):
    """Fetches and stores Sigen daily energy summary for a specific date."""
    logger.info(f"Attempting to fetch Sigen daily energy summary for date: {target_date_local_obj.strftime('%Y-%m-%d')}")
    target_date_api_str = target_date_local_obj.strftime("%Y%m%d")
    daily_summary_data = fetch_sigen_daily_energy_summary(
        sigen_api_token, SIGEN_BASE_URL, SIGEN_STATION_ID, target_date_api_str
    )
    if daily_summary_data:
        write_sigen_daily_summary_to_influxdb(
            daily_summary_data, SIGEN_STATION_ID, target_date_local_obj
        )
    else:
        logger.warning(f"No daily summary data returned from Sigen API for {target_date_api_str}.")

def run_normal_tasks(active_sigen_token, current_time_local):
    """Main function to orchestrate fetching and writing data based on schedule."""
    # --- 1a. Fetch Sigen Real-time Energy Flow Data (Every Run) ---
    if active_sigen_token:
        logger.info("Fetching Sigen real-time energy flow data...")
        sigen_api_energy_flow_data = fetch_sigen_energy_flow(active_sigen_token, SIGEN_BASE_URL, SIGEN_STATION_ID)
        
        if sigen_api_energy_flow_data:
            logger.debug(f"Raw sigen_energy_payload from API: {json.dumps(sigen_api_energy_flow_data, indent=2)}")

            influx_energy_payload = {
                "pv_day_nrg": sigen_api_energy_flow_data.get("pvDayNrg"),
                "pv_power": sigen_api_energy_flow_data.get("pvPower"),
                "load_power": sigen_api_energy_flow_data.get("loadPower"),
                "battery_soc": sigen_api_energy_flow_data.get("batterySoc"),
                "grid_flow_power": sigen_api_energy_flow_data.get("buySellPower"),
                "battery_power": sigen_api_energy_flow_data.get("batteryPower"),
                "on_grid": 1 if sigen_api_energy_flow_data.get("onGrid") else 0 if sigen_api_energy_flow_data.get("onGrid") is not None else None,
                "station_status": sigen_api_energy_flow_data.get("stationStatus"),
                "on_off_grid_status": sigen_api_energy_flow_data.get("onOffGridStatus"),
                "ac_power": sigen_api_energy_flow_data.get("acPower"),
                "ev_power": sigen_api_energy_flow_data.get("evPower"),
                "generator_power": sigen_api_energy_flow_data.get("generatorPower"),
                "heat_pump_power": sigen_api_energy_flow_data.get("heatPumpPower"),
                "third_pv_power": sigen_api_energy_flow_data.get("thirdPvPower")
            }

            influx_payload_ready_for_writer = {key: value for key, value in influx_energy_payload.items() if value is not None}

            if influx_payload_ready_for_writer:
                write_energy_flow_to_influxdb(influx_payload_ready_for_writer, SIGEN_STATION_ID)
            else:
                logger.info("No valid energy flow data fields to write after preparing payload.")
        else:
            logger.warning("No Sigen energy flow data fetched in this cycle (API client returned None).")
    else:
        logger.warning("Skipping Sigen real-time energy flow fetch: No active Sigen token.")
    
    # --- Tasks that run periodically based on current time ---

    # Fetch Sigen Daily Energy Summary for PREVIOUS day (runs once a day)
    if current_time_local.hour == DAILY_REPORTS_TRIGGER_HOUR and current_time_local.minute == DAILY_REPORTS_TRIGGER_MINUTE:
        if active_sigen_token:
            yesterday_obj_local = current_time_local - timedelta(days=1)
            fetch_and_store_specific_days_sigen_summary(active_sigen_token, yesterday_obj_local)
        else:
            logger.warning("Skipping Sigen daily summary fetch: No active token.")
    else:
        logger.debug(
            f"Skipping Sigen daily energy summary fetch (not {DAILY_REPORTS_TRIGGER_HOUR:02d}:{DAILY_REPORTS_TRIGGER_MINUTE:02d})."
        )

    # Fetch Sigen Sunrise/Sunset Data for CURRENT day (runs once a day)
    if current_time_local.hour == SUNRISE_SUNSET_FETCH_TRIGGER_HOUR and current_time_local.minute == SUNRISE_SUNSET_FETCH_TRIGGER_MINUTE:
        if active_sigen_token:
            logger.info("Attempting to fetch daily sunrise/sunset data")
            today_for_sun_obj_local = datetime.now(LOCAL_TZ)
            sun_info = fetch_sigen_sunrise_sunset(active_sigen_token, SIGEN_BASE_URL, SIGEN_STATION_ID, today_for_sun_obj_local.strftime("%Y%m%d"))
            if sun_info:
                write_sunrise_sunset_to_influxdb(sun_info, SIGEN_STATION_ID, today_for_sun_obj_local)
        else:
            logger.warning("Skipping Sigen sunrise/sunset fetch: No active token.")
    else:
        logger.debug(
            f"Skipping Sigen sunrise/sunset fetch (not {SUNRISE_SUNSET_FETCH_TRIGGER_HOUR:02d}:{SUNRISE_SUNSET_FETCH_TRIGGER_MINUTE:02d})."
        )

    # Fetch Open-Meteo Weather Data (Periodically)
    if current_time_local.minute % WEATHER_FETCH_MINUTE_MODULO == WEATHER_FETCH_TRIGGER_MINUTE:
        logger.info("Attempting to fetch weather data")
        if WEATHER_LATITUDE and WEATHER_LONGITUDE:
            weather_data_response = fetch_open_meteo_weather_data(WEATHER_LATITUDE, WEATHER_LONGITUDE, WEATHER_TIMEZONE_STR)
            if weather_data_response:
                write_weather_data_to_influxdb(weather_data_response, SIGEN_STATION_ID)
            else:
                logger.warning("Failed to fetch weather data this cycle.")
        else:
            logger.warning("Weather latitude/longitude not configured in .env. Skipping weather fetch.")
    else:
        logger.debug(f"Skipping weather fetch (not scheduled minute: {current_time_local.minute}).")


if __name__ == "__main__":
    logger.info(
        f"Main Scheduler Script Started ({datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')})"
    )

    RUN_BACKFILL_FOR_YESTERDAY_SUMMARY = False

    if not SIGEN_STATION_ID:
        logger.critical("SIGEN_STATION_ID not found. Please configure in .env file.")
        raise SystemExit(1)
    if not INFLUX_TOKEN or INFLUX_TOKEN == "YOUR_INFLUXDB_OPERATOR_API_TOKEN":
        logger.critical("INFLUX_TOKEN is not set correctly in .env. Please update it.")
        raise SystemExit(1)

    active_sigen_token = get_active_sigen_access_token()
    if not active_sigen_token:
        logger.warning("Failed to get active Sigen token. Most Sigen-dependent tasks will be skipped.")
    
    if RUN_BACKFILL_FOR_YESTERDAY_SUMMARY:
        if active_sigen_token:
            logger.info("Manual trigger: Attempting to backfill Sigen daily energy summary for YESTERDAY")
            yesterday_obj_local = datetime.now(LOCAL_TZ) - timedelta(days=1)
            fetch_and_store_specific_days_sigen_summary(active_sigen_token, yesterday_obj_local)
            logger.info("Manual trigger finished. Set RUN_BACKFILL_FOR_YESTERDAY_SUMMARY to False to avoid re-running.")
        else:
            logger.warning("Manual trigger: Cannot backfill Sigen daily summary, no active Sigen token.")
    else:
        logger.debug("Skipping one-time backfill for yesterday as RUN_BACKFILL_FOR_YESTERDAY_SUMMARY is False.")

    logger.info("Running normal scheduled tasks for current time")
    run_normal_tasks(active_sigen_token, datetime.now(LOCAL_TZ))

    logger.info(
        f"Main Scheduler Script Execution Complete ({datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')})"
    )
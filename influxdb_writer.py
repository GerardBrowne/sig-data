import os
from datetime import datetime, timezone, timedelta
import pytz
from dateutil import parser as dateutil_parser
from dotenv import load_dotenv
from logger import get_logger

# Attempt to import InfluxDB client parts, with a fallback for initial setup
try:
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
    INFLUX_CLIENT_AVAILABLE = True
except ImportError:
    INFLUX_CLIENT_AVAILABLE = False
    print("INFLUXDB_WRITER: influxdb-client library not found. Please install it: pip install influxdb-client")
    class Point: pass

logger = get_logger(__name__)

# Load environment variables from .env file
load_dotenv()

# --- InfluxDB Configuration - Loaded from .env ---
INFLUX_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUX_ORG = os.getenv("INFLUXDB_ORG")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET")
LOCAL_TZ_STR = os.getenv("TIMEZONE", "Europe/Dublin")

# Basic check for essential InfluxDB configurations
if INFLUX_CLIENT_AVAILABLE and (not all([INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET])):
    logger.error("INFLUXDB_TOKEN, INFLUXDB_ORG, or INFLUXDB_BUCKET not found in .env file or environment. Writing will fail.")

def _get_local_timezone():
    """Helper to get the local pytz timezone object."""
    try:
        return pytz.timezone(LOCAL_TZ_STR)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.warning(f"Unknown timezone '{LOCAL_TZ_STR}'. Defaulting to UTC.")
        return pytz.utc

def write_energy_flow_to_influxdb(energy_data, station_id_tag):
    """Writes Sigen energy flow data to InfluxDB."""
    if not INFLUX_CLIENT_AVAILABLE:
        return
    if not energy_data:
        logger.info("No energy_flow data provided to write.")
        return
    if not all([INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET]):
        return

    fields_to_write = {}
    essential_fields_valid = True
    for key, value in energy_data.items():
        if value is not None:
            try:
                fields_to_write[key] = float(value)
            except (ValueError, TypeError):
                logger.warning(f"Could not convert '{key}':'{value}' to float. Skipping.")
                if key in ["pv_power", "load_power", "battery_soc"]:
                    essential_fields_valid = False
    
    if not essential_fields_valid:
        logger.error("Critical field was invalid. Aborting write.")
        return
    if not fields_to_write:
        logger.info("No valid numeric fields in energy_flow data to write.")
        return

    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            point = Point("energy_metrics").tag("station_id", station_id_tag).time(datetime.now(timezone.utc))
            for field_name, field_value in fields_to_write.items():
                point = point.field(field_name, field_value)
            write_api.write(bucket=INFLUX_BUCKET, record=point)
            logger.debug("Successfully wrote energy_flow data.")
    except Exception as e:
        logger.exception(f"Error writing energy_flow data: {e}")

def write_daily_consumption_to_influxdb(consumption_data, station_id_tag, target_date_obj_local):
    """Writes Sigen daily total and hourly consumption data to InfluxDB."""
    if not INFLUX_CLIENT_AVAILABLE:
        return
    if not consumption_data:
        logger.info("No consumption_data (daily/hourly) to write.")
        return
    if not all([INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET]):
        return

    points_to_write = []
    local_tz = _get_local_timezone()

    # Daily total consumption
    daily_total = consumption_data.get("baseLoadConsumption")
    if daily_total is not None:
        try:
            daily_ts_local = local_tz.localize(datetime(target_date_obj_local.year, target_date_obj_local.month, target_date_obj_local.day))
            daily_ts_utc = daily_ts_local.astimezone(timezone.utc)
            point_daily = Point("daily_consumption_summary").tag("station_id", station_id_tag).tag("source", "sigen_api_stats").field("total_base_load_kwh", float(daily_total)).time(daily_ts_utc)
            points_to_write.append(point_daily)
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not process total_base_load_kwh '{daily_total}': {e}")

    # Hourly consumption details
    hourly_list = consumption_data.get("consumptionDetailList", [])
    processed_hours = set()
    for item in hourly_list:
        data_time_str = item.get("dataTime") # "YYYYMMDD HH:MM"
        hourly_val = item.get("baseLoadConsumption")
        if data_time_str and hourly_val is not None:
            if data_time_str in processed_hours:
                continue
            processed_hours.add(data_time_str)
            try:
                dt_obj_naive = dateutil_parser.parse(data_time_str)
                dt_obj_local_aware = local_tz.localize(dt_obj_naive)
                dt_obj_utc = dt_obj_local_aware.astimezone(timezone.utc)
                point_hourly = Point("hourly_consumption").tag("station_id", station_id_tag).tag("source", "sigen_api_stats").field("base_load_kwh", float(hourly_val)).time(dt_obj_utc)
                points_to_write.append(point_hourly)
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not process hourly consumption for '{data_time_str}': {e}")
    
    if not points_to_write:
        logger.info("No valid daily/hourly consumption points to write.")
        return
    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=INFLUX_BUCKET, record=points_to_write)
            logger.debug(f"Successfully wrote {len(points_to_write)} daily/hourly consumption stat point(s).")
    except Exception as e:
        logger.exception(f"Error writing daily/hourly consumption stats: {e}")

def write_sunrise_sunset_to_influxdb(sun_data, station_id_tag, target_date_obj_local):
    """Writes sunrise and sunset times as full UTC timestamps to InfluxDB."""
    if not INFLUX_CLIENT_AVAILABLE:
        return
    if not sun_data or not sun_data.get("sunriseTime") or not sun_data.get("sunsetTime"):
        logger.info("No valid sunrise/sunset data to write.")
        return
    if not all([INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET]):
        return

    points_to_write = []
    local_tz = _get_local_timezone()
    date_str_for_parsing = target_date_obj_local.strftime("%Y-%m-%d")

    try:
        for event_type_str, time_str_local in [("sunrise", sun_data["sunriseTime"]), ("sunset", sun_data["sunsetTime"])]:
            dt_obj_naive = dateutil_parser.parse(f"{date_str_for_parsing} {time_str_local}")
            dt_obj_local_aware = local_tz.localize(dt_obj_naive)
            dt_obj_utc = dt_obj_local_aware.astimezone(timezone.utc)
            point = Point("solar_events").tag("station_id", station_id_tag).tag("event_type", event_type_str).tag("date_local", date_str_for_parsing).field("time_str_local", time_str_local).time(dt_obj_utc)
            points_to_write.append(point)
    except Exception as e:
        logger.exception(f"Error parsing sunrise/sunset times: {e}")
        return
    
    if not points_to_write:
        return

    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=INFLUX_BUCKET, record=points_to_write)
            logger.debug(f"Successfully wrote {len(points_to_write)} solar event point(s).")
    except Exception as e:
        logger.exception(f"Error writing solar events: {e}")

def write_weather_data_to_influxdb(weather_data, station_id_tag):
    """Writes current weather and hourly forecast to InfluxDB."""
    if not INFLUX_CLIENT_AVAILABLE:
        return
    if not weather_data:
        logger.info("No weather data to write.")
        return
    if not all([INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET]):
        return

    points_to_write = []
    api_response_timezone_str = weather_data.get("timezone", LOCAL_TZ_STR)
    response_tz = pytz.timezone(api_response_timezone_str)

    # Process Current Weather
    current_weather = weather_data.get("current_weather")
    if current_weather and isinstance(current_weather, dict):
        try:
            current_time_naive = datetime.fromisoformat(current_weather.get("time"))
            current_time_local_aware = response_tz.localize(current_time_naive, is_dst=None)
            current_time_utc = current_time_local_aware.astimezone(timezone.utc)

            current_point = Point("weather_current").tag("station_id", station_id_tag).time(current_time_utc)
            field_added = False
            for key, value in current_weather.items():
                if key not in ["time", "interval"] and value is not None:
                    try:
                        current_point = current_point.field(key, float(value))
                        field_added = True
                    except (ValueError, TypeError):
                        if isinstance(value, (str, bool, int)):
                            current_point = current_point.field(key, value)
                            field_added = True
            if field_added:
                points_to_write.append(current_point)
        except Exception as e:
            logger.exception(f"Error processing current weather point: {e}")

    # Process Hourly Forecast Data
    hourly_data = weather_data.get("hourly", {})
    time_array = hourly_data.get("time", [])
    for i, timestamp_str in enumerate(time_array):
        try:
            hourly_dt_naive = datetime.fromisoformat(timestamp_str)
            hourly_dt_local_aware = response_tz.localize(hourly_dt_naive, is_dst=None)
            hourly_dt_utc = hourly_dt_local_aware.astimezone(timezone.utc)

            hourly_point = Point("weather_forecast_hourly").tag("station_id", station_id_tag).time(hourly_dt_utc)
            field_added_hourly = False
            for var_name, value_array in hourly_data.items():
                if var_name != "time" and isinstance(value_array, list) and i < len(value_array):
                    value = value_array[i]
                    if value is not None:
                        try:
                            hourly_point = hourly_point.field(var_name, float(value))
                            field_added_hourly = True
                        except (ValueError, TypeError):
                            if isinstance(value, (str, bool, int)):
                                hourly_point = hourly_point.field(var_name, value)
                                field_added_hourly = True
            if field_added_hourly:
                points_to_write.append(hourly_point)
        except Exception as e:
            logger.exception(f"Error processing hourly weather for {timestamp_str}: {e}")
    
    if not points_to_write:
        logger.info("No valid weather points to write after processing.")
        return
    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=INFLUX_BUCKET, record=points_to_write)
            logger.debug(f"Successfully wrote {len(points_to_write)} weather point(s).")
    except Exception as e:
        logger.exception(f"Error writing weather data: {e}")


def write_sigen_daily_summary_to_influxdb(daily_summary_data, station_id_tag, target_date_obj_local):
    """
    Writes Sigen daily energy summary data (from /statistics/energy endpoint) to InfluxDB.
    target_date_obj_local is the specific day these stats are for.
    """
    if not INFLUX_CLIENT_AVAILABLE:
        return
    if not daily_summary_data:
        logger.info("No daily_summary_data (from /statistics/energy) to write.")
        return
    if not all([INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET]):
        return

    fields_to_log_mapping = {
        "total_home_consumption_kwh": daily_summary_data.get("powerUse"),
        "grid_import_kwh": daily_summary_data.get("powerFromGrid"),
        "grid_export_kwh": daily_summary_data.get("powerToGrid"),
        "pv_generation_kwh": daily_summary_data.get("powerGeneration"),
        "battery_charge_kwh": daily_summary_data.get("esCharging"),
        "battery_discharge_kwh": daily_summary_data.get("esDischarging"),
        "pv_self_consumption_kwh": daily_summary_data.get("powerSelfConsumption"),
        "load_self_sufficiency_kwh": daily_summary_data.get("powerOneself")
    }

    fields_to_write = {}
    valid_point_data_exists = False
    for influx_field_key, api_value in fields_to_log_mapping.items():
        if api_value is not None:
            try:
                fields_to_write[influx_field_key] = float(api_value)
                valid_point_data_exists = True
            except (ValueError, TypeError):
                logger.warning(f"Could not convert '{influx_field_key}':'{api_value}' to float. Skipping.")
    
    if not valid_point_data_exists:
        logger.info("No valid numeric fields in daily_summary_data to write.")
        return

    local_tz = _get_local_timezone()
    daily_timestamp_local_start = local_tz.localize(
        datetime(
            target_date_obj_local.year,
            target_date_obj_local.month,
            target_date_obj_local.day,
            0,
            0,
            0,
        )
    )
    daily_timestamp_utc = daily_timestamp_local_start.astimezone(timezone.utc)

    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            point = (
                Point("sigen_daily_summary")
                .tag("station_id", station_id_tag)
                .tag("source", "sigen_api_stats_energy")
                .time(daily_timestamp_utc)
            )
            for field_name, field_value in fields_to_write.items():
                point = point.field(field_name, field_value)
            write_api.write(bucket=INFLUX_BUCKET, record=point)
            logger.debug(
                f"Successfully wrote sigen_daily_summary data for {target_date_obj_local.strftime('%Y-%m-%d')}."
            )
    except Exception as e:
        logger.exception(f"Error writing sigen_daily_summary data: {e}")
import os
from datetime import datetime, timezone
import pytz # For timezone handling
from dateutil import parser as dateutil_parser # For robust date string parsing
from dotenv import load_dotenv

# Attempt to import InfluxDB client parts, with a fallback for initial setup
try:
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
    INFLUX_CLIENT_AVAILABLE = True
except ImportError:
    INFLUX_CLIENT_AVAILABLE = False
    print("INFLUXDB_WRITER: influxdb-client library not found. Please install it: pip install influxdb-client")
    # Define dummy classes if import fails, so the rest of the file can be parsed
    class Point: pass 

# Load environment variables from .env file
load_dotenv()

# --- InfluxDB Configuration - Loaded from .env ---
INFLUX_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUX_ORG = os.getenv("INFLUXDB_ORG")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET")
LOCAL_TZ_STR = os.getenv("TIMEZONE", "Europe/Dublin") # For parsing local timestamps

# Basic check for essential InfluxDB configurations
if INFLUX_CLIENT_AVAILABLE and (not all([INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET])):
    print("INFLUXDB_WRITER CRITICAL Error: INFLUXDB_TOKEN, INFLUXDB_ORG, or INFLUXDB_BUCKET not found in .env file or environment.")
    print("Data writing to InfluxDB will fail. Please configure these in your .env file.")
    # Consider exiting or raising an exception if this module is imported and config is missing

def _get_local_timezone():
    """Helper to get the local pytz timezone object."""
    try:
        return pytz.timezone(LOCAL_TZ_STR)
    except pytz.exceptions.UnknownTimeZoneError:
        print(f"INFLUXDB_WRITER Warning: Unknown timezone '{LOCAL_TZ_STR}'. Defaulting to UTC.")
        return pytz.utc

def write_energy_flow_to_influxdb(energy_data, station_id_tag):
    """Writes Sigen energy flow data points to InfluxDB."""
    if not INFLUX_CLIENT_AVAILABLE: return
    if not energy_data:
        print("InfluxDB: No energy_flow data provided to write.")
        return
    if not all([INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET]): return # Config check

    fields_to_write = {}
    essential_fields_valid = True
    for key, value in energy_data.items():
        if value is not None:
            try:
                fields_to_write[key] = float(value)
            except (ValueError, TypeError):
                print(f"InfluxDB Warning (EnergyFlow): Could not convert '{key}':'{value}' to float. Skipping.")
                if key in ["pv_power", "load_power", "battery_soc"]:
                    essential_fields_valid = False
    
    if not essential_fields_valid:
        print("InfluxDB Error (EnergyFlow): Critical field was invalid. Aborting write.")
        return
    if not fields_to_write:
        print("InfluxDB: No valid numeric fields in energy_flow data to write.")
        return

    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            point = Point("energy_metrics") \
                .tag("station_id", station_id_tag) \
                .time(datetime.now(timezone.utc)) # Timestamps are UTC

            for field_name, field_value in fields_to_write.items():
                point = point.field(field_name, field_value)
            
            if hasattr(point, '_fields') and not point._fields: # Check internal _fields
                 print("InfluxDB Error (EnergyFlow): Point created with no fields after processing.")
                 return

            write_api.write(bucket=INFLUX_BUCKET, record=point)
            print(f"InfluxDB: Successfully wrote energy_flow data. LP: {point.to_line_protocol()}")
    except Exception as e:
        print(f"InfluxDB Error writing energy_flow data: {e}")
        import traceback
        traceback.print_exc()

def write_daily_consumption_to_influxdb(consumption_data, station_id_tag, target_date_obj_local):
    """Writes Sigen daily total and hourly consumption data to InfluxDB."""
    if not INFLUX_CLIENT_AVAILABLE: return
    if not consumption_data:
        print("InfluxDB: No consumption_data (daily/hourly) to write.")
        return
    if not all([INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET]): return

    points_to_write = []
    local_tz = _get_local_timezone()

    # Daily total consumption
    daily_total = consumption_data.get("baseLoadConsumption")
    if daily_total is not None:
        try:
            daily_ts_local = local_tz.localize(datetime(target_date_obj_local.year, target_date_obj_local.month, target_date_obj_local.day))
            daily_ts_utc = daily_ts_local.astimezone(timezone.utc)
            point_daily = Point("daily_consumption_summary") \
                .tag("station_id", station_id_tag) \
                .tag("source", "sigen_api_stats") \
                .field("total_base_load_kwh", float(daily_total)) \
                .time(daily_ts_utc)
            points_to_write.append(point_daily)
        except (ValueError, TypeError) as e:
            print(f"InfluxDB Warning (DailyConsumption): Could not process total_base_load_kwh '{daily_total}': {e}")

    # Hourly consumption details
    hourly_list = consumption_data.get("consumptionDetailList", [])
    processed_hours = set()
    for item in hourly_list:
        data_time_str = item.get("dataTime") # "YYYYMMDD HH:MM"
        hourly_val = item.get("baseLoadConsumption")
        if data_time_str and hourly_val is not None:
            if data_time_str in processed_hours: continue
            processed_hours.add(data_time_str)
            try:
                dt_obj_naive = dateutil_parser.parse(data_time_str) # Handles "YYYYMMDD HH:MM"
                dt_obj_local_aware = local_tz.localize(dt_obj_naive)
                dt_obj_utc = dt_obj_local_aware.astimezone(timezone.utc)
                
                point_hourly = Point("hourly_consumption") \
                    .tag("station_id", station_id_tag) \
                    .tag("source", "sigen_api_stats") \
                    .field("base_load_kwh", float(hourly_val)) \
                    .time(dt_obj_utc)
                points_to_write.append(point_hourly)
            except (ValueError, TypeError) as e:
                print(f"InfluxDB Warning (HourlyConsumption): Could not process for '{data_time_str}': {e}")
    
    if not points_to_write:
        print("InfluxDB: No valid daily/hourly consumption points to write.")
        return
    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=INFLUX_BUCKET, record=points_to_write)
            print(f"InfluxDB: Successfully wrote {len(points_to_write)} daily/hourly consumption stat point(s).")
    except Exception as e:
        print(f"InfluxDB Error writing daily/hourly consumption stats: {e}")
        import traceback
        traceback.print_exc()

def write_sunrise_sunset_to_influxdb(sun_data, station_id_tag, target_date_obj_local):
    """Writes sunrise and sunset times as full UTC timestamps to InfluxDB."""
    if not INFLUX_CLIENT_AVAILABLE: return
    if not sun_data or not sun_data.get("sunriseTime") or not sun_data.get("sunsetTime"):
        print("InfluxDB: No valid sunrise/sunset data to write.")
        return
    if not all([INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET]): return

    points_to_write = []
    local_tz = _get_local_timezone()
    date_str_for_parsing = target_date_obj_local.strftime("%Y-%m-%d")

    try:
        for event_type_str, time_str_local in [("sunrise", sun_data["sunriseTime"]), ("sunset", sun_data["sunsetTime"])]:
            dt_obj_naive = dateutil_parser.parse(f"{date_str_for_parsing} {time_str_local}")
            dt_obj_local_aware = local_tz.localize(dt_obj_naive)
            dt_obj_utc = dt_obj_local_aware.astimezone(timezone.utc)
            
            point = Point("solar_events") \
                .tag("station_id", station_id_tag) \
                .tag("event_type", event_type_str) \
                .tag("date_local", date_str_for_parsing) \
                .field("time_str_local", time_str_local) \
                .time(dt_obj_utc) # Use the event time as the InfluxDB timestamp
            points_to_write.append(point)
    except Exception as e:
        print(f"InfluxDB Error parsing sunrise/sunset times: {e}")
        return
    
    if not points_to_write: return # Should not happen if parsing was okay

    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=INFLUX_BUCKET, record=points_to_write)
            print(f"InfluxDB: Successfully wrote {len(points_to_write)} solar event point(s).")
    except Exception as e:
        print(f"InfluxDB Error writing solar events: {e}")
        import traceback
        traceback.print_exc()

def write_weather_data_to_influxdb(weather_data, station_id_tag):
    """Writes current weather and hourly forecast to InfluxDB."""
    if not INFLUX_CLIENT_AVAILABLE: return
    if not weather_data:
        print("InfluxDB: No weather data to write.")
        return
    if not all([INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET]): return

    points_to_write = []
    api_response_timezone_str = weather_data.get("timezone", LOCAL_TZ_STR) # Timezone of the API response times
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
            if field_added: points_to_write.append(current_point)
        except Exception as e: print(f"InfluxDB Error processing current weather point: {e}")

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
            if field_added_hourly: points_to_write.append(hourly_point)
        except Exception as e: print(f"InfluxDB Error processing hourly weather for {timestamp_str}: {e}")
    
    if not points_to_write:
        print("InfluxDB: No valid weather points to write after processing.")
        return
    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=INFLUX_BUCKET, record=points_to_write)
            print(f"InfluxDB: Successfully wrote {len(points_to_write)} weather point(s).")
    except Exception as e:
        print(f"InfluxDB Error writing weather data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("--- Testing influxdb_writer.py ---")
    if not INFLUX_CLIENT_AVAILABLE:
        print("InfluxDB client not available. Exiting test.")
    elif not all([INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET]):
        print("InfluxDB connection details not found in .env. Please configure them.")
    else:
        print("Simulating data write. Ensure your .env file has InfluxDB details correctly set up.")
        
        # Example Test Data (replace with actual fetched data in main_scheduler.py)
        test_station_id = os.getenv("SIGEN_STATION_ID", "test_station_001") # Get from .env or default
        
        print("\nTesting energy_flow write...")
        sample_energy_flow = {'pv_power': 1.2, 'load_power': 0.5, 'battery_soc': 80.0, 'grid_flow_power': 0.7, 'battery_power': 0.0}
        write_energy_flow_to_influxdb(sample_energy_flow, test_station_id)

        print("\nTesting daily_consumption write...")
        sample_daily_cons_data = {
            "baseLoadConsumption": 10.5,
            "consumptionDetailList": [
                {"dataTime": "20250514 00:00", "baseLoadConsumption": 0.5},
                {"dataTime": "20250514 01:00", "baseLoadConsumption": 0.4}
            ]
        }
        write_daily_consumption_to_influxdb(sample_daily_cons_data, test_station_id, datetime.now(_get_local_timezone()))
        
        print("\nTesting sunrise/sunset write...")
        sample_sun_data = {"sunriseTime": "06:00 AM", "sunsetTime": "08:30 PM"}
        write_sunrise_sunset_to_influxdb(sample_sun_data, test_station_id, datetime.now(_get_local_timezone()))

        print("\nTesting weather_data write...")
        # (Using a simplified version of the Open-Meteo structure for this direct test)
        sample_weather_data = {
            "timezone": LOCAL_TZ_STR, # Use configured local timezone string
            "current_weather": {"time": datetime.now(_get_local_timezone()).replace(minute=0, second=0, microsecond=0).isoformat(), "temperature": 15.0, "weather_code": 1, "wind_speed_10m": 5.0},
            "hourly": {
                "time": [(datetime.now(_get_local_timezone()).replace(minute=0, second=0, microsecond=0) + timedelta(hours=h)).isoformat() for h in range(2)],
                "temperature_2m": [15.0, 16.0],
                "cloud_cover": [20.0, 30.0],
                "shortwave_radiation": [300.0, 400.0]
            }
        }
        write_weather_data_to_influxdb(sample_weather_data, test_station_id)
        print("\n--- Test finished ---")
import requests
import json
from datetime import datetime, timezone, timedelta
import time
import os

try:
    from auth_handler import get_sigen_bearer_token, refresh_sigen_token, TOKEN_FILE
except ImportError:
    print("Error: Could not import from auth_handler.py. Make sure it's in the same directory.")
    TOKEN_FILE = "sigen_token.json"
    def get_sigen_bearer_token():
        print("CRITICAL STUB: get_sigen_bearer_token() function needs to be properly imported or defined!")
        return None
    def refresh_sigen_token(existing_refresh_token):
        print(f"CRITICAL STUB: refresh_sigen_token() function needs to be properly imported or defined!")
        return None


SIGEN_BASE_URL = "https://api-eu.sigencloud.com"
STATION_ID = ""
SIGEN_ENDPOINT_PATH = "/device/sigen/station/energyflow"
SIGEN_QUERY_PARAMS = f"?id={STATION_ID}&refreshFlag=true"
SIGEN_FULL_URL = f"{SIGEN_BASE_URL}{SIGEN_ENDPOINT_PATH}{SIGEN_QUERY_PARAMS}"

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = ""
INFLUX_ORG = ""
INFLUX_BUCKET = "" 

_current_access_token = None

def load_token_from_file():
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                token_info = json.load(f)
                # Basic validation
                if "access_token" in token_info and "retrieved_at" in token_info and "expires_in" in token_info:
                    return token_info
                else:
                    print(f"Warning: {TOKEN_FILE} is missing required token fields.")
                    return None
    except Exception as e:
        print(f"Error loading token from {TOKEN_FILE}: {e}")
    return None

def save_token_to_file(token_info):
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump(token_info, f, indent=2)
        print(f"Token information updated in {TOKEN_FILE}")
    except IOError as e:
        print(f"Error saving token information to {TOKEN_FILE}: {e}")

def get_active_sigen_access_token():
    global _current_access_token
    token_info = load_token_from_file()
    obtained_new_token_this_cycle = False

    if token_info:
        retrieved_at = token_info.get("retrieved_at", 0)
        expires_in = token_info.get("expires_in", 3600)

        if (retrieved_at + expires_in - 300) > time.time():
            print("Using existing valid access token from file.")
            _current_access_token = token_info["access_token"]
            return _current_access_token
        else:
            print("Access token from file expired or nearing expiry.")
            if token_info.get("refresh_token"):
                print("Attempting to refresh token...")
                new_token_info = refresh_sigen_token(token_info["refresh_token"])
                if new_token_info and "access_token" in new_token_info:
                    token_info = new_token_info
                    obtained_new_token_this_cycle = True
                else:
                    print("Refresh token failed.")
            else:
                print("No refresh token available in file.")
    else:
        print(f"{TOKEN_FILE} not found or invalid. Will attempt full authentication.")

    if not obtained_new_token_this_cycle:
        print("Attempting full re-authentication (username/password method)...")
        token_info = get_sigen_bearer_token()

    if token_info and "access_token" in token_info:
        save_token_to_file(token_info)
        _current_access_token = token_info["access_token"]
        return _current_access_token
    else:
        print("CRITICAL: Failed to obtain a Sigen API access token after all attempts.")
        _current_access_token = None
        return None

def write_to_influxdb(data_points, station_id_tag):
    """Writes data points to InfluxDB."""
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS

    if not data_points:
        print("InfluxDB: No data_points dictionary provided.")
        return

    fields_to_write = {}
    valid_point_data_exists = False
    for key, value in data_points.items():
        if value is not None:
            try:
                fields_to_write[key] = float(value)
                valid_point_data_exists = True
            except (ValueError, TypeError):
                print(f"InfluxDB Warning: Could not convert '{key}':'{value}' to float. Skipping this field.")
        else:
            print(f"InfluxDB Info: Key '{key}' has None value. Skipping this field.")

    if not valid_point_data_exists:
        print("InfluxDB: No valid numeric data found in data_points to write after conversion attempts.")
        return
    

    print(f"InfluxDB: Fields prepared for writing: {fields_to_write}")

    if not fields_to_write:
        print("InfluxDB: fields_to_write dictionary is empty. Nothing to write.")
        return

    try:
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            
            point = Point("energy_metrics") \
                .tag("station_id", station_id_tag) \
                .time(datetime.now(timezone.utc))

            field_added_success = False
            for field_name, field_value in fields_to_write.items():
                point = point.field(field_name, field_value)
                field_added_success = True

            if not field_added_success:
                print("InfluxDB Error: No fields were actually added to the Point object.")
                return

            try:
                line_protocol = point.to_line_protocol()
                if not line_protocol:
                    print("InfluxDB Error: Point generated an empty line protocol string. This means no fields were set.")
                    return
                print(f"InfluxDB: Generated Line Protocol: {line_protocol}")
            except Exception as e_lp:
                print(f"InfluxDB Error: Could not generate line protocol - {e_lp}")
                return

            write_api.write(bucket=INFLUX_BUCKET, record=point)
            print(f"Data successfully written to InfluxDB.")

    except Exception as e:
        print(f"Error writing to InfluxDB: {e}")
        import traceback
        traceback.print_exc()


def fetch_sigen_energy_data_with_auth():
    """Fetches energy flow data from the Sigen API using managed authentication."""
    active_access_token = get_active_sigen_access_token()
    if not active_access_token:
        print("Could not obtain Sigen API token. Aborting data fetch for this cycle.")
        return None

    sigen_api_headers = {
        "Authorization": f"Bearer {active_access_token}",
        "Content-Type": "application/json; charset=utf-8",
        "lang": "en_US",
        "auth-client-id": "sigen",
        "origin": "https://app-eu.sigencloud.com",
        "referer": "https://app-eu.sigencloud.com/",
        "User-Agent": "PythonSigenClient/1.0"
    }

    print(f"Querying Sigen Data API: {SIGEN_FULL_URL}")
    print(f"Using Sigen Access Token (first 10 chars): {active_access_token[:10]}...")

    try:
        response = requests.get(SIGEN_FULL_URL, headers=sigen_api_headers, timeout=15)

        if response.status_code == 401 or response.status_code == 403:
            print(f"Sigen API Auth Error ({response.status_code}). Marking token as potentially expired to force refresh/re-auth on next run.")
            if os.path.exists(TOKEN_FILE):
                token_info = load_token_from_file()
                if token_info:
                    token_info["expires_in"] = 0 # Force expiry
                    token_info["retrieved_at"] = 0
                    save_token_to_file(token_info)
            return None

        response.raise_for_status() 
        api_data = response.json()

        if api_data.get("code") == 0 and api_data.get("msg") == "success":
            data = api_data.get("data", {})
            current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n--- Extracted Sigen Values ({current_time_str}) ---")
            
            extracted_values = {
                "pv_day_nrg": data.get("pvDayNrg"),
                "pv_power": data.get("pvPower"),
                "load_power": data.get("loadPower"),
                "battery_soc": data.get("batterySoc"),
                "grid_flow_power": data.get("buySellPower"),
                "battery_power": data.get("batteryPower")
            }

            for key, value in extracted_values.items():
                unit = "kW"
                if key == "pv_day_nrg": unit = "kWh"
                elif key == "battery_soc": unit = "%"
                print(f"{key.replace('_', ' ').title()}: {value if value is not None else 'N/A'} {unit if value is not None and key != 'battery_soc' else '' if key == 'battery_soc' else ''}")
            return extracted_values
        else:
            print(f"\n--- ERROR: Sigen API (data endpoint) reported an issue ---")
            print(f"API Code: {api_data.get('code')}, Message: {api_data.get('msg')}")
            return None

    except requests.exceptions.HTTPError as http_err:
        print(f"\n--- HTTP error occurred during Sigen data fetch: {http_err} ---")
        if 'response' in locals() and response is not None:
             print(f"Response text: {response.text}")
    except requests.exceptions.RequestException as req_err:
        print(f"\n--- An unexpected error occurred during Sigen data fetch: {req_err} ---")
    except json.JSONDecodeError:
        print(f"\n--- Failed to decode JSON response from Sigen data API. ---")
        if 'response' in locals() and response is not None:
             print(f"Response text: {response.text}")
    return None


if __name__ == "__main__":
    print(f"--- Starting Sigen Data Fetcher ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")
    

    if not INFLUX_TOKEN or INFLUX_TOKEN == "YOUR_INFLUXDB_OPERATOR_API_TOKEN":
        print("CRITICAL: INFLUX_TOKEN is not set in the script. Please update it.")
    else:
        sigen_data_payload = fetch_sigen_energy_data_with_auth()
        
        if sigen_data_payload:
            influx_payload_for_db = {} 
            if sigen_data_payload.get("pv_day_nrg") is not None: influx_payload_for_db["pv_day_nrg"] = sigen_data_payload["pv_day_nrg"]
            if sigen_data_payload.get("pv_power") is not None: influx_payload_for_db["pv_power"] = sigen_data_payload["pv_power"]
            if sigen_data_payload.get("load_power") is not None: influx_payload_for_db["load_power"] = sigen_data_payload["load_power"]
            if sigen_data_payload.get("battery_soc") is not None: influx_payload_for_db["battery_soc"] = sigen_data_payload["battery_soc"]
            if sigen_data_payload.get("grid_flow_power") is not None: influx_payload_for_db["grid_flow_power"] = sigen_data_payload["grid_flow_power"] # Using the renamed key
            if sigen_data_payload.get("battery_power") is not None: influx_payload_for_db["battery_power"] = sigen_data_payload["battery_power"]

            if influx_payload_for_db:
                write_to_influxdb(influx_payload_for_db, STATION_ID) 
            else:
                print("No data extracted from Sigen API to prepare for InfluxDB.")

    print(f"\n--- Sigen Data Fetcher Finished ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")

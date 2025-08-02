import requests
import json
import logging

debug_requests = False

if debug_requests:
    # Enable HTTP request debugging
    try:
        import http.client as http_client
    except ImportError:
        # Python 2
        import httplib as http_client
    http_client.HTTPConnection.debuglevel = 1

    # You must initialize logging, otherwise you'll not see debug output.
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True

    print("SIGEN_API_CLIENT: HTTP request debugging enabled.")

# datetime and pytz might be needed here if we were formatting dates for API calls,
# but target_date_str and target_date_obj_local are prepared by the caller.
# from datetime import datetime
# import pytz

# Constants for Sigen API interaction (can be moved to a config if they vary significantly)
# but paths are usually stable relative to a base URL.
USER_AGENT = "PythonSigenClient/1.0" # Same as in auth_handler

def _create_sigen_headers(active_token, base_url):
    """Helper function to create standard Sigen API headers."""
    referer = base_url.replace('api-','app-')
    if not active_token:
        raise ValueError("Active token is required to create Sigen API headers.")
    return {
        "Authorization": f"Bearer {active_token}",
        "Content-Type": "application/json; charset=utf-8",
        "lang": "en_US",
        "auth-client-id": "sigen", # From previous observations
        "origin": referer,
        "referer": referer,
        "User-Agent": USER_AGENT
    }

def get_sigen_operational_mode(active_token, base_url, station_id):
    endpoint_path = f"/device/setting/operational/mode/{station_id}"
    full_url = f"{base_url}{endpoint_path}"
    headers = _create_sigen_headers(active_token, base_url)
    print(f"SIGEN_API_CLIENT: Querying current Operational Mode: {full_url}")

    try:
        response = requests.get(full_url, headers=headers, timeout=15)
        response.raise_for_status()
        api_data = response.json()

        if api_data.get("code") == 0 and api_data.get("msg") == "success":
            print(f"SIGEN_API_CLIENT: Current operational mode: {api_data.get('data')}.")
            return api_data.get("data")
        else:
            print(f"SIGEN_API_CLIENT ERROR (Query Op Mode): API Code: {api_data.get('code')}, Message: {api_data.get('msg')}")
            return None
    except requests.exceptions.HTTPError as http_err:
        print(f"SIGEN_API_CLIENT HTTP error (Query Op Mode): {http_err}")
        if 'response' in locals() and response is not None: print(f"Response text: {response.text}")
    except requests.exceptions.RequestException as req_err:
        print(f"SIGEN_API_CLIENT Request error (Query Op Mode): {req_err}")
    except json.JSONDecodeError:
        print(f"SIGEN_API_CLIENT Failed to decode JSON (Query Op Mode). Status: {response.status_code if 'response' in locals() else 'N/A'}")
        if 'response' in locals() and response is not None: print(f"Response text: {response.text}")
    return None

def set_sigen_operational_mode(active_token, base_url, station_id, operation_mode):
    endpoint_path = "/device/setting/operational/mode"
    payload = {"operationMode":int(operation_mode),"stationId":int(station_id)}
    full_url = f"{base_url}{endpoint_path}"
    headers = _create_sigen_headers(active_token, base_url)

    print(f"SIGEN_API_CLIENT: Setting station operational mode {full_url} with data {payload}")
    try:
        response = requests.put(full_url, headers=headers, data=json.dumps(payload), timeout=15)
        response.raise_for_status()
        api_data = response.json()

        if api_data.get("code") == 0 and api_data.get("msg") == "success":
            print("SIGEN_API_CLIENT: Successfully set operational mode.")
            return api_data
        else:
            print(f"SIGEN_API_CLIENT ERROR (OpMode): API Code: {api_data.get('code')}, Message: {api_data.get('msg')}")
            return None
    except requests.exceptions.HTTPError as http_err:
        print(f"SIGEN_API_CLIENT HTTP error (OpMode): {http_err}")
        if 'response' in locals() and response is not None: print(f"Response text: {response.text}")
    except requests.exceptions.RequestException as req_err:
        print(f"SIGEN_API_CLIENT Request error (OpMode): {req_err}")
    except json.JSONDecodeError:
        print(f"SIGEN_API_CLIENT Failed to decode JSON (OpMode). Status: {response.status_code if 'response' in locals() else 'N/A'}")
        if 'response' in locals() and response is not None: print(f"Response text: {response.text}")
    return None



def fetch_sigen_energy_flow(active_token, base_url, station_id):
    """Fetches real-time energy flow data from the Sigen API."""
    if not active_token:
        print("SIGEN_API_CLIENT: No active token for energy flow fetch.")
        return None

    endpoint_path = "/device/sigen/station/energyflow"
    query_params_str = f"?id={station_id}&refreshFlag=true"
    full_url = f"{base_url}{endpoint_path}{query_params_str}"
    headers = _create_sigen_headers(active_token, base_url)

    print(f"SIGEN_API_CLIENT: Querying Energy Flow: {full_url}")
    try:
        response = requests.get(full_url, headers=headers, timeout=15)
        response.raise_for_status()
        api_data = response.json()

        if api_data.get("code") == 0 and api_data.get("msg") == "success":
            print("SIGEN_API_CLIENT: Successfully fetched energy flow data.")
            return api_data.get("data")
        else:
            print(f"SIGEN_API_CLIENT ERROR (Energy Flow): API Code: {api_data.get('code')}, Message: {api_data.get('msg')}")
            return None
    except requests.exceptions.HTTPError as http_err:
        print(f"SIGEN_API_CLIENT HTTP error (Energy Flow): {http_err}")
        if 'response' in locals() and response is not None: print(f"Response text: {response.text}")
    except requests.exceptions.RequestException as req_err:
        print(f"SIGEN_API_CLIENT Request error (Energy Flow): {req_err}")
    except json.JSONDecodeError:
        print(f"SIGEN_API_CLIENT Failed to decode JSON (Energy Flow). Status: {response.status_code if 'response' in locals() else 'N/A'}")
        if 'response' in locals() and response is not None: print(f"Response text: {response.text}")
    return None

def fetch_sigen_daily_consumption_stats(active_token, base_url, station_id, target_date_str_api_format):
    """
    Fetches daily and hourly consumption statistics for a given date.
    target_date_str_api_format should be in 'YYYYMMDD' format.
    """
    if not active_token:
        print("SIGEN_API_CLIENT: No active token for daily consumption stats fetch.")
        return None

    endpoint_path = "/data-process/sigen/station/statistics/station-consumption"
    params = {
        "dateFlag": "1",
        "endDate": target_date_str_api_format,
        "startDate": target_date_str_api_format,
        "stationId": station_id
    }
    full_url = f"{base_url}{endpoint_path}"
    headers = _create_sigen_headers(active_token, base_url)

    print(f"SIGEN_API_CLIENT: Querying Daily Consumption Stats: {full_url} with params: {params}")
    try:
        response = requests.get(full_url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        api_data = response.json()

        if api_data.get("code") == 0 and api_data.get("msg") == "success":
            print("SIGEN_API_CLIENT: Successfully fetched daily consumption stats.")
            return api_data.get("data")
        else:
            print(f"SIGEN_API_CLIENT ERROR (Daily Consumption): API Code: {api_data.get('code')}, Message: {api_data.get('msg')}")
            return None
    except requests.exceptions.HTTPError as http_err:
        print(f"SIGEN_API_CLIENT HTTP error (Daily Consumption): {http_err}")
        if 'response' in locals() and response is not None: print(f"Response text: {response.text}")
    except requests.exceptions.RequestException as req_err:
        print(f"SIGEN_API_CLIENT Request error (Daily Consumption): {req_err}")
    except json.JSONDecodeError:
        print(f"SIGEN_API_CLIENT Failed to decode JSON (Daily Consumption). Status: {response.status_code if 'response' in locals() else 'N/A'}")
        if 'response' in locals() and response is not None: print(f"Response text: {response.text}")
    return None

def fetch_sigen_sunrise_sunset(active_token, base_url, station_id, target_date_str_api_format):
    """
    Fetches sunrise and sunset times for a given date.
    target_date_str_api_format should be 'YYYYMMDD'.
    """
    if not active_token:
        print("SIGEN_API_CLIENT: No active token for sunrise/sunset fetch.")
        return None

    endpoint_path = "/device/sigen/device/weather/sun"
    params = {
        "stationId": station_id,
        "date": target_date_str_api_format
    }
    full_url = f"{base_url}{endpoint_path}"
    headers = _create_sigen_headers(active_token, base_url)

    print(f"SIGEN_API_CLIENT: Querying Sunrise/Sunset: {full_url} with params: {params}")
    try:
        response = requests.get(full_url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        api_data = response.json()

        if api_data.get("code") == 0 and api_data.get("msg") == "success":
            print("SIGEN_API_CLIENT: Successfully fetched sunrise/sunset data.")
            return api_data.get("data")
        else:
            print(f"SIGEN_API_CLIENT ERROR (Sunrise/Sunset): API Code: {api_data.get('code')}, Message: {api_data.get('msg')}")
            return None
    except requests.exceptions.HTTPError as http_err:
        print(f"SIGEN_API_CLIENT HTTP error (Sunrise/Sunset): {http_err}")
        if 'response' in locals() and response is not None: print(f"Response text: {response.text}")
    except requests.exceptions.RequestException as req_err:
        print(f"SIGEN_API_CLIENT Request error (Sunrise/Sunset): {req_err}")
    except json.JSONDecodeError:
        print(f"SIGEN_API_CLIENT Failed to decode JSON (Sunrise/Sunset). Status: {response.status_code if 'response' in locals() else 'N/A'}")
        if 'response' in locals() and response is not None: print(f"Response text: {response.text}")
    return None

def fetch_sigen_station_info(active_token, base_url):
    """Fetches station metadata and configuration details."""
    if not active_token:
        print("SIGEN_API_CLIENT: No active token for station info fetch.")
        return None

    endpoint_path = "/device/owner/station/home" # Assuming no extra params needed beyond what's in URL
    full_url = f"{base_url}{endpoint_path}"
    headers = _create_sigen_headers(active_token, base_url)

    print(f"SIGEN_API_CLIENT: Querying Station Info: {full_url}")
    try:
        response = requests.get(full_url, headers=headers, timeout=15)
        response.raise_for_status()
        api_data = response.json()
        if api_data.get("code") == 0 and api_data.get("msg") == "success":
            print("SIGEN_API_CLIENT: Successfully fetched station info.")
            return api_data.get("data")
        else:
            print(f"SIGEN_API_CLIENT ERROR (Station Info): API Code: {api_data.get('code')}, Message: {api_data.get('msg')}")
            return None
    except requests.exceptions.HTTPError as http_err:
        print(f"SIGEN_API_CLIENT HTTP error (Station Info): {http_err}")
        if 'response' in locals() and response is not None: print(f"Response text: {response.text}")
    except requests.exceptions.RequestException as req_err:
        print(f"SIGEN_API_CLIENT Request error (Station Info): {req_err}")
    except json.JSONDecodeError:
        print(f"SIGEN_API_CLIENT Failed to decode JSON (Station Info). Status: {response.status_code if 'response' in locals() else 'N/A'}")
        if 'response' in locals() and response is not None: print(f"Response text: {response.text}")
    return None


if __name__ == '__main__':
    # This block is for testing this module directly.
    # You would need to manually provide a valid token and other details for testing.
    print("--- Testing sigen_api_client.py ---")
    
    # For testing, you'd need to load configs or hardcode them temporarily
    # This requires auth_handler.py to have run and sigen_token.json to exist
    # and a .env file for SIGEN_BASE_URL and STATION_ID (or hardcode them here for test)
    from dotenv import load_dotenv
    load_dotenv()
    
    test_sigen_base_url = os.getenv("SIGEN_BASE_URL", "https://api-eu.sigencloud.com")
    test_station_id = os.getenv("SIGEN_STATION_ID")

    if not test_station_id:
        print("Please set SIGEN_STATION_ID in your .env file for testing.")
    else:
        # --- Test getting an active token (requires auth_handler.py in same dir) ---
        try:
            from auth_handler import get_active_sigen_access_token, TOKEN_FILE
            if not os.path.exists(TOKEN_FILE):
                 print(f"{TOKEN_FILE} not found. Run auth_handler.py first to create it.")
                 exit()
            active_token_for_test = get_active_sigen_access_token()
        except ImportError:
            print("Could not import from auth_handler.py for testing. Place it in the same directory.")
            active_token_for_test = None

        if active_token_for_test:
            print(f"\nUsing token: {active_token_for_test[:10]}... for tests.")

            print("\n--- Testing fetch_sigen_energy_flow ---")
            flow_data = fetch_sigen_energy_flow(active_token_for_test, test_sigen_base_url, test_station_id)
            if flow_data:
                print(f"PV Power from flow: {flow_data.get('pvPower')}")

            from datetime import datetime, timedelta # For test dates
            import pytz
            local_tz = pytz.timezone(os.getenv("TIMEZONE", "Europe/Dublin"))
            test_date_obj = datetime.now(local_tz)
            test_date_str = test_date_obj.strftime("%Y%m%d")

            print(f"\n--- Testing fetch_sigen_daily_consumption_stats for {test_date_str} ---")
            cons_stats = fetch_sigen_daily_consumption_stats(active_token_for_test, test_sigen_base_url, test_station_id, test_date_str)
            if cons_stats:
                print(f"Daily Base Load from stats: {cons_stats.get('baseLoadConsumption')}")

            print(f"\n--- Testing fetch_sigen_sunrise_sunset for {test_date_str} ---")
            sun_stats = fetch_sigen_sunrise_sunset(active_token_for_test, test_sigen_base_url, test_station_id, test_date_str)
            if sun_stats:
                print(f"Sunrise: {sun_stats.get('sunriseTime')}, Sunset: {sun_stats.get('sunsetTime')}")
            
            print(f"\n--- Testing fetch_sigen_station_info ---")
            info_stats = fetch_sigen_station_info(active_token_for_test, test_sigen_base_url)
            if info_stats:
                print(f"Station Name: {info_stats.get('stationName')}, PV Capacity: {info_stats.get('pvCapacity')}")
        else:
            print("\nCould not get active token for testing sigen_api_client.py.")
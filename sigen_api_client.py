import requests
import json
import os
import time
from dotenv import load_dotenv
from logger import get_logger

logger = get_logger(__name__)

# datetime and pytz might be needed here if we were formatting dates for API calls,
# but target_date_str and target_date_obj_local are prepared by the caller.
# from datetime import datetime
# import pytz

# Load env (for __main__ test)
load_dotenv()

# Constants for Sigen API interaction (can be moved to a config if they vary significantly)
USER_AGENT = "PythonSigenClient/1.0" # Same as in auth_handler

def _create_sigen_headers(active_token):
    """Helper function to create standard Sigen API headers."""
    if not active_token:
        raise ValueError("Active token is required to create Sigen API headers.")
    return {
        "Authorization": f"Bearer {active_token}",
        "Content-Type": "application/json; charset=utf-8",
        "lang": "en_US",
        "auth-client-id": "sigen",
        "origin": "https://app-eu.sigencloud.com",
        "referer": "https://app-eu.sigencloud.com/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    }

def fetch_sigen_energy_flow(active_token, base_url, station_id, max_retries=2):
    """Fetches real-time energy flow data from the Sigen API with retry logic."""
    if not active_token:
        logger.warning("No active token for energy flow fetch.")
        return None

    endpoint_path = "/device/sigen/station/energyflow"
    query_params_str = f"?id={station_id}"
    full_url = f"{base_url}{endpoint_path}{query_params_str}"
    headers = _create_sigen_headers(active_token)

    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait_time = 5 * attempt  # Wait 5, 10 seconds between retries
            logger.info(f"Retrying API call in {wait_time} seconds (attempt {attempt + 1}/{max_retries + 1})")
            time.sleep(wait_time)

        logger.info(f"Querying Energy Flow: {full_url}")
        try:
            # Create session with specific settings
            session = requests.Session()
            session.headers.update(headers)

            # Force HTTP/1.1 and disable keep-alive to avoid connection issues
            adapter = requests.adapters.HTTPAdapter()
            session.mount('https://', adapter)

            response = session.get(full_url, timeout=30, stream=False)
            response.raise_for_status()
            api_data = response.json()

            if api_data.get("code") == 0 and api_data.get("msg") == "success":
                logger.debug("Successfully fetched energy flow data.")
                return api_data.get("data")
            else:
                logger.error(f"Energy Flow API error: Code: {api_data.get('code')}, Message: {api_data.get('msg')}")
                return None
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error (Energy Flow): {http_err}")
            if 'response' in locals() and response is not None:
                logger.debug(f"Response text: {response.text}")
            # Don't retry on 4xx errors except 408
            if hasattr(http_err, 'response') and http_err.response is not None:
                if 400 <= http_err.response.status_code < 500 and http_err.response.status_code != 408:
                    break
        except requests.exceptions.Timeout as timeout_err:
            logger.error(f"Timeout error (Energy Flow): {timeout_err}")
            if attempt == max_retries:
                logger.error("Max retries reached for timeout. Giving up.")
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request error (Energy Flow): {req_err}")
            if attempt == max_retries:
                logger.error("Max retries reached for request error. Giving up.")
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON (Energy Flow). Status: {response.status_code if 'response' in locals() else 'N/A'}")
            if 'response' in locals() and response is not None:
                logger.debug(f"Response text: {response.text}")
            break  # Don't retry JSON decode errors
    return None

def fetch_sigen_daily_energy_summary(active_token, base_url, station_id, target_date_str_api_format):
    """
    Fetches daily energy summary (PV gen, grid import/export, total consumption, battery charge/discharge)
    for a given date using the /statistics/energy endpoint.
    target_date_str_api_format should be in 'YYYYMMDD' format.
    """
    if not active_token:
        logger.warning("No active token for daily energy summary fetch.")
        return None

    endpoint_path = "/data-process/sigen/station/statistics/energy"
    params = {
        "dateFlag": "1",
        "endDate": target_date_str_api_format,
        "startDate": target_date_str_api_format,
        "stationId": station_id,
        "fulfill": "false"
    }
    full_url = f"{base_url}{endpoint_path}"
    headers = _create_sigen_headers(active_token)

    logger.info(f"Querying Daily Energy Summary: {full_url} with params: {params}")
    try:
        response = requests.get(full_url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        api_data = response.json()

        if api_data.get("code") == 0 and api_data.get("msg") == "success":
            logger.debug("Successfully fetched daily energy summary.")
            logger.debug(f"Daily Summary Raw Response: {json.dumps(api_data, indent=2)}")
            return api_data.get("data")
        else:
            logger.error(f"Daily Energy Summary API error: Code: {api_data.get('code')}, Message: {api_data.get('msg')}")
            return None
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error (Daily Energy Summary): {http_err}")
        if 'response' in locals() and response is not None:
            logger.debug(f"Response text: {response.text}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error (Daily Energy Summary): {req_err}")
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON (Daily Energy Summary). Status: {response.status_code if 'response' in locals() else 'N/A'}")
        if 'response' in locals() and response is not None:
            logger.debug(f"Response text: {response.text}")
    return None

def fetch_sigen_daily_consumption_stats(active_token, base_url, station_id, target_date_str_api_format):
    """
    Fetches daily and hourly consumption statistics for a given date.
    target_date_str_api_format should be in 'YYYYMMDD' format.
    """
    if not active_token:
        logger.warning("No active token for daily consumption stats fetch.")
        return None

    endpoint_path = "/data-process/sigen/station/statistics/station-consumption"
    params = {
        "dateFlag": "1",
        "endDate": target_date_str_api_format,
        "startDate": target_date_str_api_format,
        "stationId": station_id
    }
    full_url = f"{base_url}{endpoint_path}"
    headers = _create_sigen_headers(active_token)

    logger.info(f"Querying Daily Consumption Stats: {full_url} with params: {params}")
    try:
        response = requests.get(full_url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        api_data = response.json()

        if api_data.get("code") == 0 and api_data.get("msg") == "success":
            logger.debug("Successfully fetched daily consumption stats.")
            return api_data.get("data")
        else:
            logger.error(f"Daily Consumption API error: Code: {api_data.get('code')}, Message: {api_data.get('msg')}")
            return None
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error (Daily Consumption): {http_err}")
        if 'response' in locals() and response is not None:
            logger.debug(f"Response text: {response.text}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error (Daily Consumption): {req_err}")
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON (Daily Consumption). Status: {response.status_code if 'response' in locals() else 'N/A'}")
        if 'response' in locals() and response is not None:
            logger.debug(f"Response text: {response.text}")
    return None

def fetch_sigen_sunrise_sunset(active_token, base_url, station_id, target_date_str_api_format):
    """
    Fetches sunrise and sunset times for a given date.
    target_date_str_api_format should be 'YYYYMMDD'.
    """
    if not active_token:
        logger.warning("No active token for sunrise/sunset fetch.")
        return None

    endpoint_path = "/device/sigen/device/weather/sun"
    params = {
        "stationId": station_id,
        "date": target_date_str_api_format
    }
    full_url = f"{base_url}{endpoint_path}"
    headers = _create_sigen_headers(active_token)

    logger.info(f"Querying Sunrise/Sunset: {full_url} with params: {params}")
    try:
        response = requests.get(full_url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        api_data = response.json()

        if api_data.get("code") == 0 and api_data.get("msg") == "success":
            logger.debug("Successfully fetched sunrise/sunset data.")
            return api_data.get("data")
        else:
            logger.error(f"Sunrise/Sunset API error: Code: {api_data.get('code')}, Message: {api_data.get('msg')}")
            return None
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error (Sunrise/Sunset): {http_err}")
        if 'response' in locals() and response is not None:
            logger.debug(f"Response text: {response.text}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error (Sunrise/Sunset): {req_err}")
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON (Sunrise/Sunset). Status: {response.status_code if 'response' in locals() else 'N/A'}")
        if 'response' in locals() and response is not None:
            logger.debug(f"Response text: {response.text}")
    return None

def fetch_sigen_station_info(active_token, base_url):
    """Fetches station metadata and configuration details."""
    if not active_token:
        logger.warning("No active token for station info fetch.")
        return None

    endpoint_path = "/device/owner/station/home"
    full_url = f"{base_url}{endpoint_path}"
    headers = _create_sigen_headers(active_token)

    logger.info(f"Querying Station Info: {full_url}")
    try:
        response = requests.get(full_url, headers=headers, timeout=15)
        response.raise_for_status()
        api_data = response.json()
        if api_data.get("code") == 0 and api_data.get("msg") == "success":
            logger.debug("Successfully fetched station info.")
            return api_data.get("data")
        else:
            logger.error(f"Station Info API error: Code: {api_data.get('code')}, Message: {api_data.get('msg')}")
            return None
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error (Station Info): {http_err}")
        if 'response' in locals() and response is not None:
            logger.debug(f"Response text: {response.text}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error (Station Info): {req_err}")
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON (Station Info). Status: {response.status_code if 'response' in locals() else 'N/A'}")
        if 'response' in locals() and response is not None:
            logger.debug(f"Response text: {response.text}")
    return None


if __name__ == '__main__':
    logger.info("Testing sigen_api_client.py")
    test_sigen_base_url = os.getenv("SIGEN_BASE_URL", "https://api-eu.sigencloud.com")
    test_station_id = os.getenv("SIGEN_STATION_ID")

    if not test_station_id:
        logger.error("Please set SIGEN_STATION_ID in your .env file for testing.")
    else:
        try:
            from auth_handler import get_active_sigen_access_token, TOKEN_FILE
            if not os.path.exists(TOKEN_FILE):
                logger.error(f"{TOKEN_FILE} not found. Run auth_handler.py first to create it.")
                raise SystemExit(1)
            active_token_for_test = get_active_sigen_access_token()
        except ImportError:
            logger.error("Could not import from auth_handler.py for testing. Place it in the same directory.")
            active_token_for_test = None

        if active_token_for_test:
            logger.info("Testing fetch_sigen_energy_flow")
            flow_data = fetch_sigen_energy_flow(active_token_for_test, test_sigen_base_url, test_station_id)
            if flow_data:
                logger.info(f"PV Power from flow: {flow_data.get('pvPower')}")

            from datetime import datetime
            import pytz
            local_tz = pytz.timezone(os.getenv("TIMEZONE", "Europe/Dublin"))
            test_date_obj = datetime.now(local_tz)
            test_date_str = test_date_obj.strftime("%Y%m%d")

            logger.info(f"Testing fetch_sigen_daily_consumption_stats for {test_date_str}")
            cons_stats = fetch_sigen_daily_consumption_stats(active_token_for_test, test_sigen_base_url, test_station_id, test_date_str)
            if cons_stats:
                logger.info(f"Daily Base Load from stats: {cons_stats.get('baseLoadConsumption')}")

            logger.info("Testing fetch_sigen_sunrise_sunset")
            sun_stats = fetch_sigen_sunrise_sunset(active_token_for_test, test_sigen_base_url, test_station_id, test_date_str)
            if sun_stats:
                logger.info(f"Sunrise: {sun_stats.get('sunriseTime')}, Sunset: {sun_stats.get('sunsetTime')}")
            
            logger.info("Testing fetch_sigen_station_info")
            info_stats = fetch_sigen_station_info(active_token_for_test, test_sigen_base_url)
            if info_stats:
                logger.info(f"Station Name: {info_stats.get('stationName')}, PV Capacity: {info_stats.get('pvCapacity')}")
        else:
            logger.error("Could not get active token for testing sigen_api_client.py.")
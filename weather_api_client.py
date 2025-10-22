import requests
import json
import os
from dotenv import load_dotenv
from logger import get_logger

logger = get_logger(__name__)

# Load environment variables from .env file
load_dotenv()

# --- Open-Meteo Configuration - Loaded from .env or defaults ---
# These will be used if the script is run directly or if functions are called without lat/lon params
DEFAULT_WEATHER_LATITUDE = os.getenv("WEATHER_LATITUDE", "52.638074") # Default to your Sigen station's lat
DEFAULT_WEATHER_LONGITUDE = os.getenv("WEATHER_LONGITUDE", "-8.677346") # Default to your Sigen station's lon
DEFAULT_WEATHER_TIMEZONE = os.getenv("WEATHER_TIMEZONE", "Europe/Dublin") # Your local timezone
OPEN_METEO_API_KEY = os.getenv("OPEN_METEO_API_KEY") # Optional API key for higher rate limits

# Use customer API endpoint if API key is available, otherwise use free tier
OPEN_METEO_API_URL = "https://customer-api.open-meteo.com/v1/forecast" if OPEN_METEO_API_KEY else "https://api.open-meteo.com/v1/forecast"
USER_AGENT_WEATHER = "PythonWeatherClient/1.0"

def fetch_open_meteo_weather_data(latitude=None, longitude=None, timezone_str=None):
    """
    Fetches current weather and hourly forecast from Open-Meteo.
    Uses default lat/lon/timezone from .env if not provided as arguments.
    Returns the full parsed JSON response on success, None on failure.
    """
    lat_to_use = latitude if latitude is not None else DEFAULT_WEATHER_LATITUDE
    lon_to_use = longitude if longitude is not None else DEFAULT_WEATHER_LONGITUDE
    tz_to_use = timezone_str if timezone_str is not None else DEFAULT_WEATHER_TIMEZONE

    if not all([lat_to_use, lon_to_use, tz_to_use]):
        logger.error("Latitude, Longitude, or Timezone not configured or provided.")
        return None

    logger.info(f"Fetching Weather Data from Open-Meteo for Lat: {lat_to_use}, Lon: {lon_to_use}")
    
    params = {
        "latitude": lat_to_use,
        "longitude": lon_to_use,
        "current_weather": "true",
        "hourly": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation_probability,precipitation,weather_code,cloud_cover,shortwave_radiation,direct_radiation,diffuse_radiation,wind_speed_10m,wind_direction_10m",
        "timezone": tz_to_use,
        "forecast_days": 2 # Get today's and tomorrow's hourly forecast
    }

    # Add API key if available
    if OPEN_METEO_API_KEY:
        params["apikey"] = OPEN_METEO_API_KEY
    
    headers = {
        "User-Agent": USER_AGENT_WEATHER
    }

    try:
        response = requests.get(OPEN_METEO_API_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        weather_data = response.json()
        logger.debug("Successfully fetched weather data.")
        return weather_data # Return the full parsed JSON
        
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        if 'response' in locals() and response is not None:
            logger.debug(f"Response text: {response.text}")
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error occurred: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f"Timeout error occurred: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"An unexpected error occurred with the request: {req_err}")
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON weather response. Status: {response.status_code if 'response' in locals() else 'N/A'}")
        if 'response' in locals() and response is not None:
            logger.debug(f"Response text: {response.text}")
    return None

if __name__ == '__main__':
    logger.info("Testing weather_api_client.py")
    
    # Check if essential configs are loaded from .env (for direct testing)
    if not DEFAULT_WEATHER_LATITUDE or not DEFAULT_WEATHER_LONGITUDE or not DEFAULT_WEATHER_TIMEZONE:
        logger.error("Please ensure WEATHER_LATITUDE, WEATHER_LONGITUDE, and WEATHER_TIMEZONE are set in your .env file for testing.")
    else:
        logger.info(f"Using Lat: {DEFAULT_WEATHER_LATITUDE}, Lon: {DEFAULT_WEATHER_LONGITUDE}, Timezone: {DEFAULT_WEATHER_TIMEZONE} for test.")
        data = fetch_open_meteo_weather_data() # Uses defaults from .env
        if data:
            if "current_weather" in data:
                logger.info(f"Current weather time: {data['current_weather'].get('time')}, temp: {data['current_weather'].get('temperature')}°C")
            if "hourly" in data and "time" in data["hourly"] and len(data["hourly"]["time"]) > 0:
                logger.info(f"First hour forecast temp: {data['hourly']['temperature_2m'][0]}°C, cloud: {data['hourly']['cloud_cover'][0]}%")
        else:
            logger.error("Failed to fetch weather data for testing.")
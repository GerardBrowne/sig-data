import requests
import urllib.parse
import time
import json
import os
from dotenv import load_dotenv
from logger import get_logger

logger = get_logger(__name__)

# Load environment variables from .env file
load_dotenv()

# --- Configuration - Read from environment variables ---
SIGEN_USERNAME = os.getenv("SIGEN_USERNAME")
OBSERVED_TRANSFORMED_PASSWORD_STRING_FROM_BROWSER = os.getenv("SIGEN_TRANSFORMED_PASSWORD")

# --- Constants (can be here or also in .env if they might change per user) ---
TOKEN_URL = "https://api-eu.sigencloud.com/auth/oauth/token"
CLIENT_AUTH_BASE_64 = "c2lnZW46c2lnZW4=" # sigen:sigen
USER_AGENT = "PythonSigenClient/1.0" # For API requests
TOKEN_FILE = os.getenv("SIGEN_TOKEN_FILE", "sigen_token.json")      # File to store the current live token

# --- Functions (get_sigen_bearer_token, refresh_sigen_token, load_token_from_file, save_token_to_file, get_active_sigen_access_token) ---

def get_sigen_bearer_token():
    """
    Attempts to retrieve a new Bearer token set (access and refresh) from the Sigen API
    using the username and the observed transformed password from environment variables.
    Returns a dictionary with token info on success, None on failure.
    """
    if not SIGEN_USERNAME or not OBSERVED_TRANSFORMED_PASSWORD_STRING_FROM_BROWSER:
        logger.error("SIGEN_USERNAME or SIGEN_TRANSFORMED_PASSWORD not configured (expected in .env). Cannot attempt initial auth.")
        return None
    try:
        password_to_send_url_encoded = urllib.parse.quote_plus(OBSERVED_TRANSFORMED_PASSWORD_STRING_FROM_BROWSER)
        user_device_id = str(int(time.time() * 1000))

        payload_data = (
            f"username={urllib.parse.quote_plus(SIGEN_USERNAME)}"
            f"&password={password_to_send_url_encoded}"
            f"&scope=server"
            f"&grant_type=password"
            f"&userDeviceId={user_device_id}"
        )
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {CLIENT_AUTH_BASE_64}",
            "User-Agent": USER_AGENT
        }
        logger.info(f"Attempting initial token acquisition from: {TOKEN_URL}")
        response = requests.post(TOKEN_URL, headers=headers, data=payload_data, timeout=15)
        response_json = response.json()
        logger.debug(f"Initial Auth - Response Status Code: {response.status_code}")

        if response.status_code == 200 and response_json.get("code") == 0:
            token_data = response_json.get("data")
            if token_data and "access_token" in token_data:
                logger.info("Initial token acquisition succeeded.")
                return {
                    "access_token": token_data['access_token'],
                    "refresh_token": token_data.get('refresh_token'),
                    "expires_in": token_data.get('expires_in'),
                    "retrieved_at": int(time.time())
                }
        logger.error(f"Initial token acquisition failed. API Code: {response_json.get('code')}, Message: {response_json.get('msg')}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request error during initial token acquisition: {e}")
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from initial token endpoint. Status: {response.status_code if 'response' in locals() else 'N/A'}")
    except Exception as e:
        logger.exception(f"Unexpected error during initial token acquisition: {e}")
    return None

def refresh_sigen_token(existing_refresh_token):
    """
    Attempts to refresh the Sigen API Bearer token using an existing refresh_token.
    Returns a dictionary with new token info on success, None on failure.
    """
    if not existing_refresh_token:
        logger.error("No refresh token provided for refreshing.")
        return None
    if not SIGEN_USERNAME: # Needed for userDeviceId context, though API might not strictly need it for refresh
        logger.error("SIGEN_USERNAME not configured. Cannot attempt refresh (userDeviceId context potentially missing).")
        return None

    try:
        user_device_id = str(int(time.time() * 1000))
        payload_data = (
            f"grant_type=refresh_token"
            f"&refresh_token={urllib.parse.quote_plus(existing_refresh_token)}"
            f"&userDeviceId={user_device_id}"
        )
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {CLIENT_AUTH_BASE_64}",
            "User-Agent": USER_AGENT
        }
        logger.info("Attempting to refresh token...")
        response = requests.post(TOKEN_URL, headers=headers, data=payload_data, timeout=15)
        response_json = response.json()
        logger.debug(f"Refresh - Response Status Code: {response.status_code}")

        if response.status_code == 200 and response_json.get("code") == 0:
            token_data = response_json.get("data")
            if token_data and "access_token" in token_data:
                logger.info("Token refresh succeeded.")
                return {
                    "access_token": token_data['access_token'],
                    "refresh_token": token_data.get('refresh_token'),
                    "expires_in": token_data.get('expires_in'),
                    "retrieved_at": int(time.time())
                }
        logger.error(f"Token refresh failed. API Code: {response_json.get('code')}, Message: {response_json.get('msg')}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request error during token refresh: {e}")
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from refresh token endpoint. Status: {response.status_code if 'response' in locals() else 'N/A'}")
    except Exception as e:
        logger.exception(f"Unexpected error during token refresh: {e}")
    return None

def load_token_from_file():
    """Loads token information from the token file."""
    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r") as f:
                token_info = json.load(f)
                if "access_token" in token_info and "retrieved_at" in token_info and "expires_in" in token_info:
                    return token_info
        logger.warning(f"{TOKEN_FILE} not found or invalid.")
    except Exception as e:
        logger.error(f"Error loading token from {TOKEN_FILE}: {e}")
    return None

def save_token_to_file(token_info):
    """Saves token information to the token file."""
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump(token_info, f, indent=2)
        try:
            os.chmod(TOKEN_FILE, 0o600)
        except Exception as chmod_err:
            logger.warning(f"Could not set permissions on {TOKEN_FILE}: {chmod_err}")
        logger.info(f"Token information updated in {TOKEN_FILE}")
    except IOError as e:
        logger.error(f"Error saving token information to {TOKEN_FILE}: {e}")

def get_active_sigen_access_token():
    """
    Manages Sigen API token, ensuring a valid one is available.
    Loads from file, refreshes if needed, or gets a new one.
    Returns the active access_token string or None.
    """
    token_info = load_token_from_file()
    obtained_new_token_this_cycle = False

    if token_info:
        retrieved_at = token_info.get("retrieved_at", 0)
        expires_in = token_info.get("expires_in", 0) or 0 # Ensure it's a number
        
        # Check if token is expired or close to expiring (e.g., within next 5 minutes (300s) buffer)
        if (retrieved_at + expires_in - 300) > time.time():
            logger.info("Using existing valid access token from file.")
            return token_info["access_token"]
        else:
            logger.info("Access token from file expired or nearing expiry.")
            if token_info.get("refresh_token"):
                logger.info("Attempting to refresh token...")
                new_token_info = refresh_sigen_token(token_info["refresh_token"])
                if new_token_info and "access_token" in new_token_info:
                    token_info = new_token_info # Update with new tokens
                    obtained_new_token_this_cycle = True
                else:
                    logger.error("Refresh token failed.")
            else:
                logger.warning("No refresh token available in file.")
    else:
        logger.info(f"{TOKEN_FILE} not found or invalid. Will attempt full authentication.")

    if not obtained_new_token_this_cycle: # If not obtained by refresh or if no initial token
        logger.info("Attempting full re-authentication (username/password method)...")
        token_info = get_sigen_bearer_token()

    if token_info and "access_token" in token_info:
        save_token_to_file(token_info)
        return token_info["access_token"]
    else:
        logger.critical("Failed to obtain a Sigen API access token after all attempts.")
        return None

if __name__ == "__main__":
    logger.info("Running auth_handler.py directly to get/save initial token")
    if not SIGEN_USERNAME or not OBSERVED_TRANSFORMED_PASSWORD_STRING_FROM_BROWSER:
        logger.error("Please ensure SIGEN_USERNAME and SIGEN_TRANSFORMED_PASSWORD are set in your .env file and loaded.")
    else:
        logger.info(f"Using username: {SIGEN_USERNAME} for initial token.")
        token_info = get_sigen_bearer_token()
        if token_info and token_info.get("access_token"):
            save_token_to_file(token_info)
        else:
            logger.error(f"Failed to retrieve initial token. {TOKEN_FILE} not created/updated by direct run.")
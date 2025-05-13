import requests
import urllib.parse
import time
import json
import os

# --- Configuration - Ensure these are correct ---
SIGEN_USERNAME = "" # Your Sigen account email

# Using the OBSERVED transformed password string as it worked.
OBSERVED_TRANSFORMED_PASSWORD_STRING_FROM_BROWSER = ""

TOKEN_URL = "https://api-eu.sigencloud.com/auth/oauth/token"
# Client ID and Secret for Sigen API (sigen:sigen) Base64 encoded
CLIENT_AUTH_BASE64 = "c2lnZW46c2lnZW4="
USER_AGENT = "PythonSigenClient/1.0"
TOKEN_FILE = "sigen_token.json"

def get_sigen_bearer_token():
    """
    Attempts to retrieve a new Bearer token set (access and refresh) from the Sigen API
    using the username and the observed transformed password.
    Returns a dictionary with token info on success, None on failure.
    """
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
            "Authorization": f"Basic {CLIENT_AUTH_BASE64}",
            "User-Agent": USER_AGENT
        }

        print(f"Attempting initial token acquisition from: {TOKEN_URL}")
        response = requests.post(TOKEN_URL, headers=headers, data=payload_data, timeout=15)

        print(f"Initial Auth - Response Status Code: {response.status_code}")
        response_json = response.json()
        print("Initial Auth - Response JSON:")
        print(json.dumps(response_json, indent=2))

        if response.status_code == 200 and response_json.get("code") == 0:
            token_data = response_json.get("data")
            if token_data and "access_token" in token_data:
                print("--- INITIAL TOKEN SUCCESS! ---")
                return {
                    "access_token": token_data['access_token'],
                    "refresh_token": token_data.get('refresh_token'),
                    "expires_in": token_data.get('expires_in'),
                    "retrieved_at": int(time.time())
                }
            else:
                print("--- INITIAL TOKEN FAILED: 'access_token' not found in data object. ---")
                return None
        else:
            print("--- INITIAL TOKEN FAILED: API reported an error. ---")
            print(f"API Code: {response_json.get('code')}, Message: {response_json.get('msg')}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"An HTTP request error occurred during initial token acquisition: {e}")
        return None
    except json.JSONDecodeError:
        print("Failed to decode JSON response from initial token endpoint.")
        print(f"Response text: {response.text if 'response' in locals() else 'No response object'}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during initial token acquisition: {e}")
        return None

def refresh_sigen_token(existing_refresh_token):
    """
    Attempts to refresh the Sigen API Bearer token using an existing refresh_token.
    Returns a dictionary with new token info on success, None on failure.
    """
    if not existing_refresh_token:
        print("Error: No refresh token provided for refreshing.")
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
            "Authorization": f"Basic {CLIENT_AUTH_BASE64}",
            "User-Agent": USER_AGENT
        }

        print(f"\nAttempting to refresh token using refresh_token: {existing_refresh_token[:10]}...")
        response = requests.post(TOKEN_URL, headers=headers, data=payload_data, timeout=15)

        print(f"Refresh - Response Status Code: {response.status_code}")
        response_json = response.json()
        print("Refresh - Response JSON:")
        print(json.dumps(response_json, indent=2))

        if response.status_code == 200 and response_json.get("code") == 0:
            token_data = response_json.get("data")
            if token_data and "access_token" in token_data:
                print("--- TOKEN REFRESH SUCCESS! ---")
                return {
                    "access_token": token_data['access_token'],
                    "refresh_token": token_data.get('refresh_token'), # API might return a new refresh token
                    "expires_in": token_data.get('expires_in'),
                    "retrieved_at": int(time.time())
                }
            else:
                print("--- REFRESH FAILED: 'access_token' not found in data object. ---")
                return None
        else:
            print("--- REFRESH FAILED: API reported an error. ---")
            print(f"API Code: {response_json.get('code')}, Message: {response_json.get('msg')}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"An HTTP request error occurred during token refresh: {e}")
        return None
    except json.JSONDecodeError:
        print("Failed to decode JSON response from token refresh endpoint.")
        print(f"Response text: {response.text if 'response' in locals() else 'No response object'}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during token refresh: {e}")
        return None

if __name__ == "__main__":
    print("Attempting to acquire and save initial Sigen API token...")
    if not SIGEN_USERNAME or SIGEN_USERNAME == "your_sigen_email@example.com": # Basic check
        print("Please update SIGEN_USERNAME in the auth_handler.py script.")
    else:
        token_info = get_sigen_bearer_token()
        if token_info and token_info.get("access_token"):
            try:
                with open(TOKEN_FILE, "w") as f:
                    json.dump(token_info, f, indent=2)
                print(f"Token information saved to {TOKEN_FILE}")
            except IOError as e:
                print(f"Error saving token information to {TOKEN_FILE}: {e}")
        else:
            print(f"Failed to retrieve initial token. {TOKEN_FILE} not created/updated.")

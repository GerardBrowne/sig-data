import requests
import urllib.parse
import time
import json

# --- Configuration Section ---
SIGEN_USERNAME = "" # Your Sigen account email

OBSERVED_TRANSFORMED_PASSWORD_STRING_FROM_BROWSER = ""
password_to_send_url_encoded = urllib.parse.quote_plus(OBSERVED_TRANSFORMED_PASSWORD_STRING_FROM_BROWSER)

# --- Advanced Settings (Usually no need to change) ---
TOKEN_URL = "https://api-eu.sigencloud.com/auth/oauth/token"
CLIENT_AUTH_BASE64 = "c2lnZW46c2lnZW4=" # sigen:sigen
# --- End Configuration Section ---

def get_sigen_bearer_token():
    """
    Attempts to retrieve a Bearer token from the Sigen API.
    Returns a dictionary with 'access_token' and 'refresh_token' on success, None on failure.
    """
    try:
        user_device_id = str(int(time.time() * 1000))
        payload_data = f"username={urllib.parse.quote_plus(SIGEN_USERNAME)}&password={password_to_send_url_encoded}&scope=server&grant_type=password&userDeviceId={user_device_id}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {CLIENT_AUTH_BASE64}",
            "User-Agent": "PythonSigenClient/1.0"
        }

        print(f"Attempting to get token from: {TOKEN_URL}")
        # (Optional: print payload details, masking password if needed for logs)

        response = requests.post(TOKEN_URL, headers=headers, data=payload_data, timeout=15)
        
        print(f"Response Status Code: {response.status_code}")
        response_json = response.json() # Assume it's always JSON based on observed behavior
        print("Response JSON:")
        print(json.dumps(response_json, indent=2))

        if response.status_code == 200 and response_json.get("code") == 0 and response_json.get("msg") == "success":
            token_data = response_json.get("data")
            if token_data and "access_token" in token_data:
                print("\n--- SUCCESS! ---")
                print(f"Access Token (first 10 chars): {token_data['access_token'][:10]}...")
                print(f"Refresh Token (first 10 chars): {token_data.get('refresh_token', 'N/A')[:10]}...")
                print(f"Expires In: {token_data.get('expires_in')} seconds")
                return {
                    "access_token": token_data['access_token'],
                    "refresh_token": token_data.get('refresh_token'),
                    "expires_in": token_data.get('expires_in'),
                    "retrieved_at": int(time.time()) # Store retrieval time
                }
            else:
                print("\n--- FAILED: 'access_token' not found in data object or data object missing. ---")
                return None
        else:
            print("\n--- FAILED: API reported an error or unexpected structure. ---")
            print(f"API Code: {response_json.get('code')}, Message: {response_json.get('msg')}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"An HTTP request error occurred: {e}")
        return None
    except json.JSONDecodeError:
        print("Failed to decode JSON response from token endpoint.")
        print(f"Response text: {response.text if 'response' in locals() else 'No response object'}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

if __name__ == "__main__":
    TOKEN_FILE = "sigen_token.json" # Define the file to store token info

    print("Requesting Sigen API Bearer Token...")
    if not SIGEN_USERNAME or SIGEN_USERNAME == "your_sigen_email@example.com":
        print("Please update SIGEN_USERNAME in the script.")
    else:
        token_info = get_sigen_bearer_token()
        if token_info and token_info.get("access_token"):
            print(f"\nToken successfully retrieved. Saving to {TOKEN_FILE}...")
            try:
                with open(TOKEN_FILE, "w") as f:
                    json.dump(token_info, f, indent=2)
                print(f"Token information saved to {TOKEN_FILE}")
            except IOError as e:
                print(f"Error saving token information to {TOKEN_FILE}: {e}")
        else:
            print("\nFailed to retrieve or parse a new token. Please check the output above.")

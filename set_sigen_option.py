import os
import time
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
import argparse

# --- Load Configuration from .env file ---
load_dotenv()

# Sigen specific (used to pass to sigen_api_client functions)
SIGEN_STATION_ID = os.getenv("SIGEN_STATION_ID")
SIGEN_BASE_URL = os.getenv("SIGEN_BASE_URL")

# --- Import your custom modules ---
# These should be in the same directory or your Python path
try:
    from auth_handler import get_active_sigen_access_token
    from sigen_api_client import (
        fetch_sigen_energy_flow,
        fetch_sigen_daily_consumption_stats,
        fetch_sigen_sunrise_sunset,
        fetch_sigen_station_info,
        get_sigen_operational_mode,
        set_sigen_operational_mode
    )
except ImportError as e:
    print(f"SIGEN UPDATE CRITICAL Error: Could not import one or more modules: {e}")
    print("Ensure auth_handler.py, sigen_api_client.py, weather_api_client.py, and influxdb_writer.py are present.")
    exit()


def run_tasks():
    parser = argparse.ArgumentParser()

    parser.add_argument('--query-opmode', '-q', dest='opmodeq', action='store_true', help="Query current operational mode.")
    parser.add_argument('--set-opmode', '-s', dest='opmodes', type=str, help="Set operational mode. 0 = self consumption, 2 = time based schedule")
    args = parser.parse_args()

    # 1. Get Active Sigen API Token
    # This function now handles loading, checking expiry, refreshing, or full re-auth
    active_sigen_token = get_active_sigen_access_token()

    if not active_sigen_token:
        print("SIGEN UPDATE: Failed to obtain Sigen API token.")
        exit
    else:
        if(args.opmodes):
            # ensure opmode is either 'X' or 'Y'

            if args.opmodes not in ['0', '2']:
                print("Invalid operational mode. 0 = self consumption, 2 = time based schedule.")
                exit()
            else:
                # set the sigen opmode via API
                set_sigen_operational_mode(active_sigen_token, SIGEN_BASE_URL, SIGEN_STATION_ID, args.opmodes)

        if(args.opmodeq):

                # query the sigen opmode via API
                get_sigen_operational_mode(active_sigen_token, SIGEN_BASE_URL, SIGEN_STATION_ID)

    print("SIGEN UPDATE: Script terminated.")

if __name__ == "__main__":
    # Basic check for essential Sigen configurations from .env needed by sigen_api_client
    if not SIGEN_STATION_ID:
        print("SIGEN UPDATE CRITICAL Error: SIGEN_STATION_ID not found in .env file or environment.")
        print("Please configure this in your .env file.")
        exit()
    
    run_tasks()
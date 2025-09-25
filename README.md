# Sigen Solar Monitoring System

A comprehensive Kubernetes-native application for monitoring Sigen solar inverter systems, integrating weather data, storing metrics in InfluxDB, and providing rich Grafana visualizations.

**Disclaimer:** This project interacts with an unofficial Sigen API by reverse-engineering web application calls. Sigen may change their API at any time without notice, which could break these scripts. Use at your own risk.

## Features

* Fetches real-time energy flow data (PV power, load, grid, battery power, SOC).
* Fetches daily and hourly consumption statistics from the Sigen API.
* Fetches daily sunrise/sunset times from the Sigen API.
* Fetches current and hourly forecast weather data from Open-Meteo.
* Automated Sigen API Bearer token acquisition and refresh.
* Stores data in InfluxDB v2.x.
* Includes a pre-configured Grafana dashboard JSON for visualization.
* Scheduled data collection using `cron`.
* Centralized structured logging via `logger.py` (configure with LOG_LEVEL/LOG_FILE env vars).

## Prerequisites

* Python 3.8+
* InfluxDB v2.x installed and running.
* Grafana installed and running.
* Access to your Sigen solar system via the MySigen web portal/app.
* `pip` for Python package installation.
* (Optional, for macOS users) Homebrew for easier installation of InfluxDB/Grafana.

## Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/GerardBrowne/sig-data.git](https://github.com/GerardBrowne/sig-data.git)
    cd sig-data
    ```

2.  **Python Virtual Environment & Dependencies:**
    It's highly recommended to use a Python virtual environment.
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On macOS/Linux
    # .\\venv\\Scripts\\activate # On Windows
    pip install -r requirements.txt
    ```
    *(You will need to create the `requirements.txt` file by running `pip freeze > requirements.txt` in your activated virtual environment after installing all necessary packages like `requests`, `influxdb-client`, `python-dotenv`, `pytz`, `python-dateutil`)*

3.  **InfluxDB Setup:**
    * Ensure InfluxDB v2.x is installed and running (e.g., `brew install influxdb` and `brew services start influxdb` on macOS).
    * Access the InfluxDB UI (usually `http://localhost:8086`).
    * Perform the initial setup: create a username, password, an **Organization** (e.g., "SigenSolar"), and a **Bucket** (e.g., "energy_metrics").
    * **Crucially, save the InfluxDB Operator API Token** generated during setup. You will need this for the `.env` file.

4.  **Grafana Setup:**
    * Ensure Grafana is installed and running (e.g., `brew install grafana` and `brew services start grafana` on macOS).
    * Access Grafana (usually `http://localhost:3000`) and log in (default: admin/admin, change password on first login).
    * Later, you will configure the InfluxDB data source and import the dashboard.

5.  **Sigen API Credentials & Configuration (`.env` file):**
    This is the most critical step for allowing the scripts to authenticate with the Sigen API.
    * Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    * **Edit the `.env` file** with your specific details. This file is **not** committed to GitHub (it should be in your `.gitignore` file).

        **`.env` file content:**
        ```env
        # Sigen API Credentials (for auth_handler.py)
        SIGEN_USERNAME="your_actual_sigen_login_email@example.com"
        SIGEN_TRANSFORMED_PASSWORD="the_special_password_string_you_capture_below"
        SIGEN_STATION_ID="your_sigen_station_id"

        # Sigen API Config (for sigen_api_client.py, often loaded in main_scheduler.py)
        SIGEN_BASE_URL="https://api-eu.sigencloud.com"

        # Weather API Config (for weather_api_client.py)
        WEATHER_LATITUDE="your_latitude" 
        WEATHER_LONGITUDE="your_longitude"
        WEATHER_TIMEZONE="Europe/Dublin"    # For Open-Meteo API requests

        # InfluxDB Configuration (for influxdb_writer.py)
        INFLUXDB_URL="http://localhost:8086"
        INFLUXDB_TOKEN="your_long_influxdb_api_token_here"
        INFLUXDB_ORG="YourInfluxDBOrgName" # e.g., SigenSolar
        INFLUXDB_BUCKET="YourInfluxDBBucketName" # e.g., energy_metrics

        # General (for date/time functions)
        TIMEZONE="Europe/Dublin"
        ```

    * **How to get `SIGEN_TRANSFORMED_PASSWORD`:**
        This is the most complex manual step. The Sigen web app transforms your actual password in the browser before sending it. You need to capture this transformed value:
        1.  Open your web browser (e.g., Chrome, Firefox).
        2.  Go to the MySigen web portal login page (likely `https://app-eu.sigencloud.com` or similar for your region).
        3.  Open **Developer Tools** (usually by pressing F12, or right-click -> Inspect).
        4.  Switch to the **"Network"** tab in Developer Tools. Check the box for **"Preserve log"** (or "Persist logs").
        5.  Now, enter your Sigen username and your normal Sigen password into the login form on the webpage and click the "Login" button.
        6.  After the login attempt (successful or not, though you need it to be successful for the right request to be made), look through the list of network requests in the Developer Tools.
        7.  Find the request made to `https://api-eu.sigencloud.com/auth/oauth/token`. It will likely be a `POST` request.
        8.  Click on this request.
        9.  Look for the **"Payload," "Form Data," or "Request"** tab for this request.
        10. You will see the data that was sent. Find the field named `password`. Its value will be a long string, possibly URL-encoded
        11. **Copy the value of this `password` field.**
            * If it contains URL-encoded characters like `%2B` (for `+`) or `%3D` (for `=`), you should store the *decoded* version in your `.env` file. The Python script (`auth_handler.py`) uses `urllib.parse.quote_plus()` which will correctly re-encode it if needed for the HTTP request body.
        12. Paste this (decoded if necessary) string as the value for `SIGEN_TRANSFORMED_PASSWORD` in your `.env` file.

## Running the Scripts

1.  **Initial Sigen API Token Generation:**
    Before the automated data fetching can work, you need an initial `sigen_token.json` file.
    * Make sure your `.env` file is correctly populated with `SIGEN_USERNAME` and `SIGEN_TRANSFORMED_PASSWORD`.
    * Run the `auth_handler.py` (or `get_sigen_token.py` if you named it that) script once:
        ```bash
        # (Ensure your virtual environment is active: source venv/bin/activate)
        python3 auth_handler.py
        ```
    * This should create/update `sigen_token.json` with a valid access and refresh token.

2.  **Automated Data Fetching (`main_scheduler.py`):**
    * This script is designed to be run regularly by a scheduler like `cron`.
    * Ensure your `.env` file contains all necessary configurations (Sigen details, InfluxDB details, Weather details).
    * **Manual Test:**
        ```bash
        python3 main_scheduler.py
        ```
        Check its output for errors and verify data appears in InfluxDB.
    * **Setup with `cron` (macOS/Linux):**
        1.  Edit your crontab: `crontab -e`
        2.  Add a line to run the script every minute (adjust path as needed):
            ```cron
            * * * * * /full/path/to/your/venv/bin/python3 /full/path/to/your/sigensolar/main_scheduler.py >> /full/path/to/your/sigensolar/cron.log 2>&1
            ```
            *(Replace `/full/path/to/your/...` with the actual absolute paths).*

## Quickstart (macOS)

- python3 -m venv venv && source venv/bin/activate
- pip install -r requirements.txt
- cp .env.example .env && edit .env
- python3 auth_handler.py
- python3 main_scheduler.py

## Housekeeping

- A `.gitignore` is included to avoid committing secrets (e.g., `.env`, `sigen_token.json`) and logs.
- `sigen_token.json` permissions are set to 600 on write when possible.

## Grafana Dashboard

1.  **Add InfluxDB Data Source in Grafana:**
    * Go to Grafana (`http://localhost:3000`).
    * Configuration -> Data Sources -> Add data source.
    * Select "InfluxDB".
    * **Query Language:** Set to **Flux**.
    * **HTTP URL:** `http://localhost:8086` (if InfluxDB is on the same machine).
    * **InfluxDB Details:**
        * **Organization:** Your InfluxDB Org name (from your `.env` file).
        * **Token:** Your InfluxDB API Token (from your `.env` file).
        * **Default Bucket:** Your InfluxDB Bucket name (from your `.env` file).
    * Click "Save & Test."

2.  **Import Dashboard JSON:**
    * In Grafana, click the "+" icon in the sidebar -> "Import".
    * Upload the `YourDashboardName.json` file provided in this repository, or paste the JSON content directly.
    * Select your InfluxDB data source when prompted.
    * Click "Import."

## Docker

Build image:

```bash
docker build -t sig-data:latest .
```

Run one-off to fetch/refresh token (mount a volume to persist token file):

```bash
docker run --rm \
  -e SIGEN_USERNAME="..." \
  -e SIGEN_TRANSFORMED_PASSWORD="..." \
  -e SIGEN_STATION_ID="..." \
  -e INFLUXDB_URL="http://influxdb:8086" \
  -e INFLUXDB_TOKEN="..." \
  -e INFLUXDB_ORG="..." \
  -e INFLUXDB_BUCKET="..." \
  -e SIGEN_BASE_URL="https://api-eu.sigencloud.com" \
  -e TIMEZONE="Europe/Dublin" \
  -e WEATHER_LATITUDE="..." -e WEATHER_LONGITUDE="..." -e WEATHER_TIMEZONE="Europe/Dublin" \
  -e LOG_LEVEL=INFO \
  -e SIGEN_TOKEN_FILE=/data/sigen_token.json \
  -v $(pwd)/data:/data \
  sig-data:latest \
  python auth_handler.py
```

Run scheduler (uses same mounted volume for token/logs):

```bash
docker run -d --name sig-data \
  -e SIGEN_USERNAME="..." \
  -e SIGEN_TRANSFORMED_PASSWORD="..." \
  -e SIGEN_STATION_ID="..." \
  -e INFLUXDB_URL="http://influxdb:8086" \
  -e INFLUXDB_TOKEN="..." \
  -e INFLUXDB_ORG="..." \
  -e INFLUXDB_BUCKET="..." \
  -e SIGEN_BASE_URL="https://api-eu.sigencloud.com" \
  -e TIMEZONE="Europe/Dublin" \
  -e WEATHER_LATITUDE="..." -e WEATHER_LONGITUDE="..." -e WEATHER_TIMEZONE="Europe/Dublin" \
  -e LOG_LEVEL=INFO \
  -e SIGEN_TOKEN_FILE=/data/sigen_token.json \
  -v $(pwd)/data:/data \
  sig-data:latest
```

Run with your existing InfluxDB/Grafana (app only):

```bash
docker compose up -d sig-data
```

Run full stack with provisioning (InfluxDB + Grafana + app):

```bash
docker compose --profile stack up -d
```

- Place your existing dashboard JSON files in `grafana/dashboards/` before starting; they will be auto-imported.
- Grafana admin: user `${GRAFANA_USER:-admin}`, password `${GRAFANA_PASSWORD:-admin}` at http://localhost:3000
- InfluxDB UI: http://localhost:8086 (init creds from compose env vars)

## Kubernetes

1) Build and make the image available to your cluster (examples):
- Local kind/minikube: docker build -t sig-data:latest . && kind load docker-image sig-data:latest
- Remote cluster: docker build -t <registry>/sig-data:latest . && docker push <registry>/sig-data:latest (then set image in k8s/sig-data.yaml)

2) Apply manifests (edit secrets first):
- kubectl apply -f k8s/namespace.yaml
- Edit k8s/secret-sig-data.yaml and fill SIGEN_* and passwords
- kubectl apply -f k8s/secret-sig-data.yaml
- kubectl apply -f k8s/configmap-sig-data.yaml
- kubectl apply -f k8s/influxdb.yaml
- kubectl apply -f k8s/grafana-provisioning-configmaps.yaml
- kubectl apply -f k8s/grafana.yaml
- kubectl apply -f k8s/sig-data.yaml

3) Access UIs (port-forward):
- kubectl -n sig-data port-forward svc/grafana 3000:3000
- kubectl -n sig-data port-forward svc/influxdb 8086:8086

Notes:
- The app writes token/logs to a PVC mounted at /data.
- Grafana auto-provisions an InfluxDB datasource; drop your dashboard JSONs into grafana/dashboards and import via UI, or create a ConfigMap to mount them.

## Helm

Package is in `charts/sig-data`.

Examples:
- Full stack:
  helm install my-sig ./charts/sig-data \
    --set secrets.sigenUsername=me@example.com \
    --set secrets.sigenTransformedPassword=... \
    --set secrets.sigenStationId=... \
    --set influxdb.token=changeme

- App only (use existing InfluxDB/Grafana):
  helm install my-sig ./charts/sig-data \
    --set influxdb.enabled=false \
    --set grafana.enabled=false \
    --set externalInfluxUrl=http://influxdb.default:8086 \
    --set influxdb.org=yourOrg --set influxdb.bucket=yourBucket --set influxdb.token=...

## Important Notes

* **Sigen API Changes:** The Sigen API is not officially documented for this use. If Sigen changes their API endpoints or authentication mechanism, these scripts will likely break.
* **`SIGEN_TRANSFORMED_PASSWORD` Updates:** If you change your actual Sigen account password, or if Sigen changes their client-side password transformation logic, the `SIGEN_TRANSFORMED_PASSWORD` value in your `.env` file will become invalid. You would then need to recapture it using the browser developer tools method described above. The `refresh_token` mechanism should reduce the frequency of needing to use this transformed password.
* **Security:** Keep your `.env` file and `sigen_token.json` file secure and **never commit them to GitHub.**

---
Remember to replace placeholder URLs/usernames in the "Clone the Repository" section with your actual GitHub details.
You'll also need to create the `.env.example` file and the `requirements.txt` file.
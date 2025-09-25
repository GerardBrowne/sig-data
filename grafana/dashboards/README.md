Place your existing Grafana dashboard JSON files in this folder.
They will be auto-imported on container start via provisioning.

- Ensure the dashboard queries use the provisioned datasource name: InfluxDB
- Changes in this folder are watched and reloaded automatically.

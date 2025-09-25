# Kubernetes Deployment Guide

This guide will help you deploy the Sigen Solar Data monitoring system to Kubernetes.

## Prerequisites

1. **Kubernetes cluster** with kubectl configured
2. **Docker** installed for building images
3. **Container registry access** (Docker Hub, ECR, GCR, etc.)
4. **Sigen credentials** (see setup below)

## Quick Start

1. **Configure the deployment script:**
   ```bash
   # Edit deploy-k8s.sh and update the REGISTRY variable
   vim deploy-k8s.sh
   # Change: REGISTRY="your-registry"
   # To: REGISTRY="docker.io/yourusername"  # or your registry
   ```

2. **Configure your secrets:**
   ```bash
   # Edit the secrets file with your Sigen credentials
   vim k8s/secret-sig-data.yaml
   ```

3. **Deploy everything:**
   ```bash
   ./deploy-k8s.sh all
   ```

## Detailed Setup

### Step 1: Gather Your Sigen Credentials

You'll need these values from your Sigen account:

#### Sigen Username
Your Sigen account email address.

#### Sigen Station ID
1. Log into your Sigen web portal
2. Look at the URL or account settings for your station ID
3. It's typically a numeric ID

#### Sigen Transformed Password
This is the most complex step - you need to capture the transformed password from your browser:

1. Open Chrome/Firefox Developer Tools (F12)
2. Go to the **Network** tab
3. Check **"Preserve log"**
4. Go to the Sigen login page
5. Enter your username and password, click Login
6. Look for a POST request to `https://api-eu.sigencloud.com/auth/oauth/token`
7. Click on this request → **Payload/Form Data** tab
8. Copy the value of the `password` field (it will be a long encoded string)
9. If URL-encoded (has %20, %3D etc), decode it first

### Step 2: Configure Secrets

Edit `k8s/secret-sig-data.yaml`:

```yaml
stringData:
  SIGEN_USERNAME: "your-email@example.com"
  SIGEN_TRANSFORMED_PASSWORD: "your-captured-password-string"
  SIGEN_STATION_ID: "your-station-id"
  INFLUXDB_TOKEN: "your-secure-token"  # Change from default
  INFLUXDB_USERNAME: "admin"
  INFLUXDB_PASSWORD: "your-secure-password"  # Change from default
  GRAFANA_USER: "admin"
  GRAFANA_PASSWORD: "your-secure-password"  # Change from default
```

### Step 3: Configure Location (Optional)

Edit `k8s/configmap-sig-data.yaml` to update your location coordinates:

```yaml
data:
  WEATHER_LATITUDE: "your-latitude"    # e.g., "52.638074"
  WEATHER_LONGITUDE: "your-longitude"  # e.g., "-8.677346"
  WEATHER_TIMEZONE: "your-timezone"    # e.g., "Europe/Dublin"
```

### Step 4: Configure Container Registry

Edit `deploy-k8s.sh` and update the registry settings:

```bash
# For Docker Hub:
REGISTRY="docker.io/yourusername"

# For Google Container Registry:
REGISTRY="gcr.io/your-project-id"

# For Amazon ECR:
REGISTRY="123456789.dkr.ecr.region.amazonaws.com"
```

### Step 5: Deploy

Run the deployment script:

```bash
# Check prerequisites
./deploy-k8s.sh check

# Build and push image (do this first)
./deploy-k8s.sh build

# Deploy to Kubernetes
./deploy-k8s.sh deploy

# Check status
./deploy-k8s.sh status
```

Or run everything at once:

```bash
./deploy-k8s.sh all
```

## Accessing the Services

### Grafana Dashboard

```bash
# Port forward to access Grafana
kubectl port-forward svc/grafana 3000:3000 -n sig-data

# Visit http://localhost:3000
# Login with admin/admin (or your configured password)
```

### InfluxDB UI

```bash
# Port forward to access InfluxDB
kubectl port-forward svc/influxdb 8086:8086 -n sig-data

# Visit http://localhost:8086
```

### View Application Logs

```bash
# View real-time logs
kubectl logs -f deployment/sig-data -n sig-data

# View recent logs
kubectl logs deployment/sig-data -n sig-data --tail=100
```

## Monitoring & Troubleshooting

### Check Pod Status

```bash
kubectl get pods -n sig-data
```

### Describe Failing Pods

```bash
kubectl describe pod <pod-name> -n sig-data
```

### Check Events

```bash
kubectl get events -n sig-data --sort-by='.lastTimestamp'
```

### Restart Application

```bash
kubectl rollout restart deployment/sig-data -n sig-data
```

## Storage & Persistence

The deployment creates persistent volumes for:

- **InfluxDB data**: 10Gi for time-series data
- **Grafana storage**: 5Gi for dashboards and settings
- **Application data**: 1Gi for tokens and logs

## Security Considerations

1. **Change default passwords** in the secrets file
2. **Use strong tokens** for InfluxDB
3. **Enable RBAC** if your cluster supports it
4. **Use network policies** to restrict traffic between pods
5. **Keep your secrets file secure** and never commit it to git

## Scaling & Production

For production deployments:

1. **Resource limits**: Adjust CPU/memory requests and limits
2. **High availability**: Consider running multiple replicas
3. **Backup strategy**: Regular backups of InfluxDB data
4. **Monitoring**: Set up alerts for pod health and data collection
5. **Load balancer**: Use a proper load balancer instead of port-forward

## Cleanup

To remove the deployment:

```bash
kubectl delete namespace sig-data
```

This will remove all resources in the sig-data namespace, including persistent volumes.
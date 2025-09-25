# Sigen Solar Monitoring - Final Setup Tasks

## 🌐 Domain & DNS Configuration

### 1. Stop Local Services
- [ ] Stop your local Grafana instance (currently on port 3000)
- [ ] Stop your local InfluxDB instance (currently on port 8086)
- [ ] Stop your local cloudflared tunnel (if running separately)

### 2. Update Cloudflare DNS Records
Go to your Cloudflare dashboard (cloudflare.com) → DNS → Records:

- [ ] **Add/Update CNAME records:**
  ```
  grafana.coeusdata.xyz  -> 743fc85d-6239-4d79-8671-4c4b0190c2a3.cfargotunnel.com
  influxdb.coeusdata.xyz -> 743fc85d-6239-4d79-8671-4c4b0190c2a3.cfargotunnel.com
  argocd.coeusdata.xyz   -> 743fc85d-6239-4d79-8671-4c4b0190c2a3.cfargotunnel.com
  ```

- [ ] **Set Proxy Status:** Orange cloud (Proxied) for all records
- [ ] **Verify SSL/TLS settings:** Set to "Full (strict)" mode

### 3. Test Domain Access
- [ ] Visit `https://grafana.coeusdata.xyz` (should show Grafana login)
- [ ] Visit `https://influxdb.coeusdata.xyz` (should show InfluxDB UI)
- [ ] Visit `https://argocd.coeusdata.xyz` (should show ArgoCD login)

## 🔐 Authentication & Configuration

### 4. Fix Sigen API Authentication
Current error: "authentication failed (API Code: 11003)"

- [ ] **Recapture transformed password from browser:**
  1. Open browser dev tools (F12) → Network tab
  2. Check "Preserve log"
  3. Go to MySigen portal and login
  4. Find POST request to `https://api-eu.sigencloud.com/auth/oauth/token`
  5. Copy the `password` field from request payload
  6. Update the secret in Kubernetes:
     ```bash
     kubectl patch secret sig-data-secrets -n sig-data \
       --patch='{"stringData":{"SIGEN_TRANSFORMED_PASSWORD":"new-captured-password"}}'
     ```

- [ ] **Test authentication:**
  ```bash
  # Check if new password works
  kubectl logs -f deployment/sig-data -n sig-data

  # If still failing, try running auth test locally first
  python auth_handler.py
  ```

### 5. Configure Grafana
- [ ] **Login to Grafana:** `https://grafana.coeusdata.xyz`
  - Username: `admin`
  - Password: `secure-grafana-password-2024`

- [ ] **Verify InfluxDB data source connection**
- [ ] **Import your existing dashboards** (if you have JSON files)
- [ ] **Wait for data collection** (sig-data runs every minute)

### 6. Configure InfluxDB (if needed)
- [ ] **Login to InfluxDB:** `https://influxdb.coeusdata.xyz`
- [ ] **Verify bucket exists:** `energy_metrics`
- [ ] **Check data is flowing** once auth is fixed

## 🔧 Optional Enhancements

### 7. Set up GitOps (ArgoCD)
- [ ] **Push code to GitHub** (resolve any auth issues first)
- [ ] **Login to ArgoCD:** `https://argocd.coeusdata.xyz`
  - Username: `admin`
  - Password: `7KFXUTJCFN6j1hhe`
- [ ] **Create ArgoCD application** pointing to your GitHub repo
- [ ] **Enable auto-sync** for continuous deployment

### 8. Monitoring & Alerts (Optional)
- [ ] Set up **Cloudflare health checks** for your services
- [ ] Configure **Grafana alerts** for system issues
- [ ] Set up **email notifications** for data collection failures

## 🚨 Troubleshooting Commands

### Check Kubernetes Status
```bash
# Overall pod status
kubectl get pods -n sig-data

# Check specific service logs
kubectl logs -f deployment/sig-data -n sig-data
kubectl logs -f deployment/grafana -n sig-data
kubectl logs -f deployment/cloudflared -n sig-data

# Check tunnel connection
kubectl describe pod -l app=cloudflared -n sig-data
```

### Check Cloudflare Tunnel
```bash
# Verify tunnel config in cluster
kubectl get configmap cloudflared-config -n sig-data -o yaml

# Check tunnel logs
kubectl logs -f deployment/cloudflared -n sig-data
```

### Test Local Authentication
```bash
# Test Sigen auth locally before updating cluster
python auth_handler.py

# Check what's in your .env file
cat .env | grep SIGEN
```

## ✅ Success Criteria

- [ ] All three domains load properly with HTTPS
- [ ] Grafana shows "Connected" for InfluxDB data source
- [ ] Sigen authentication successful (no error code 11003)
- [ ] Energy data appears in InfluxDB within 5-10 minutes
- [ ] Solar monitoring dashboard displays current data

---

**Priority Order:**
1. Stop local services → Update DNS → Test domain access
2. Fix Sigen authentication
3. Verify data collection is working
4. Optional: Set up GitOps and monitoring
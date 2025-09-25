# ArgoCD GitOps Deployment Guide

This guide shows how to deploy the Sigen Solar Data monitoring system using ArgoCD for GitOps-style continuous deployment.

## Why ArgoCD?

- **GitOps Workflow**: Your Git repository is the single source of truth
- **Automatic Sync**: Changes to your repo automatically deploy to Kubernetes
- **Visual UI**: See deployment status, logs, and resource relationships
- **Rollback Capability**: Easy rollback to previous versions
- **Multi-Environment**: Easy to manage dev/staging/prod environments

## Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Git Repo      │    │   ArgoCD     │    │  Kubernetes     │
│  (sig-data)     │───▶│   Server     │───▶│   Cluster       │
│                 │    │              │    │                 │
│ • k8s manifests │    │ • Monitors   │    │ • InfluxDB      │
│ • Kustomization│    │ • Syncs      │    │ • Grafana       │
│ • ArgoCD Apps   │    │ • Deploys    │    │ • sig-data app  │
└─────────────────┘    └──────────────┘    └─────────────────┘
```

## Quick Start

### Prerequisites

1. **Kubernetes cluster** (kind, minikube, or remote cluster)
2. **kubectl** configured and connected
3. **Git repository** with your sig-data code
4. **Docker** for building images

### 1. Setup Git Repository

```bash
# If you haven't already, initialize and push to a Git repository
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/sig-data.git
git push -u origin main
```

### 2. Configure Secrets

```bash
# Copy and configure your Sigen credentials
cp k8s/secret-sig-data.example.yaml k8s/secret-sig-data-configured.yaml
vim k8s/secret-sig-data-configured.yaml  # Add your actual credentials
```

### 3. Deploy with ArgoCD

```bash
# One command deployment
./setup-argocd.sh deploy
```

This will:
- Install ArgoCD on your cluster
- Build and load your Docker image
- Configure secrets
- Create the ArgoCD application
- Start automatic synchronization

### 4. Access the Services

```bash
# ArgoCD UI (for kind clusters)
# Visit: http://localhost:30080
# Username: admin, Password: (shown in script output)

# Grafana (after ArgoCD syncs)
kubectl port-forward svc/grafana 3000:3000 -n sig-data
# Visit: http://localhost:3000

# InfluxDB
kubectl port-forward svc/influxdb 8086:8086 -n sig-data
# Visit: http://localhost:8086
```

## Advanced Configuration

### Multiple Deployment Options

The project includes two ArgoCD application configurations:

#### 1. Simple Application (`argocd/application.yaml`)
- Direct deployment of k8s manifests
- Good for simple scenarios

#### 2. Kustomize Application (`argocd/application-with-kustomize.yaml`) **[Default]**
- Uses Kustomize for configuration management
- Better for customizations and multiple environments
- Includes image patching and common labels

### Customizing Your Deployment

#### Update Repository URL
The setup script automatically detects your Git remote, but you can manually update:

```yaml
# In argocd/application-with-kustomize.yaml
spec:
  source:
    repoURL: https://github.com/yourusername/sig-data.git  # Update this
```

#### Configure Image Registry
For production deployments with a container registry:

```yaml
# In argocd/patches/sig-data-deployment.yaml
spec:
  template:
    spec:
      containers:
        - name: sig-data
          image: your-registry.com/sig-data:v1.0.0  # Update this
```

#### Environment-Specific Configurations
Create separate Kustomize overlays:

```bash
mkdir -p argocd/overlays/{dev,staging,prod}

# argocd/overlays/prod/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../base
images:
  - name: sig-data
    newTag: v1.0.0
replicas:
  - name: sig-data
    count: 2
```

## GitOps Workflow

### 1. Development Workflow
```bash
# Make changes to your application
vim main_scheduler.py

# Commit and push changes
git add .
git commit -m "Improve error handling in scheduler"
git push origin main

# ArgoCD automatically detects and syncs changes (within 3 minutes)
```

### 2. Configuration Changes
```bash
# Update Kubernetes manifests
vim k8s/configmap-sig-data.yaml

# Update image version
vim argocd/patches/sig-data-deployment.yaml

# Push changes
git add .
git commit -m "Update configuration and image version"
git push origin main

# ArgoCD syncs automatically
```

### 3. Manual Sync (if needed)
```bash
# Force immediate sync via kubectl
kubectl patch application sig-data-kustomize -n argocd --type merge -p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{"revision":"HEAD"}}}'

# Or use ArgoCD CLI
argocd app sync sig-data-kustomize
```

## Monitoring and Troubleshooting

### Check Application Status
```bash
# List all ArgoCD applications
kubectl get applications -n argocd

# Describe application status
kubectl describe application sig-data-kustomize -n argocd

# Check sync status
kubectl get application sig-data-kustomize -n argocd -o jsonpath='{.status.sync.status}'
```

### View Application Logs
```bash
# ArgoCD application controller logs
kubectl logs -f deployment/argocd-application-controller -n argocd

# Your application logs
kubectl logs -f deployment/sig-data -n sig-data
```

### Common Issues

#### Sync Failures
- Check if secrets are configured correctly
- Verify image is available (for registry-based deployments)
- Check resource quotas and permissions

#### Image Pull Errors
```bash
# For kind clusters, ensure image is loaded
kind load docker-image sig-data:latest --name your-cluster-name

# For registry deployments, verify image exists and credentials are correct
```

#### Configuration Issues
```bash
# Check if secrets exist
kubectl get secrets -n sig-data

# Verify ConfigMap values
kubectl get configmap sig-data-config -n sig-data -o yaml
```

## Production Considerations

### Security
- Use private Git repositories for sensitive configurations
- Store secrets in external secret management systems (e.g., External Secrets Operator)
- Enable RBAC and proper access controls
- Use signed commits and branch protection

### High Availability
- Deploy ArgoCD in HA mode for production
- Use multiple replicas for your applications
- Implement proper backup strategies for ArgoCD configuration

### Monitoring
- Set up alerts for sync failures
- Monitor application health metrics
- Use ArgoCD notifications for deployment events

### Multi-Environment Setup
```bash
# Create environment-specific applications
├── argocd/
│   ├── applications/
│   │   ├── sig-data-dev.yaml
│   │   ├── sig-data-staging.yaml
│   │   └── sig-data-prod.yaml
│   └── overlays/
│       ├── dev/
│       ├── staging/
│       └── prod/
```

## ArgoCD CLI (Optional)

Install ArgoCD CLI for advanced operations:

```bash
# macOS
brew install argocd

# Linux
curl -sSL -o /usr/local/bin/argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
chmod +x /usr/local/bin/argocd

# Login
argocd login localhost:30080  # for kind clusters
argocd app list
argocd app sync sig-data-kustomize
argocd app history sig-data-kustomize
```

## Cleanup

```bash
# Delete the application
kubectl delete application sig-data-kustomize -n argocd

# Delete ArgoCD (removes everything)
kubectl delete namespace argocd

# Delete application namespace
kubectl delete namespace sig-data
```
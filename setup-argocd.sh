#!/bin/bash

# ArgoCD Setup Script for Sigen Solar Data Project
# This script installs and configures ArgoCD for GitOps deployment

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ARGOCD_VERSION="v2.8.4"
ARGOCD_NAMESPACE="argocd"
APP_NAMESPACE="sig-data"

echo -e "${BLUE}🚀 Setting up ArgoCD for Sigen Solar Data Project${NC}"
echo "=================================================="

# Check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl is not installed or not in PATH${NC}"
        echo "Please install kubectl first"
        exit 1
    fi

    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}❌ Cannot connect to Kubernetes cluster${NC}"
        echo "Please ensure kubectl is configured correctly"
        exit 1
    fi

    echo -e "${GREEN}✅ kubectl is configured and cluster is accessible${NC}"
}

# Install ArgoCD
install_argocd() {
    echo -e "${YELLOW}📦 Installing ArgoCD...${NC}"

    # Create argocd namespace
    kubectl create namespace ${ARGOCD_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

    # Install ArgoCD
    kubectl apply -n ${ARGOCD_NAMESPACE} -f https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml

    # Wait for ArgoCD to be ready
    echo -e "${YELLOW}⏳ Waiting for ArgoCD to be ready...${NC}"
    kubectl wait --for=condition=available deployment/argocd-server -n ${ARGOCD_NAMESPACE} --timeout=300s

    echo -e "${GREEN}✅ ArgoCD installed successfully${NC}"
}

# Configure ArgoCD
configure_argocd() {
    echo -e "${YELLOW}⚙️  Configuring ArgoCD...${NC}"

    # Patch ArgoCD server to use NodePort for kind
    if kubectl get nodes -o jsonpath='{.items[0].metadata.labels}' | grep -q "kind"; then
        echo -e "${YELLOW}🔧 Detected kind cluster, configuring NodePort access...${NC}"
        kubectl patch svc argocd-server -n ${ARGOCD_NAMESPACE} -p '{"spec":{"type":"NodePort","ports":[{"port":80,"nodePort":30080,"targetPort":8080}]}}'
    fi

    # Get initial admin password
    ADMIN_PASSWORD=$(kubectl -n ${ARGOCD_NAMESPACE} get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)

    echo -e "${GREEN}✅ ArgoCD configured${NC}"
    echo -e "${YELLOW}📝 Initial admin password: ${ADMIN_PASSWORD}${NC}"
}

# Create ArgoCD Application
create_application() {
    echo -e "${YELLOW}📱 Creating ArgoCD Application...${NC}"

    # Check if we have a Git repository configured
    if ! git remote -v &> /dev/null; then
        echo -e "${RED}❌ No Git remote configured${NC}"
        echo "Please configure your Git repository first:"
        echo "  git remote add origin https://github.com/yourusername/sig-data.git"
        echo "  git push -u origin main"
        echo ""
        echo "Then update argocd/application.yaml with your repository URL"
        return 1
    fi

    # Get the Git repository URL
    REPO_URL=$(git remote get-url origin 2>/dev/null || echo "")

    if [[ -n "$REPO_URL" ]]; then
        # Update the application manifest with the actual repo URL
        sed -i.bak "s|https://github.com/yourusername/sig-data.git|${REPO_URL}|" argocd/application.yaml
        sed -i.bak "s|https://github.com/yourusername/sig-data.git|${REPO_URL}|" argocd/application-with-kustomize.yaml
        echo -e "${GREEN}✅ Updated application manifests with repository URL: ${REPO_URL}${NC}"
    fi

    # Apply the ArgoCD application (using Kustomize version by default)
    kubectl apply -f argocd/application-with-kustomize.yaml

    echo -e "${GREEN}✅ ArgoCD Application created${NC}"
}

# Setup secrets
setup_secrets() {
    echo -e "${YELLOW}🔐 Setting up secrets...${NC}"

    if [ ! -f "k8s/secret-sig-data-configured.yaml" ]; then
        echo -e "${YELLOW}⚠️  Creating secrets template...${NC}"
        cp k8s/secret-sig-data.example.yaml k8s/secret-sig-data-configured.yaml
        echo -e "${RED}❌ Please edit k8s/secret-sig-data-configured.yaml with your Sigen credentials${NC}"
        echo "Then run this script again with 'deploy' option"
        return 1
    fi

    # Apply secrets directly (ArgoCD will sync the rest)
    kubectl apply -f k8s/secret-sig-data-configured.yaml

    echo -e "${GREEN}✅ Secrets configured${NC}"
}

# Build and load Docker image for kind
build_image() {
    echo -e "${YELLOW}🔨 Building Docker image...${NC}"

    # Build the image
    docker build -t sig-data:latest .

    # Check if we're using kind
    if kubectl get nodes -o jsonpath='{.items[0].metadata.labels}' | grep -q "kind"; then
        echo -e "${YELLOW}📤 Loading image into kind cluster...${NC}"
        # Try to detect kind cluster name
        CLUSTER_NAME=$(kubectl config current-context | sed 's/kind-//')
        kind load docker-image sig-data:latest --name ${CLUSTER_NAME}
        echo -e "${GREEN}✅ Image loaded into kind cluster${NC}"
    else
        echo -e "${YELLOW}⚠️  For remote clusters, you'll need to push the image to a registry${NC}"
        echo "Then update argocd/patches/sig-data-deployment.yaml with the registry image path"
    fi
}

# Show access information
show_access_info() {
    echo -e "${BLUE}🌐 Access Information${NC}"
    echo "===================="
    echo ""

    # Get admin password
    ADMIN_PASSWORD=$(kubectl -n ${ARGOCD_NAMESPACE} get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d 2>/dev/null || echo "Not available")

    # Check if kind is being used
    if kubectl get nodes -o jsonpath='{.items[0].metadata.labels}' | grep -q "kind"; then
        echo -e "${YELLOW}ArgoCD UI (Kind):${NC}"
        echo "  http://localhost:30080"
        echo "  Username: admin"
        echo "  Password: ${ADMIN_PASSWORD}"
        echo ""
        echo -e "${YELLOW}Grafana (after sync):${NC}"
        echo "  kubectl port-forward svc/grafana 3000:3000 -n sig-data"
        echo "  http://localhost:3000"
        echo ""
        echo -e "${YELLOW}InfluxDB (after sync):${NC}"
        echo "  kubectl port-forward svc/influxdb 8086:8086 -n sig-data"
        echo "  http://localhost:8086"
    else
        echo -e "${YELLOW}ArgoCD UI:${NC}"
        echo "  kubectl port-forward svc/argocd-server 8080:80 -n argocd"
        echo "  http://localhost:8080"
        echo "  Username: admin"
        echo "  Password: ${ADMIN_PASSWORD}"
    fi

    echo ""
    echo -e "${YELLOW}Useful Commands:${NC}"
    echo "• Check ArgoCD apps: kubectl get applications -n argocd"
    echo "• Check app status: kubectl describe application sig-data-kustomize -n argocd"
    echo "• View app logs: kubectl logs -f deployment/sig-data -n sig-data"
    echo "• Sync manually: argocd app sync sig-data-kustomize (requires argocd CLI)"
}

# Show help
show_help() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  install    - Install ArgoCD on the cluster"
    echo "  configure  - Configure ArgoCD and create applications"
    echo "  build      - Build and load Docker image"
    echo "  secrets    - Setup secrets (interactive)"
    echo "  deploy     - Full deployment (install + configure + build)"
    echo "  info       - Show access information"
    echo "  help       - Show this help message"
    echo ""
    echo "Prerequisites:"
    echo "1. kubectl configured and connected to cluster"
    echo "2. Git repository with remote origin configured"
    echo "3. Docker available (for building images)"
    echo "4. Configured secrets file (k8s/secret-sig-data-configured.yaml)"
}

# Main script logic
case "${1:-deploy}" in
    "install")
        check_kubectl
        install_argocd
        configure_argocd
        ;;
    "configure")
        check_kubectl
        create_application
        ;;
    "build")
        build_image
        ;;
    "secrets")
        setup_secrets
        ;;
    "deploy")
        check_kubectl
        install_argocd
        configure_argocd
        build_image
        setup_secrets
        create_application
        show_access_info
        ;;
    "info")
        show_access_info
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac
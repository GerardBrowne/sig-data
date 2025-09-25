#!/bin/bash

# Sigen Solar Data - Kubernetes Deployment Script
# This script helps deploy the sig-data application to Kubernetes

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration - Update these values
# For kind: use "kind-local" (no registry push needed)
# For remote clusters: use "docker.io/yourusername", "gcr.io/your-project", etc.
REGISTRY="kind-local"
IMAGE_NAME="sig-data"
TAG="latest"
NAMESPACE="sig-data"

echo -e "${BLUE}🚀 Sigen Solar Data - Kubernetes Deployment${NC}"
echo "=================================================="

# Function to check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl is not installed or not in PATH${NC}"
        echo "Please install kubectl and configure it to connect to your cluster"
        exit 1
    fi

    # Check if we can connect to the cluster
    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}❌ Cannot connect to Kubernetes cluster${NC}"
        echo "Please ensure kubectl is configured correctly"
        exit 1
    fi

    echo -e "${GREEN}✅ kubectl is configured and cluster is accessible${NC}"
}

# Function to check if Docker is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed or not in PATH${NC}"
        echo "Please install Docker to build and push the image"
        exit 1
    fi
    echo -e "${GREEN}✅ Docker is available${NC}"
}

# Function to build and push Docker image
build_and_push_image() {
    echo -e "${YELLOW}🔨 Building Docker image...${NC}"

    # Build the image
    docker build -t ${IMAGE_NAME}:${TAG} .

    if [[ "${REGISTRY}" == "kind-local" ]]; then
        # For kind, load image directly into cluster
        echo -e "${YELLOW}📤 Loading image into kind cluster...${NC}"
        kind load docker-image ${IMAGE_NAME}:${TAG} --name sig-data
        echo -e "${GREEN}✅ Image loaded into kind cluster${NC}"
    else
        # Tag for registry
        FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${TAG}"
        docker tag ${IMAGE_NAME}:${TAG} ${FULL_IMAGE}

        echo -e "${YELLOW}📤 Pushing image to registry...${NC}"
        docker push ${FULL_IMAGE}

        echo -e "${GREEN}✅ Image pushed: ${FULL_IMAGE}${NC}"
    fi
}

# Function to check if secrets are configured
check_secrets() {
    echo -e "${YELLOW}🔍 Checking secrets configuration...${NC}"

    # Check if the secret exists
    if kubectl get secret sig-data-secrets -n ${NAMESPACE} &> /dev/null; then
        echo -e "${GREEN}✅ Secrets already exist${NC}"
        return 0
    fi

    echo -e "${RED}❌ Secrets not found${NC}"
    echo -e "${YELLOW}Please configure your secrets first:${NC}"
    echo ""
    echo "1. Edit k8s/secret-sig-data.yaml and fill in your values:"
    echo "   - SIGEN_USERNAME: Your Sigen account email"
    echo "   - SIGEN_TRANSFORMED_PASSWORD: Password from browser dev tools"
    echo "   - SIGEN_STATION_ID: Your Sigen station ID"
    echo ""
    echo "2. Apply the secrets:"
    echo "   kubectl apply -f k8s/secret-sig-data.yaml"
    echo ""
    return 1
}

# Function to deploy the application
deploy() {
    echo -e "${YELLOW}🚀 Deploying to Kubernetes...${NC}"

    # Create namespace
    echo "Creating namespace..."
    kubectl apply -f k8s/namespace.yaml

    # Apply ConfigMap
    echo "Creating ConfigMap..."
    kubectl apply -f k8s/configmap-sig-data.yaml

    # Check secrets
    if ! check_secrets; then
        echo -e "${RED}❌ Cannot proceed without secrets. Please configure them first.${NC}"
        return 1
    fi

    # Deploy InfluxDB
    echo "Deploying InfluxDB..."
    kubectl apply -f k8s/influxdb.yaml

    # Deploy Grafana provisioning
    echo "Creating Grafana provisioning ConfigMaps..."
    kubectl apply -f k8s/grafana-provisioning-configmaps.yaml

    # Deploy Grafana
    echo "Deploying Grafana..."
    kubectl apply -f k8s/grafana.yaml

    # Update the sig-data deployment with the correct image
    echo "Updating sig-data deployment image..."
    if [[ "${REGISTRY}" == "kind-local" ]]; then
        # For kind, use the local image name
        sed "s|image: sig-data:latest|image: ${IMAGE_NAME}:${TAG}|" k8s/sig-data.yaml | kubectl apply -f -
    else
        # For remote registries, use the full registry path
        sed "s|image: sig-data:latest|image: ${REGISTRY}/${IMAGE_NAME}:${TAG}|" k8s/sig-data.yaml | kubectl apply -f -
    fi

    echo -e "${GREEN}✅ Deployment complete!${NC}"
}

# Function to check deployment status
check_status() {
    echo -e "${YELLOW}📊 Checking deployment status...${NC}"

    echo "Pods:"
    kubectl get pods -n ${NAMESPACE}

    echo -e "\nServices:"
    kubectl get services -n ${NAMESPACE}

    echo -e "\nPersistent Volume Claims:"
    kubectl get pvc -n ${NAMESPACE}
}

# Function to show access instructions
show_access_info() {
    echo -e "${BLUE}🌐 Access Information${NC}"
    echo "===================="
    echo ""
    echo "To access Grafana:"
    echo "  kubectl port-forward svc/grafana 3000:3000 -n ${NAMESPACE}"
    echo "  Then visit: http://localhost:3000"
    echo "  Default login: admin/admin (from secrets)"
    echo ""
    echo "To access InfluxDB UI:"
    echo "  kubectl port-forward svc/influxdb 8086:8086 -n ${NAMESPACE}"
    echo "  Then visit: http://localhost:8086"
    echo ""
    echo "To view logs:"
    echo "  kubectl logs -f deployment/sig-data -n ${NAMESPACE}"
}

# Function to show help
show_help() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  check       - Check prerequisites and cluster connectivity"
    echo "  build       - Build and push Docker image"
    echo "  deploy      - Deploy the application to Kubernetes"
    echo "  status      - Check deployment status"
    echo "  info        - Show access information"
    echo "  all         - Run check, build, and deploy"
    echo "  help        - Show this help message"
    echo ""
    echo "Before running, update the REGISTRY variable in this script!"
}

# Main script logic
case "${1:-all}" in
    "check")
        check_kubectl
        check_docker
        ;;
    "build")
        check_docker
        build_and_push_image
        ;;
    "deploy")
        check_kubectl
        deploy
        ;;
    "status")
        check_kubectl
        check_status
        ;;
    "info")
        show_access_info
        ;;
    "all")
        check_kubectl
        check_docker
        build_and_push_image
        deploy
        check_status
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
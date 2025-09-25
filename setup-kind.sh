#!/bin/bash

# Kind Kubernetes Setup for Sigen Solar Data Project
# This script sets up a kind cluster optimized for this project

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

CLUSTER_NAME="sig-data"
KIND_CONFIG="kind-config.yaml"

echo -e "${BLUE}🏗️  Setting up Kind Kubernetes cluster for Sigen Solar Data${NC}"
echo "============================================================"

# Check if kind is installed
check_kind() {
    if ! command -v kind &> /dev/null; then
        echo -e "${RED}❌ kind is not installed${NC}"
        echo -e "${YELLOW}Installing kind...${NC}"

        # Install kind based on OS
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if command -v brew &> /dev/null; then
                brew install kind
            else
                echo "Please install Homebrew first, then run: brew install kind"
                exit 1
            fi
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
            chmod +x ./kind
            sudo mv ./kind /usr/local/bin/kind
        else
            echo "Please install kind manually: https://kind.sigs.k8s.io/docs/user/quick-start/#installation"
            exit 1
        fi
    fi
    echo -e "${GREEN}✅ kind is installed${NC}"
}

# Check if kubectl is installed
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl is not installed${NC}"
        echo -e "${YELLOW}Installing kubectl...${NC}"

        if [[ "$OSTYPE" == "darwin"* ]]; then
            if command -v brew &> /dev/null; then
                brew install kubectl
            else
                echo "Please install Homebrew first, then run: brew install kubectl"
                exit 1
            fi
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
            chmod +x kubectl
            sudo mv kubectl /usr/local/bin/kubectl
        else
            echo "Please install kubectl manually: https://kubernetes.io/docs/tasks/tools/"
            exit 1
        fi
    fi
    echo -e "${GREEN}✅ kubectl is installed${NC}"
}

# Check if Docker is running
check_docker() {
    if ! docker info &> /dev/null; then
        echo -e "${RED}❌ Docker is not running${NC}"
        echo "Please start Docker Desktop and try again"
        exit 1
    fi
    echo -e "${GREEN}✅ Docker is running${NC}"
}

# Create kind configuration
create_kind_config() {
    cat > ${KIND_CONFIG} << EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ${CLUSTER_NAME}
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  # Grafana (using different port since you have local Grafana on 3000)
  - containerPort: 30001
    hostPort: 3001
    protocol: TCP
  # InfluxDB (using different port since you have local InfluxDB on 8086)
  - containerPort: 30087
    hostPort: 8087
    protocol: TCP
EOF
    echo -e "${GREEN}✅ Kind configuration created${NC}"
}

# Create the kind cluster
create_cluster() {
    if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
        echo -e "${YELLOW}⚠️  Cluster '${CLUSTER_NAME}' already exists${NC}"
        read -p "Do you want to delete and recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}🗑️  Deleting existing cluster...${NC}"
            kind delete cluster --name ${CLUSTER_NAME}
        else
            echo -e "${BLUE}Using existing cluster${NC}"
            return 0
        fi
    fi

    echo -e "${YELLOW}🚀 Creating kind cluster...${NC}"
    kind create cluster --config ${KIND_CONFIG}

    # Wait for cluster to be ready
    echo -e "${YELLOW}⏳ Waiting for cluster to be ready...${NC}"
    kubectl wait --for=condition=Ready nodes --all --timeout=300s

    echo -e "${GREEN}✅ Cluster created successfully${NC}"
}

# Update the deployment script for kind
update_deployment_script() {
    if [ -f "deploy-k8s.sh" ]; then
        # Update the registry setting for kind
        sed -i.bak 's/REGISTRY="your-registry"/REGISTRY="kind-local"/' deploy-k8s.sh
        echo -e "${GREEN}✅ Updated deploy-k8s.sh for kind${NC}"
    fi
}

# Create NodePort services for easy access
create_nodeport_services() {
    cat > nodeport-services.yaml << EOF
apiVersion: v1
kind: Service
metadata:
  name: grafana-nodeport
  namespace: sig-data
spec:
  type: NodePort
  selector:
    app: grafana
  ports:
    - port: 3000
      targetPort: 3000
      nodePort: 30001
---
apiVersion: v1
kind: Service
metadata:
  name: influxdb-nodeport
  namespace: sig-data
spec:
  type: NodePort
  selector:
    app: influxdb
  ports:
    - port: 8086
      targetPort: 8086
      nodePort: 30087
EOF
    echo -e "${GREEN}✅ Created NodePort services configuration${NC}"
}

# Show next steps
show_next_steps() {
    echo -e "${BLUE}🎉 Kind cluster is ready!${NC}"
    echo "========================"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Configure your Sigen credentials:"
    echo "   cp k8s/secret-sig-data.example.yaml k8s/secret-sig-data-configured.yaml"
    echo "   vim k8s/secret-sig-data-configured.yaml"
    echo ""
    echo "2. Deploy the application:"
    echo "   ./deploy-k8s.sh all"
    echo ""
    echo "3. Apply NodePort services (after deployment):"
    echo "   kubectl apply -f nodeport-services.yaml"
    echo ""
    echo -e "${YELLOW}Access URLs (after deployment):${NC}"
    echo "• Grafana: http://localhost:3001 (cluster) - Your local: http://localhost:3000"
    echo "• InfluxDB: http://localhost:8087 (cluster) - Your local: http://localhost:8086"
    echo ""
    echo -e "${YELLOW}Useful commands:${NC}"
    echo "• View cluster info: kubectl cluster-info --context kind-${CLUSTER_NAME}"
    echo "• Delete cluster: kind delete cluster --name ${CLUSTER_NAME}"
    echo "• Load image to kind: kind load docker-image <image-name> --name ${CLUSTER_NAME}"
}

# Main execution
main() {
    check_docker
    check_kind
    check_kubectl
    create_kind_config
    create_cluster
    update_deployment_script
    create_nodeport_services
    show_next_steps
}

# Handle script arguments
case "${1:-setup}" in
    "setup")
        main
        ;;
    "delete")
        echo -e "${YELLOW}🗑️  Deleting kind cluster...${NC}"
        kind delete cluster --name ${CLUSTER_NAME}
        rm -f ${KIND_CONFIG} nodeport-services.yaml
        echo -e "${GREEN}✅ Cluster deleted${NC}"
        ;;
    "status")
        if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
            echo -e "${GREEN}✅ Cluster '${CLUSTER_NAME}' is running${NC}"
            kubectl cluster-info --context kind-${CLUSTER_NAME}
        else
            echo -e "${RED}❌ Cluster '${CLUSTER_NAME}' not found${NC}"
        fi
        ;;
    *)
        echo "Usage: $0 [setup|delete|status]"
        echo ""
        echo "Commands:"
        echo "  setup  - Create and configure kind cluster (default)"
        echo "  delete - Delete the kind cluster"
        echo "  status - Check cluster status"
        ;;
esac
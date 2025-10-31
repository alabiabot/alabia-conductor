#!/bin/bash
# Deploy script para AWS Ubuntu

set -e

echo "🚀 Alabia Conductor - Deploy Script"
echo "===================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}ERROR: .env file not found${NC}"
    echo "Copy .env.example to .env and configure it first:"
    echo "  cp .env.example .env"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker not found. Installing...${NC}"
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
    echo -e "${GREEN}Docker installed${NC}"
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}Docker Compose not found. Installing...${NC}"
    sudo apt-get install -y docker-compose
    echo -e "${GREEN}Docker Compose installed${NC}"
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data/chroma_db secrets logs

# Build and start services
echo "🔨 Building containers..."
cd infra
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

# Wait for services
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check health
echo "🏥 Checking health..."
docker-compose ps

# Test endpoint
echo "🧪 Testing API..."
sleep 5
curl -f http://localhost:8000/health || echo -e "${RED}API not responding${NC}"

echo ""
echo -e "${GREEN}✅ Deploy complete!${NC}"
echo ""
echo "📊 Status:"
docker-compose ps

echo ""
echo "📝 Logs:"
echo "  docker-compose -f infra/docker-compose.yml logs -f"

echo ""
echo "🔧 Management:"
echo "  Stop:    docker-compose -f infra/docker-compose.yml stop"
echo "  Restart: docker-compose -f infra/docker-compose.yml restart"
echo "  Remove:  docker-compose -f infra/docker-compose.yml down"

echo ""
echo "🌐 Endpoints:"
echo "  API:     http://localhost:8000"
echo "  Health:  http://localhost:8000/health"
echo "  Chat:    http://localhost:8000/api/chat"
echo "  Chroma:  http://localhost:8001"

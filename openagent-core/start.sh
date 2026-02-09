#!/bin/bash

# OpenAgent Startup Script
# Provides easy commands to start different modes

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_banner() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                    OpenAgent Starter                       ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_help() {
    echo -e "${GREEN}Usage:${NC} ./start.sh [mode]"
    echo ""
    echo -e "${GREEN}Modes:${NC}"
    echo "  setup     - Initial setup (first time only)"
    echo "  server    - Start LangGraph Server only (for LangSmith Studio)"
    echo "  cli       - Start CLI only (interactive development)"
    echo "  both      - Start both Server and CLI"
    echo "  stop      - Stop all services"
    echo "  logs      - Show logs from all services"
    echo "  build     - Rebuild Docker images"
    echo ""
    echo -e "${GREEN}Examples:${NC}"
    echo "  ./start.sh setup     # First time setup"
    echo "  ./start.sh server    # Start API server on port 8000"
    echo "  ./start.sh cli       # Start interactive CLI"
    echo "  ./start.sh both      # Start everything"
    echo ""
}

check_env() {
    if [ ! -f .env ]; then
        echo -e "${YELLOW}Warning: .env file not found${NC}"
        echo "Run './start.sh setup' first to configure the environment"
        exit 1
    fi
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: Docker not found${NC}"
        echo "Install Docker Desktop: https://www.docker.com/products/docker-desktop"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}Error: Docker Compose not found${NC}"
        exit 1
    fi
}

run_setup() {
    print_banner
    echo -e "${GREEN}OpenAgent Initial Setup${NC}"
    echo ""

    # Check Docker
    echo -e "${BLUE}Checking prerequisites...${NC}"
    check_docker
    echo -e "${GREEN}✓ Docker and Docker Compose found${NC}"
    echo ""

    # Create .env
    if [ ! -f .env ]; then
        echo -e "${BLUE}Creating .env file...${NC}"
        cp .env.example .env
        echo -e "${GREEN}✓ .env created${NC}"
        echo ""
        echo -e "${YELLOW}IMPORTANT: Edit .env and add your API keys${NC}"
        echo ""
        read -p "Press Enter to edit .env now (or Ctrl+C to skip)..."
        ${EDITOR:-nano} .env
    else
        echo -e "${GREEN}✓ .env already exists${NC}"
    fi

    echo ""

    # Create workspace
    if [ ! -d workspace ]; then
        echo -e "${BLUE}Creating workspace directory...${NC}"
        mkdir -p workspace
        echo -e "${GREEN}✓ workspace/ created${NC}"
    else
        echo -e "${GREEN}✓ workspace/ already exists${NC}"
    fi

    echo ""

    # Build images
    echo -e "${BLUE}Building Docker images (this may take a few minutes)...${NC}"
    docker-compose build

    echo ""
    echo -e "${GREEN}✓ Setup complete!${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Make sure you added your GROQ_API_KEY to .env"
    echo "  2. Start OpenAgent with:"
    echo "     ./start.sh server  (for LangSmith Studio integration)"
    echo "     ./start.sh cli     (for interactive CLI)"
    echo ""
}

start_server() {
    print_banner
    echo -e "${GREEN}Starting LangGraph Server...${NC}"
    echo ""
    echo -e "${BLUE}Services starting:${NC}"
    echo "  - PostgreSQL (checkpoint storage)"
    echo "  - Redis (caching)"
    echo "  - LangGraph Server (API on port 8000)"
    echo ""

    docker-compose up -d postgres redis langgraph-server

    echo ""
    echo -e "${GREEN}✓ LangGraph Server started!${NC}"
    echo ""
    echo -e "${BLUE}Access points:${NC}"
    echo "  - API: http://localhost:8000"
    echo "  - LangSmith Studio: Connect to http://localhost:8000"
    echo ""
    echo -e "${YELLOW}Tip:${NC} Run './start.sh logs' to view logs"
}

start_cli() {
    print_banner
    echo -e "${GREEN}Starting OpenAgent CLI...${NC}"
    echo ""
    echo -e "${BLUE}Services starting:${NC}"
    echo "  - PostgreSQL (checkpoint storage)"
    echo "  - Redis (caching)"
    echo "  - OpenAgent CLI (interactive)"
    echo ""

    docker-compose --profile cli up -d postgres redis
    docker-compose --profile cli run --rm openagent-cli
}

start_both() {
    print_banner
    echo -e "${GREEN}Starting all services...${NC}"
    echo ""
    echo -e "${BLUE}Services starting:${NC}"
    echo "  - PostgreSQL (checkpoint storage)"
    echo "  - Redis (caching)"
    echo "  - LangGraph Server (API on port 8000)"
    echo "  - OpenAgent CLI (interactive)"
    echo ""

    docker-compose --profile cli up -d postgres redis langgraph-server

    echo ""
    echo -e "${GREEN}✓ LangGraph Server started!${NC}"
    echo ""
    echo -e "${BLUE}Access points:${NC}"
    echo "  - API: http://localhost:8000"
    echo "  - LangSmith Studio: Connect to http://localhost:8000"
    echo ""
    echo "Now starting CLI..."
    echo ""

    docker-compose --profile cli run --rm openagent-cli
}

stop_services() {
    print_banner
    echo -e "${YELLOW}Stopping all services...${NC}"
    docker-compose --profile cli down
    echo -e "${GREEN}✓ All services stopped${NC}"
}

show_logs() {
    print_banner
    echo -e "${GREEN}Showing logs (Ctrl+C to exit)...${NC}"
    echo ""
    docker-compose --profile cli logs -f
}

build_images() {
    print_banner
    echo -e "${GREEN}Building Docker images...${NC}"
    echo ""
    docker-compose build --no-cache
    echo ""
    echo -e "${GREEN}✓ Build complete!${NC}"
}

# Main script
case "${1:-}" in
    setup)
        run_setup
        ;;
    server)
        check_env
        check_docker
        start_server
        ;;
    cli)
        check_env
        check_docker
        start_cli
        ;;
    both)
        check_env
        check_docker
        start_both
        ;;
    stop)
        stop_services
        ;;
    logs)
        show_logs
        ;;
    build)
        check_docker
        build_images
        ;;
    help|--help|-h)
        print_help
        ;;
    *)
        print_help
        exit 1
        ;;
esac

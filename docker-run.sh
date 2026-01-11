#!/bin/bash
# Isolated LLM Evaluation Runner
#
# Runs evaluation with proper isolation:
# - Game server container: has all game code/data
# - Agent container: only has client, cannot see game files

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    echo "Isolated LLM Evaluation Runner"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  build              Build both containers"
    echo "  run-random         Run with random agent"
    echo "  run-cohere         Run with Cohere agent"
    echo "  up                 Start game server (background)"
    echo "  down               Stop all containers"
    echo "  logs               Show agent logs"
    echo "  shell-agent        Shell into agent container"
    echo "  shell-server       Shell into server container"
    echo ""
    echo "Options:"
    echo "  --turns N          Max turns (default: 200)"
    echo "  --model MODEL      Cohere model (default: command-r-plus)"
    echo ""
    echo "Environment:"
    echo "  COHERE_API_KEY     Required for Cohere agent"
    echo ""
    echo "Example:"
    echo "  $0 build"
    echo "  COHERE_API_KEY=xxx $0 run-cohere --turns 500"
}

build() {
    echo -e "${GREEN}Building isolated containers...${NC}"
    docker-compose build
    echo -e "${GREEN}Done!${NC}"
}

run_random() {
    local turns="${1:-200}"
    echo -e "${GREEN}Running isolated evaluation (random agent)...${NC}"
    echo "  Max turns: $turns"
    echo ""

    EVAL_AGENT=random EVAL_MAX_TURNS="$turns" \
        docker-compose up --abort-on-container-exit llm-agent

    echo ""
    echo -e "${GREEN}Results saved to ./results/${NC}"
}

run_cohere() {
    local turns="${1:-200}"
    local model="${2:-command-r-plus}"

    if [ -z "$COHERE_API_KEY" ]; then
        echo -e "${RED}Error: COHERE_API_KEY not set${NC}"
        exit 1
    fi

    echo -e "${GREEN}Running isolated evaluation (Cohere agent)...${NC}"
    echo "  Model: $model"
    echo "  Max turns: $turns"
    echo ""

    EVAL_AGENT=cohere EVAL_MAX_TURNS="$turns" \
        docker-compose up --abort-on-container-exit llm-agent

    echo ""
    echo -e "${GREEN}Results saved to ./results/${NC}"
}

up() {
    echo -e "${GREEN}Starting game server...${NC}"
    docker-compose up -d game-server
    echo "Game server running. Use '$0 down' to stop."
}

down() {
    echo -e "${GREEN}Stopping containers...${NC}"
    docker-compose down
}

logs() {
    docker-compose logs -f llm-agent
}

shell_agent() {
    echo -e "${YELLOW}Opening shell in AGENT container (isolated, no game files)${NC}"
    docker-compose run --rm llm-agent /bin/bash
}

shell_server() {
    echo -e "${YELLOW}Opening shell in SERVER container (has game files)${NC}"
    docker-compose run --rm game-server /bin/bash
}

# Parse arguments
TURNS=200
MODEL="command-r-plus"

case "${1:-}" in
    build)
        build
        ;;
    run-random)
        shift
        while [[ $# -gt 0 ]]; do
            case $1 in
                --turns) TURNS="$2"; shift 2 ;;
                *) shift ;;
            esac
        done
        run_random "$TURNS"
        ;;
    run-cohere)
        shift
        while [[ $# -gt 0 ]]; do
            case $1 in
                --turns) TURNS="$2"; shift 2 ;;
                --model) MODEL="$2"; shift 2 ;;
                *) shift ;;
            esac
        done
        run_cohere "$TURNS" "$MODEL"
        ;;
    up)
        up
        ;;
    down)
        down
        ;;
    logs)
        logs
        ;;
    shell-agent)
        shell_agent
        ;;
    shell-server)
        shell_server
        ;;
    -h|--help|"")
        usage
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        usage
        exit 1
        ;;
esac

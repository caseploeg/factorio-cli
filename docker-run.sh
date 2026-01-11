#!/bin/bash
# Convenience script for running LLM evaluations in Docker

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
IMAGE_NAME="factorio-llm-eval"
CONTAINER_NAME="factorio-eval"

usage() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  build              Build the Docker image"
    echo "  run-random         Run evaluation with random agent"
    echo "  run-cohere         Run evaluation with Cohere agent"
    echo "  run-compare        Compare random vs Cohere agents"
    echo "  shell              Start interactive shell in container"
    echo "  logs               Show logs from running evaluation"
    echo "  stop               Stop running evaluation"
    echo ""
    echo "Options:"
    echo "  --turns N          Max turns per episode (default: 200)"
    echo "  --episodes N       Number of episodes (default: 1)"
    echo "  --model MODEL      Cohere model (default: command-r-plus)"
    echo ""
    echo "Environment:"
    echo "  COHERE_API_KEY     Required for Cohere agent"
    echo ""
    echo "Examples:"
    echo "  $0 build"
    echo "  $0 run-random --turns 100"
    echo "  COHERE_API_KEY=xxx $0 run-cohere --turns 500"
    echo "  $0 run-compare --episodes 3"
}

build() {
    echo -e "${GREEN}Building Docker image...${NC}"
    docker build -t "$IMAGE_NAME" .
    echo -e "${GREEN}Done!${NC}"
}

run_random() {
    local turns="${1:-200}"
    local episodes="${2:-1}"

    echo -e "${GREEN}Running evaluation with random agent...${NC}"
    echo "  Turns: $turns, Episodes: $episodes"

    docker run --rm \
        -v "$(pwd)/results:/app/results" \
        -v "$(pwd)/logs:/app/logs" \
        "$IMAGE_NAME" \
        --agent random \
        --max-turns "$turns" \
        --episodes "$episodes" \
        --output-dir /app/results
}

run_cohere() {
    local turns="${1:-200}"
    local episodes="${2:-1}"
    local model="${3:-command-r-plus}"

    if [ -z "$COHERE_API_KEY" ]; then
        echo -e "${RED}Error: COHERE_API_KEY not set${NC}"
        echo "Export it first: export COHERE_API_KEY=your-key"
        exit 1
    fi

    echo -e "${GREEN}Running evaluation with Cohere agent...${NC}"
    echo "  Model: $model, Turns: $turns, Episodes: $episodes"

    docker run --rm \
        -e COHERE_API_KEY="$COHERE_API_KEY" \
        -v "$(pwd)/results:/app/results" \
        -v "$(pwd)/logs:/app/logs" \
        "$IMAGE_NAME" \
        --agent cohere \
        --model "$model" \
        --max-turns "$turns" \
        --episodes "$episodes" \
        --output-dir /app/results
}

run_compare() {
    local turns="${1:-200}"
    local episodes="${2:-3}"

    echo -e "${GREEN}Running agent comparison...${NC}"

    local cohere_flag=""
    if [ -n "$COHERE_API_KEY" ]; then
        cohere_flag="-e COHERE_API_KEY=$COHERE_API_KEY"
        echo "  Comparing: random vs cohere"
    else
        echo -e "${YELLOW}  Note: COHERE_API_KEY not set, only running random agent${NC}"
    fi

    docker run --rm \
        $cohere_flag \
        -v "$(pwd)/results:/app/results" \
        "$IMAGE_NAME" \
        --compare \
        --max-turns "$turns" \
        --episodes "$episodes"
}

run_shell() {
    echo -e "${GREEN}Starting interactive shell...${NC}"
    docker run --rm -it \
        -e COHERE_API_KEY="${COHERE_API_KEY:-}" \
        -v "$(pwd)/results:/app/results" \
        --entrypoint /bin/bash \
        "$IMAGE_NAME"
}

show_logs() {
    docker logs -f "$CONTAINER_NAME" 2>/dev/null || echo "No running evaluation found"
}

stop_eval() {
    docker stop "$CONTAINER_NAME" 2>/dev/null || echo "No running evaluation to stop"
}

# Parse arguments
TURNS=200
EPISODES=1
MODEL="command-r-plus"

while [[ $# -gt 0 ]]; do
    case $1 in
        build)
            build
            exit 0
            ;;
        run-random)
            shift
            while [[ $# -gt 0 ]]; do
                case $1 in
                    --turns) TURNS="$2"; shift 2 ;;
                    --episodes) EPISODES="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            run_random "$TURNS" "$EPISODES"
            exit 0
            ;;
        run-cohere)
            shift
            while [[ $# -gt 0 ]]; do
                case $1 in
                    --turns) TURNS="$2"; shift 2 ;;
                    --episodes) EPISODES="$2"; shift 2 ;;
                    --model) MODEL="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            run_cohere "$TURNS" "$EPISODES" "$MODEL"
            exit 0
            ;;
        run-compare)
            shift
            while [[ $# -gt 0 ]]; do
                case $1 in
                    --turns) TURNS="$2"; shift 2 ;;
                    --episodes) EPISODES="$2"; shift 2 ;;
                    *) shift ;;
                esac
            done
            run_compare "$TURNS" "$EPISODES"
            exit 0
            ;;
        shell)
            run_shell
            exit 0
            ;;
        logs)
            show_logs
            exit 0
            ;;
        stop)
            stop_eval
            exit 0
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown command: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

usage

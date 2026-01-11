# Dockerizing the LLM Evaluation Testbed

## Goals

1. **Reproducible environment** - Same Python version, dependencies everywhere
2. **Sandboxed execution** - LLM bash access is safe within container
3. **Easy deployment** - One command to run evaluations
4. **Persistent results** - Checkpoints/logs survive container restarts
5. **API key security** - Secrets handled properly

---

## Architecture Options

### Option A: Single Container (Simple)

```
┌─────────────────────────────────────┐
│           Docker Container          │
│  ┌─────────────────────────────┐   │
│  │   Python + Factorio Sim     │   │
│  │   + LLM Harness             │   │
│  │   + Evaluation Runner       │   │
│  └─────────────────────────────┘   │
│              │                      │
│              ▼                      │
│     Cohere API (external)           │
└─────────────────────────────────────┘
         │
         ▼ (volume mount)
    ./results/
```

**Pros:** Simple, single image, easy to run
**Cons:** No separation of concerns

### Option B: Multi-Container with Docker Compose

```
┌─────────────────────────────────────────────────┐
│                Docker Compose                    │
│  ┌──────────────┐    ┌──────────────────────┐   │
│  │  Flask API   │◄───│  LLM Eval Runner     │   │
│  │  (optional)  │    │  (main workload)     │   │
│  └──────────────┘    └──────────────────────┘   │
│                              │                   │
│                              ▼                   │
│                      Cohere API                  │
└─────────────────────────────────────────────────┘
```

**Pros:** Can run web UI alongside, scalable
**Cons:** More complex setup

### Recommendation: Start with Option A

Single container is sufficient for evaluation runs. Add Compose later if needed.

---

## Implementation Steps

### Step 1: Create Dockerfile

```dockerfile
# Base image with Python
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for outputs
RUN mkdir -p /app/checkpoints /app/logs /app/results

# Default command
ENTRYPOINT ["python", "run_llm_eval.py"]
CMD ["--help"]
```

### Step 2: Create .dockerignore

```
.git
__pycache__
*.pyc
*.pyo
checkpoints/
logs/
results/
eval_output/
*.log
.env
```

### Step 3: Environment Variables

```bash
# Required
COHERE_API_KEY=your-api-key

# Optional
EVAL_MAX_TURNS=500
EVAL_EPISODES=1
EVAL_MODEL=command-r-plus
```

### Step 4: Docker Compose (optional)

```yaml
version: '3.8'

services:
  eval-runner:
    build: .
    environment:
      - COHERE_API_KEY=${COHERE_API_KEY}
    volumes:
      - ./results:/app/results
      - ./checkpoints:/app/checkpoints
      - ./logs:/app/logs
    command: ["--agent", "cohere", "--max-turns", "500", "--output-dir", "/app/results"]

  # Optional: Flask web UI
  web:
    build: .
    ports:
      - "5000:5000"
    command: ["flask", "run", "--host=0.0.0.0"]
    profiles:
      - web
```

### Step 5: Build & Run Commands

```bash
# Build the image
docker build -t factorio-llm-eval .

# Run with Cohere agent
docker run --rm \
  -e COHERE_API_KEY="$COHERE_API_KEY" \
  -v $(pwd)/results:/app/results \
  factorio-llm-eval \
  --agent cohere --max-turns 500

# Run with random agent (no API key needed)
docker run --rm \
  -v $(pwd)/results:/app/results \
  factorio-llm-eval \
  --agent random --max-turns 100

# Interactive shell for debugging
docker run --rm -it \
  -e COHERE_API_KEY="$COHERE_API_KEY" \
  factorio-llm-eval \
  /bin/bash
```

---

## Security Considerations

### Restricted Bash Access (if enabled)

Docker provides natural sandboxing:

1. **No host filesystem access** - Only mounted volumes visible
2. **No network by default** - Add `--network=none` for full isolation
3. **Resource limits** - CPU/memory caps prevent runaway processes
4. **Read-only filesystem** - `--read-only` flag for extra safety

```bash
# Maximum security run
docker run --rm \
  --read-only \
  --network=none \
  --memory=512m \
  --cpus=1 \
  -v $(pwd)/results:/app/results \
  factorio-llm-eval \
  --agent random --max-turns 100
```

### API Key Handling

```bash
# Option 1: Environment variable (good for CI)
docker run -e COHERE_API_KEY="$COHERE_API_KEY" ...

# Option 2: Secrets file (better for production)
docker run --env-file .env ...

# Option 3: Docker secrets (best for swarm/k8s)
# Requires Docker Swarm or Kubernetes
```

---

## Long-Running Evaluations

### Background Execution

```bash
# Run in background with auto-restart
docker run -d \
  --name factorio-eval \
  --restart unless-stopped \
  -e COHERE_API_KEY="$COHERE_API_KEY" \
  -v $(pwd)/results:/app/results \
  factorio-llm-eval \
  --agent cohere --max-turns 10000 --episodes 10

# Check logs
docker logs -f factorio-eval

# Stop gracefully
docker stop factorio-eval
```

### Checkpoint Recovery

```bash
# Resume from checkpoint after container restart
docker run --rm \
  -e COHERE_API_KEY="$COHERE_API_KEY" \
  -v $(pwd)/results:/app/results \
  factorio-llm-eval \
  --resume /app/results/checkpoints/episode_0_turn_500.json
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: LLM Evaluation

on:
  schedule:
    - cron: '0 0 * * *'  # Daily
  workflow_dispatch:

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t factorio-llm-eval .

      - name: Run evaluation
        env:
          COHERE_API_KEY: ${{ secrets.COHERE_API_KEY }}
        run: |
          docker run --rm \
            -e COHERE_API_KEY \
            -v ${{ github.workspace }}/results:/app/results \
            factorio-llm-eval \
            --agent cohere --max-turns 500

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: eval-results
          path: results/
```

---

## TODO Checklist

- [ ] Create Dockerfile
- [ ] Create .dockerignore
- [ ] Test local build
- [ ] Add volume mounts for persistence
- [ ] Test checkpoint/resume across container restarts
- [ ] Add Docker Compose for multi-service setup
- [ ] Document CI/CD integration
- [ ] Add health checks for long-running containers
- [ ] Consider multi-stage build for smaller image

---

## Open Questions

1. **GPU support?** - If using local LLMs later, need nvidia-docker
2. **Multiple parallel evaluations?** - Could use docker-compose scale
3. **Results aggregation?** - Need a solution for collecting results from multiple runs
4. **Web dashboard?** - Flask server could show live progress

# Isolated LLM Evaluation Architecture

## Problem

Current setup lets LLM read game data files directly via bash, which is "cheating" - the LLM should learn through interaction, not by reading implementation details.

## New Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LLM Container (isolated)                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  LLM Agent                                                 │  │
│  │  - Cohere API access (outbound only)                      │  │
│  │  - Fresh bash (empty workspace, no game files)            │  │
│  │  - Can only interact via HTTP to game server              │  │
│  │  - Scratch space for notes/planning                       │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              │ HTTP (internal network)           │
│                              ▼                                   │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Game Server Container                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Factorio Simulation                                       │  │
│  │  - All source code and data files                         │  │
│  │  - REST API endpoints (action execution)                  │  │
│  │  - Info endpoints (recipes, tech, help)                   │  │
│  │  - NO file system access exposed                          │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## What LLM CAN Do

1. **Game Actions** (via HTTP):
   - `mine`, `craft`, `place`, `research`, `next`, `limit`, `launch`

2. **Query Game State** (via HTTP):
   - Get inventory
   - Get available recipes (names only, not full details)
   - Get researchable technologies
   - Get production stats

3. **Get Help** (via HTTP):
   - `info <item>` - Recipe requirements for a specific item
   - `help <command>` - How to use a command
   - Error messages explain what went wrong

4. **Bash** (isolated sandbox):
   - Write notes to scratch files
   - Basic calculations
   - NO access to game data/source files

## What LLM CANNOT Do

1. Read source code (`sim.py`, `server.py`, etc.)
2. Read data files (`data/recipe.json`, `data/technology.json`)
3. See implementation details
4. Access the game server filesystem

## Information Discovery

The LLM must learn through:

1. **Trial and error** - Try crafting, see what fails
2. **Error messages** - "Missing 5 iron-plate" tells them the recipe
3. **Info command** - Explicitly ask about specific items
4. **State observation** - See what's in inventory after actions
5. **Research unlocks** - Discover new recipes through gameplay

## API Endpoints (Game Server)

### Actions (POST)
```
POST /action/mine?resource=iron-ore&amount=50
POST /action/craft?item=iron-gear-wheel&amount=10
POST /action/place?machine=stone-furnace&item=iron-plate
POST /action/research?tech=automation
POST /action/next?minutes=5
POST /action/limit?item=iron-plate&amount=100
POST /action/launch
```

### Queries (GET)
```
GET /state              # Full game state (inventory, machines, time)
GET /recipes            # List of available recipe NAMES (not details)
GET /technologies       # List of researchable tech NAMES
GET /production         # Production statistics
GET /info?item=X        # Recipe details for specific item
GET /help?topic=X       # Help on commands
```

## Docker Compose Setup

```yaml
version: '3.8'

services:
  game-server:
    build:
      context: .
      dockerfile: Dockerfile.server
    networks:
      - game-net
    # No ports exposed to host - only internal

  llm-agent:
    build:
      context: .
      dockerfile: Dockerfile.agent
    environment:
      - COHERE_API_KEY=${COHERE_API_KEY}
      - GAME_SERVER_URL=http://game-server:5000
    networks:
      - game-net
    volumes:
      - ./results:/app/results
    depends_on:
      - game-server

networks:
  game-net:
    driver: bridge
```

## Dockerfile.server (Game Server)

```dockerfile
FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL game code and data
COPY . .

# Run Flask server
EXPOSE 5000
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0"]
```

## Dockerfile.agent (LLM Agent - Isolated)

```dockerfile
FROM python:3.11-slim
WORKDIR /app

# Only install what agent needs
RUN pip install --no-cache-dir cohere requests

# Copy ONLY agent code (no game files)
COPY llm_agent.py .
COPY agent_client.py .
COPY evaluation.py .
COPY metrics.py .
COPY run_llm_eval.py .

# Create scratch space for agent
RUN mkdir -p /app/scratch /app/results

# Non-root user
RUN useradd -m agent && chown -R agent:agent /app
USER agent

CMD ["python", "run_llm_eval.py", "--help"]
```

## Agent Client (Replaces Direct Harness)

```python
# agent_client.py - HTTP client for LLM to interact with game server

class GameClient:
    def __init__(self, server_url: str):
        self.server_url = server_url

    def execute_action(self, action: str) -> dict:
        """Send action to game server, get result."""
        # Parse action and call appropriate endpoint
        ...

    def get_state(self) -> dict:
        """Get current game state."""
        ...

    def get_info(self, item: str) -> str:
        """Get recipe info for item."""
        ...
```

## Restricted Bash for Agent

The agent gets bash, but in an empty environment:

```python
# Only these paths accessible:
allowed_paths = [
    "/app/scratch",  # Agent's notes
    "/app/results",  # Output
]

# NO access to:
# - /app/data/
# - /app/*.py (game code)
# - /app/docs/ (might have hints)
```

## Migration Path

1. Create `Dockerfile.server` and `Dockerfile.agent`
2. Create `agent_client.py` (HTTP client)
3. Update `server.py` with cleaner REST API
4. Update `run_llm_eval.py` to use client
5. Update `docker-compose.yml` for two containers
6. Test isolation

## Benefits

1. **Fair evaluation** - LLM can't cheat by reading files
2. **Realistic** - Mimics how a human would learn (trial + error)
3. **Measurable** - Can track how much the LLM explores
4. **Secure** - Full isolation between containers

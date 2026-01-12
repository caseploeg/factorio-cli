# LLM Evaluation Testbed - Architecture & Flow

## Overview

This testbed evaluates LLM agents playing Factorio in isolated Docker containers with automatic metrics collection.

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Container                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   LLM Agent                             │ │
│  │  (Cohere API / Other)                                   │ │
│  │         │                                               │ │
│  │         ▼                                               │ │
│  │  ┌─────────────┐    ┌──────────────┐                   │ │
│  │  │   Harness   │───►│  Simulation  │                   │ │
│  │  │  (actions)  │◄───│   (Factorio) │                   │ │
│  │  └─────────────┘    └──────────────┘                   │ │
│  │         │                                               │ │
│  │         ▼                                               │ │
│  │  ┌─────────────────┐     ┌──────────────────┐          │ │
│  │  │ RestrictedBash  │     │ MetricsCollector │          │ │
│  │  │ (game data)     │     │ (auto-save)      │          │ │
│  │  └─────────────────┘     └──────────────────┘          │ │
│  └────────────────────────────────────────────────────────┘ │
│                              │                               │
│                              ▼                               │
│                    /app/results/ (volume mount)              │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    ./results/ (host persists)
```

## Core Components

### 1. LLM Harness (`llm_harness.py`)

Direct interface to Factorio simulation, bypassing HTTP.

**Capabilities:**
- Game actions: `mine`, `craft`, `place`, `research`, `next`, `limit`, `launch`
- Information: `info <item>` - recipe/tech requirements
- Exploration: `bash <command>` - restricted shell access to game data

**Key Classes:**
```python
FactorioHarness(enable_bash=True, bash_security=SecurityLevel.MODERATE)
GameObservation  # Current game state
ActionResult     # Result of an action
```

### 2. Restricted Bash (`restricted_bash.py`)

Sandboxed shell access for LLM to explore game data.

**Security Layers:**
| Layer | Protection |
|-------|------------|
| Command whitelist | Only `cat`, `grep`, `ls`, `head`, etc. |
| Blocked commands | `rm`, `chmod`, `sudo`, `ssh`, etc. |
| Pattern blocking | No `;`, `|`, `>`, `$()` |
| Path restrictions | Only `data/` and `docs/` directories |
| Timeout | 5 seconds max |
| Output limit | 10KB max |

**Example allowed commands:**
```bash
bash ls data/
bash cat data/recipe.json
bash grep rocket data/technology.json
bash head -20 data/assembling-machine.json
```

### 3. LLM Agent (`llm_agent.py`)

Agent implementations that play the game.

**Available Agents:**
- `CohereAgent` - Uses Cohere API (command-r-plus default)
- `RandomAgent` - Baseline random actions
- `ScriptedAgent` - Follows predefined script

**System Prompt Philosophy:**
The agent receives:
- The goal: "Launch a rocket (100 rocket-parts)"
- Available tools: bash, info, game actions
- NO explicit sub-goals or strategy tips

The agent must explore game data to discover:
- What recipes exist
- What technologies unlock what
- How machines work
- Dependency chains

### 4. Metrics Collector (`metrics.py`)

Automatic metrics collection with guaranteed persistence.

**Features:**
- Auto-save on exit (normal or crash)
- Signal handlers (SIGTERM, SIGINT)
- Periodic checkpoints
- JSON export

**Metrics Collected:**
```json
{
  "run_id": "20240115_143022",
  "agent_type": "CohereAgent",
  "model": "command-r-plus",
  "game_won": false,
  "total_turns": 500,
  "game_time_hours": 12.5,
  "success_rate": 0.78,
  "action_counts": {
    "mine": 45,
    "craft": 120,
    "place": 30,
    "bash": 25,
    "next": 150
  },
  "tech_researched": 8,
  "machines_placed": 15,
  "rocket_parts": 0,
  "bash_commands_run": 25,
  "bash_commands_blocked": 3
}
```

### 5. Evaluation Runner (`evaluation.py`)

Orchestrates evaluation runs with checkpointing.

**Features:**
- Configurable stopping conditions
- Checkpoint/resume support
- Multi-episode runs
- Progress callbacks

## Execution Flow

### 1. Container Startup

```bash
docker run --rm \
  -e COHERE_API_KEY="$KEY" \
  -v $(pwd)/results:/app/results \
  factorio-llm-eval \
  --agent cohere --max-turns 1000
```

### 2. Evaluation Loop

```
for each turn:
    1. Agent receives observation (inventory, machines, production)
    2. Agent decides action (may use bash to explore)
    3. Harness executes action
    4. Metrics collector records result
    5. Check stopping conditions
    6. Checkpoint if interval reached
```

### 3. Stopping Conditions

| Condition | Default |
|-----------|---------|
| Max turns | 1000 |
| Max game time | 24 hours |
| Consecutive failures | 20 |
| Game won | Stop on rocket launch |

### 4. Container Shutdown

```
1. MetricsCollector.save_final() called (atexit handler)
2. Final JSON written to /app/results/
3. Turn history written to /app/results/
4. Container exits
5. Results persist in host ./results/
```

## File Outputs

After evaluation, the `./results/` directory contains:

```
results/
├── metrics_20240115_143022_final.json    # Summary metrics
├── history_20240115_143022.jsonl         # Turn-by-turn log
├── evaluation_summary.json               # Multi-episode summary
└── logs/
    └── eval_20240115_143022.log          # Detailed log
```

## Running Evaluations

### Quick Local Test

```bash
# Random agent (no API key needed)
python run_llm_eval.py --agent random --max-turns 100

# With Cohere
export COHERE_API_KEY="your-key"
python run_llm_eval.py --agent cohere --max-turns 500
```

### Docker Execution

```bash
# Build
./docker-run.sh build

# Run evaluation
./docker-run.sh run-cohere --turns 1000

# Or with docker directly
docker run --rm \
  -e COHERE_API_KEY="$COHERE_API_KEY" \
  -v $(pwd)/results:/app/results \
  factorio-llm-eval \
  --agent cohere --max-turns 1000

# Compare agents
./docker-run.sh run-compare --episodes 3
```

### Long-Running Evaluation

```bash
# Background execution with restart policy
docker run -d \
  --name factorio-eval \
  --restart unless-stopped \
  -e COHERE_API_KEY="$KEY" \
  -v $(pwd)/results:/app/results \
  factorio-llm-eval \
  --agent cohere --max-turns 10000

# Monitor
docker logs -f factorio-eval

# Results available immediately in ./results/
```

## Agent Prompt Design

The default prompt gives minimal guidance:

```
GOAL: Launch a rocket (100 rocket-parts)

EXPLORATION TOOLS:
- info <item>: Get recipe requirements
- bash <command>: Read game data files

GAME ACTIONS:
- mine, craft, place, research, next, limit, launch

Explore the data files to understand what's possible.
```

The agent must:
1. Use `bash ls data/` to discover available data
2. Use `bash grep` / `bash cat` to understand recipes
3. Use `info` to get specific item requirements
4. Figure out the production chain from raw resources to rocket-parts

## Security Model

### In Docker (Recommended)

```
┌─────────────────────────────────────┐
│  Container                          │
│  ├── Non-root user (evaluser)      │
│  ├── Read-only filesystem (opt)    │
│  ├── No network (opt)              │
│  ├── Memory/CPU limits             │
│  └── Only /app/results writable    │
└─────────────────────────────────────┘
```

### RestrictedBash (Defense in Depth)

Even if Docker isolation fails:
- Only whitelisted commands run
- Only project data directories accessible
- No command chaining or injection
- Timeout prevents infinite loops
- Output size capped

## Metrics Analysis

After runs complete:

```python
import json
from pathlib import Path

# Load all metrics
results = Path("results")
metrics = []
for f in results.glob("metrics_*_final.json"):
    with open(f) as fp:
        metrics.append(json.load(fp))

# Analyze
for m in metrics:
    print(f"{m['run_id']}: won={m['game_won']}, "
          f"turns={m['total_turns']}, "
          f"success_rate={m['success_rate']:.1%}")
```

## Extending the System

### Adding a New Agent

```python
class MyAgent(BaseAgent):
    def get_action(self, observation, last_result=None):
        # Your logic here
        return "mine iron-ore 50"
```

### Custom Metrics

```python
collector = MetricsCollector()
collector.record_turn(turn, action, success, message, game_time)
collector.record_game_state(tech, machines, parts, items)
# Auto-saved on exit
```

### Different LLM Provider

```python
class OpenAIAgent(BaseAgent):
    def __init__(self, config, api_key):
        self.client = openai.OpenAI(api_key=api_key)
        # ...
```

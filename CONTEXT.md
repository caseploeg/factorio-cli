# Factorio-CLI Context & Development Plan

## Project Overview

**Tagline:** Simulate 10 hours of gameplay in < 1 minute on the command line.

Factorio-cli is a text-based simulation of the game Factorio, designed for speedrun planning. It's turn-based Factorio where each in-game action has been abstracted into a text command. The simulation is deterministic, allowing for precise planning and optimization.

**Origin Story:** Started as a way to bring programming skills into game planning - instead of spreadsheets, use code. Evolved from a simple recipe calculator into a full turn-based simulation with automated production tracking.

## Architecture

### Layer Structure
```
shell.py (CLI interface)
    ↓
client.py (HTTP client)
    ↓
server.py (Flask web server + API)
    ↓
sim.py (Game simulation engine)
```

### Core Files

- **sim.py** - Game simulation engine
  - `Sim` class manages all game state
  - Inventory system with `defaultdict(int)`
  - Machine placement and production
  - Time-based simulation
  - Research/technology tree
  - Serialization/deserialization for save files

- **server.py** - Flask web server
  - REST API exposing simulation functions
  - Rate limiting (10,000 requests/hour)
  - SSE (Server-Sent Events) for live updates (`/ping`, `/stateping`)
  - Request history tracking
  - Web frontend at root route

- **client.py** - HTTP client library
  - Glue between CLI and server
  - Server URL from `SERVER_URL` environment variable
  - Maps each CLI command to HTTP endpoint

- **shell.py** - CLI interface
  - Built on cmd2 framework
  - Auto-completion for items, recipes, technologies
  - Color-coded suggestions (green=available, red=unavailable)
  - Hooks for prompt updates and alias conversion
  - Table formatting for production statistics

### Supporting Modules

- **craft.py** - Crafting logic
  - Recursive ingredient checking
  - Returns: success/failure, missing items, available items
  - Handles bulk recipe production

- **utils.py** - Stateless utility functions
  - `shopping_list()` - recursive ingredient calculator
  - `tech_needed()` - technology tree traversal
  - Machine compatibility checks

- **data.py** - Static game data operations
  - `craft_time()` calculation
  - `is_machine_compatible()` validation

- **init.py** - Initial game state
  - Starter inventory (1 stone-furnace, 1 burner-mining-drill, 5 iron-plate, 1B water)
  - Empty tech tree at start
  - Enabled recipes only

- **files.py** - Data loading
  - Loads 8 JSON files from Factorio mod export
  - Maps to structured dictionaries

- **shortcuts.py** - Command aliases
  - Common abbreviations (sf=stone-furnace, bmd=burner-mining-drill, etc.)

- **errors.py** - Custom exceptions
  - Error hierarchy for different failure modes

- **fbot.py** - Simple bot implementation
  - Random mining and crafting
  - Demonstrates automation potential
  - Currently doesn't do research

### Data Files (from Factorio mod)

Located in `/data/`:
- `recipe.json` - All crafting recipes
- `technology.json` - Tech tree
- `mining-drill.json` - Mining equipment stats
- `resource.json` - Minable resources
- `furnace.json` - Smelting equipment
- `assembling-machine.json` - Assembly machines
- `rocket-silo.json` - Rocket launch data
- `machines.json` - Machine type mapping (0=miner, 1=assembler, 2=furnace)

## Core Features

### Simulation Features
- Inventory management
- Resource mining (stone, coal, iron-ore, copper-ore, crude-oil)
- Item crafting with time calculation
- Technology research
- Machine placement (miners, furnaces, assemblers)
- Automated production with priority system
- Production rate limiting
- Time advancement
- Rocket launching (win condition: 100 rocket-parts)
- Save/load game state (deterministic JSON)

### CLI Commands

**Core Actions:**
- `mine <resource> <amount>` - Manual resource gathering
- `craft <item> <amount>` - Craft items in inventory
- `place <machine> <item> <amount>` - Deploy automated machines
- `research <tech>` - Unlock new recipes
- `next <minutes>` - Advance time and run production
- `launch` - Launch rocket if 100 parts available

**Information:**
- `inventory` - Show current items
- `prod` - Production statistics (actual vs potential per minute)
- `cookbook` - Available recipes
- `wish <item> <amount>` - Show ingredient tree
- `tech_needed <tech>` - Show tech prerequisites
- `time` - Game time elapsed

**Management:**
- `limit <item> <amount>` - Cap production of specific items
- `limits` - Show current limits
- `prio <machine> <item> <old> <new>` - Change machine priority
- `save <file>` - Export game state
- `load <file>` - Import game state
- `spawn <item> <amount>` - Cheat items in (debug)
- `clear` - Reset simulation

**Aliases:** Defined in `scripts/startup.txt`
- `lprod` / `prodl` - Production with paging
- `raw` - Filter production for ores/plates
- `science` - Filter production for science packs

### Production System

**Machine Priority:**
Machines are keyed as `{item}:{machine}:{priority}` where priority is an integer (default 0). Lower priority machines process first. This controls resource allocation when supplies are limited.

**Production Algorithm (sim.py:48-117):**
1. For each machine (sorted by priority):
   - Calculate **potential** production (machine_count × speed × time / energy)
   - Calculate **actual** production (min of potential and available ingredients)
   - Respect rate limits if set
   - Deduct ingredients from inventory
   - Add products to inventory
2. Returns production stats showing actual vs potential rates

**Rate Limiting:**
Prevents waste on low-priority items. Format: `limit <item> <amount>` caps total inventory. Production stops when limit reached.

**Bottleneck Detection:**
The system calculates the limiting ingredient ratio (sim.py:82-83) but doesn't currently expose this to players.

## Testing Strategy

**End-to-End Deterministic Testing:**
Since the simulation is deterministic (same commands = same save file), tests consist of:
1. Script file with commands (`testcases/export.txt`)
2. Expected save file in `expected/`
3. `run_tests.sh` compares outputs

This approach:
- Tests real usage scenarios
- Catches breaking changes
- Easy to create new tests
- Covers full stack

**Test Script:** `./run_tests.sh`

## Data Flow

### Time & Crafting
1. Crafting/mining calculates time required
2. `next(seconds)` is called automatically
3. All machines produce during time advancement
4. Bulk recipes handled (e.g., concrete produces 10 units)
5. Excess production from rounding goes to player inventory

### State Management
All state in `Sim` class:
- `game_time` - Seconds elapsed
- `current_tech` - Set of researched technologies
- `current_recipes` - Set of unlocked recipes
- `current_items` - Counter of inventory items
- `machines` - Counter keyed by `{item}:{machine}:{priority}`
- `limited_items` - Dict of production caps

Serialization is deterministic (sorted keys) for testing.

## Known Issues & TODOs

### Code TODOs (from source)

**client.py:11**
- Need better cross-referencing between client and server code
- Idea: Add hyperlinks or clearer mapping

**sim.py:29**
- Error messages on crafting should return full missing item list

**sim.py:82**
- Surface bottleneck information to the player
- Currently calculated but not displayed

**sim.py:94**
- Machine processing order matters (inventory affected immediately)
- Users probably want more control of ordering
- Deterministic ordering needed for testing

**sim.py:212**
- Verify `grant_excess_production()` is correct
- Handles bulk recipe rounding

**fbot.py:11**
- Bot doesn't do research
- Could be enhanced for more sophisticated automation

**shell.py:22**
- Mineable resource list is hardcoded
- Should be moved/refactored

**shell.py:152**
- `place` command should only show machines in inventory
- Currently shows all machines

**shell.py:168**
- Make machine choices work with aliases

**shell.py:203**
- Server should send JSON instead of string representation
- Current production endpoint returns Python string

**shell.py:220**
- Add caching to reduce HTTP requests
- `craft_item_choices()` makes many requests

**server.py:138**
- Improve result handling beyond simple success/fail

**server.py:152**
- Sim functions don't return anything on success
- Inconsistent with error case

**server.py:199**
- Limits endpoint needs error handling

### Feature TODOs (from todo.md)

#### Rate Limiting Improvements
- Priority system for assemblers (which gets resources first?)
- Sane defaults for rate-limiting (global cap 10 items/min?)
- Warning when crafting rate-limited items
- Better feedback when crafting fails due to limits

#### Production Statistics
- Better visibility into what's happening
- History of transactions/production logs
- Projected inventory diff over time
- Failed research should show missing materials
- Percentage breakdown of resource usage per recipe
- Show production stats for all recipe ingredients

#### Error Handling
- Inconsistent exception usage
- Need detailed error messages for failed crafting
- Show exactly which items are missing

#### Simulation Features
- Labs/research should happen in background like other machines
  - Track research progress
  - Notify when complete
- Chemistry recipes (oil-processing category)
- Fluid handling for mining drills
- Energy consumption system

#### Shell Commands
- New: `limits` command to output current rate-limited items
- Script to visualize tech tree
- Script to visualize inventory over time
- Bug: Negative limits break production graph scaling
- Bug: Can place steel-smelting furnace before researching steel-processing

#### Potential Features
- Electricity system
- Web frontend improvements
  - Research feedback (show unlocked recipes)
  - Mobile-friendly (3 buttons)
  - Better inventory parsing/display
  - Cookie-clicker style animations
  - CLI-like appearance
- Bot development
  - Simple but eventually successful bot
  - Sophisticated optimization bot
  - Optimal path finding

#### Infrastructure
- Better exporting/sharing/saving
- Traffic analytics for web version
- Active user tracking

## Current Limitations

1. **Multi-product recipes not supported** - Only first product obtained
2. **Infinite water** - Players get 1 billion water at start
3. **No fluid system** - Simplified for now
4. **No electricity** - Power not simulated
5. **No pollution/biters** - Combat removed
6. **Chemistry recipes incomplete** - Oil processing limited
7. **Research not automated** - Must be done manually (labs don't run in background)

## Development Priorities

### High Priority
1. **Production visibility** - Players can't see what's happening
   - Better logging
   - Bottleneck indicators
   - Resource flow breakdown
2. **Error messaging** - Make failures informative
3. **Rate limiting UX** - Warnings and feedback

### Medium Priority
1. **Server-client consistency** - Return JSON everywhere
2. **Performance** - Caching, reduce HTTP requests
3. **Machine priority system** - User control over resource allocation
4. **Inventory-aware completions** - Only suggest placeable machines

### Low Priority
1. **Background research** - Labs as production machines
2. **Chemistry/fluids** - Oil processing
3. **Electricity** - Power simulation
4. **Web frontend polish** - Mobile UX, animations
5. **Bot sophistication** - Optimization algorithms

## Future Directions

### Cool Software Ideas
- Advanced bots with different strategies
- Visualizations (tech tree, production graphs, inventory timeline)
- Multiplayer support
- Speedrun leaderboards
- Optimization challenges

### Technical Improvements
- GraphQL or better REST conventions
- WebSocket for real-time updates
- Better state diffing for web frontend
- Plugin system for custom commands
- Replay system for sharing strategies

## Getting Started (for Developers)

### Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
source ./setupdevenv.sh
```

### Running
Terminal 1 (server):
```bash
flask --app server run
```

Terminal 2 (client):
```bash
python3 ./main.py
```

### Testing
```bash
./run_tests.sh
```

### Data Extraction
Uses [Data Exporter to JSON](https://mods.factorio.com/mod/recipelister) Factorio mod by Erythion.

## Key Design Principles

1. **Deterministic** - Same inputs always produce same outputs (critical for testing)
2. **Text-first** - Everything accessible via CLI
3. **Composable** - Tools can be piped and scripted
4. **Portable** - JSON state files, plain text commands
5. **Transparent** - See the data, understand the systems
6. **Extensible** - Bot-friendly, scriptable

## Code Patterns

### State Mutations
Most methods in `Sim` return `(result_code, message)`:
- `res=0` means success
- `res=1` means user error (wrong item, missing resources)
- `res=2` means can't recurse further (missing raw materials)

### Inventory Operations
- Use `defaultdict(int)` for automatic 0-initialization
- Always use integer amounts (avoid floating point issues)
- Deduct after validation (don't need to rollback)

### Time Simulation
- All times in seconds
- Energy field in recipes = crafting time at speed 1
- Speed modifiers from machines
- Bulk recipes handled via `main_product.amount`

### Testing Pattern
1. Write script in `scripts/` or `testcases/`
2. Run and save output
3. Move to `expected/`
4. Script becomes regression test

## Web Frontend

Located at server root (`/`):
- Uses Server-Sent Events for live updates
- Shows production stats, game state, request history
- Commit hash displayed (from `commit_hash.txt`)
- Basic mobile interface (in progress)

### API Endpoints

**GET:**
- `/time` - Game seconds
- `/cookbook` - Available recipes
- `/limits` - Rate-limited items
- `/suggest` - Researchable technologies
- `/production` - Production stats
- `/inventory` - Current items
- `/craftable?item=X&amount=N` - Check if craftable
- `/state` - Full game state JSON
- `/ping` - SSE stream (production + state + history)
- `/stateping` - SSE stream (state only)
- `/history` - Request history

**POST:**
- `/clear` - Reset game
- `/update` - Load game state
- `/spawn?item=X&amount=N` - Cheat items
- `/research?technology=X` - Research tech
- `/researchable?technology=X` - Check if researchable
- `/place?machine=X&item=Y&amount=N` - Place machine
- `/prio?machine=X&item=Y&oldprio=A&newprio=B` - Change priority
- `/next?minutes=N` - Advance time
- `/craft?item=X&amount=N` - Craft item
- `/mine?resource=X&amount=N` - Mine resource
- `/limit?item=X&amount=N` - Set production limit
- `/launch` - Launch rocket

## Questions for Future Exploration

1. What would a simple but eventually successful bot look like?
2. What does a sophisticated optimization bot look like?
3. What does an optimal speedrun path look like?
4. How to visualize the tech tree effectively?
5. How to make multiplayer work?
6. What analytics would be most useful for speedrunning?

---

**Last Updated:** 2026-01-04
**Created By:** Automated documentation collection

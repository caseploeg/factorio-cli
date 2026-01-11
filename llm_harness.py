"""
LLM Simulation Harness for Factorio CLI

Provides a minimal interface for LLM agents to play the Factorio simulation.
Bypasses HTTP layer for direct simulation access.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any
from collections import defaultdict

from sim import Sim
from files import load_files
from utils import shopping_list, tech_needed, get_potion_list
from restricted_bash import RestrictedBash, BashConfig, SecurityLevel, BashResult


@dataclass
class ActionResult:
    """Result of executing an action in the simulation."""
    success: bool
    action: str
    message: str
    state_before: dict = field(default_factory=dict)
    state_after: dict = field(default_factory=dict)
    game_time_delta: float = 0.0


@dataclass
class GameObservation:
    """Observable game state for the LLM agent."""
    game_time: float
    inventory: Dict[str, int]
    machines: Dict[str, int]
    available_recipes: List[str]
    researched_tech: List[str]
    researchable_tech: List[str]
    production_rates: List[Dict]
    limited_items: Dict[str, int]

    def to_prompt_string(self) -> str:
        """Convert observation to a string suitable for LLM prompts."""
        lines = [
            f"=== GAME STATE ===",
            f"Time Elapsed: {self.game_time:.0f} seconds ({self.game_time/3600:.1f} hours)",
            "",
            "INVENTORY:",
        ]

        # Show non-zero inventory items
        inv_items = {k: v for k, v in self.inventory.items() if v > 0}
        if inv_items:
            for item, count in sorted(inv_items.items()):
                lines.append(f"  {item}: {count}")
        else:
            lines.append("  (empty)")

        lines.append("")
        lines.append("MACHINES RUNNING:")
        if self.machines:
            for machine_key, count in sorted(self.machines.items()):
                if count > 0:
                    lines.append(f"  {machine_key}: {count}")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append("PRODUCTION (per minute):")
        if self.production_rates:
            for prod in self.production_rates:
                item = prod[0]
                actual = prod[1]
                potential = prod[2]
                inv = prod[3]
                limit = prod[4] if prod[4] != '' else 'none'
                lines.append(f"  {item}: {actual}/{potential} (inv: {inv}, limit: {limit})")
        else:
            lines.append("  (no production)")

        lines.append("")
        lines.append(f"RESEARCHABLE TECH: {', '.join(sorted(self.researchable_tech)[:10])}")
        if len(self.researchable_tech) > 10:
            lines.append(f"  ... and {len(self.researchable_tech) - 10} more")

        return "\n".join(lines)


class FactorioHarness:
    """
    Minimal harness for LLM agents to interact with Factorio simulation.

    Provides:
    - Direct simulation access (no HTTP overhead)
    - Action parsing and execution
    - State observation
    - Save/load for checkpointing
    """

    AVAILABLE_ACTIONS = [
        "mine <resource> <amount>",
        "craft <item> [amount]",
        "place <machine> <item> [amount]",
        "research <technology>",
        "next [minutes]",
        "limit <item> <amount>",
        "prio <machine> <item> <old_prio> <new_prio>",
        "launch",
        "bash <command>",
        "info <item>",
    ]

    MINEABLE_RESOURCES = ['stone', 'coal', 'iron-ore', 'copper-ore']

    def __init__(self, data_dict: Optional[dict] = None, enable_bash: bool = True,
                 bash_security: SecurityLevel = SecurityLevel.MODERATE):
        """Initialize the harness with game data."""
        if data_dict is None:
            data_dict = load_files()
        self.data_dict = data_dict
        self.sim = Sim(data_dict)
        self.action_history: List[ActionResult] = []
        self.turn_count = 0

        # Initialize restricted bash if enabled
        self.bash_enabled = enable_bash
        if enable_bash:
            import os
            project_dir = os.path.dirname(os.path.abspath(__file__))
            bash_config = BashConfig(
                security_level=bash_security,
                timeout=5.0,
                allowed_paths=[
                    os.path.join(project_dir, "data"),
                    os.path.join(project_dir, "docs"),
                ],
                working_dir=project_dir,
            )
            self.bash = RestrictedBash(bash_config)
        else:
            self.bash = None

    def reset(self) -> GameObservation:
        """Reset the simulation to initial state."""
        self.sim.clear()
        self.action_history = []
        self.turn_count = 0
        return self.get_observation()

    def get_observation(self) -> GameObservation:
        """Get current observable game state."""
        return GameObservation(
            game_time=self.sim.game_time,
            inventory=dict(self.sim.current_items),
            machines=dict(self.sim.machines),
            available_recipes=sorted(list(self.sim.current_recipes)),
            researched_tech=sorted(list(self.sim.current_tech)),
            researchable_tech=sorted(list(self.sim.all_researchable())),
            production_rates=self.sim.production(),
            limited_items=dict(self.sim.limited_items),
        )

    def get_action_prompt(self) -> str:
        """Get available actions as a prompt string."""
        lines = [
            "=== AVAILABLE ACTIONS ===",
            "",
            "MINING (manual resource gathering):",
            f"  mine <resource> <amount>  - Resources: {', '.join(self.MINEABLE_RESOURCES)}",
            "",
            "CRAFTING (uses inventory items, takes time):",
            "  craft <item> [amount]  - Craft items from your recipe book",
            "",
            "MACHINES (automate production):",
            "  place <machine> <item> [amount]  - Place machines from inventory",
            "    - burner-mining-drill: mines resources automatically",
            "    - stone-furnace: smelts ore into plates",
            "    - assembling-machine-1/2/3: crafts items automatically",
            "",
            "RESEARCH (unlock new recipes):",
            "  research <technology>  - Requires science packs in inventory",
            "",
            "TIME (advance simulation):",
            "  next [minutes]  - Run factory for N minutes (default: 1)",
            "",
            "LIMITS (control production):",
            "  limit <item> <amount>  - Cap production of an item",
            "",
            "INFORMATION:",
            "  info <item>  - Get recipe/research requirements for an item",
        ]

        if self.bash_enabled:
            lines.extend([
                "",
                "BASH (read game data files):",
                "  bash <command>  - Run restricted shell command",
                "    Examples:",
                "      bash cat data/recipe.json | head -20",
                "      bash grep iron data/recipe.json",
                "      bash ls data/",
            ])

        lines.extend([
            "",
            "GOAL:",
            "  launch  - Launch rocket (requires 100 rocket-parts)",
            "",
            "Respond with a single action in the format shown above.",
        ])
        return "\n".join(lines)

    def execute_action(self, action_str: str) -> ActionResult:
        """
        Parse and execute an action string from the LLM.

        Returns ActionResult with success status and any messages.
        """
        self.turn_count += 1
        state_before = json.loads(self.sim.serialize_state())
        time_before = self.sim.game_time

        action_str = action_str.strip()

        # Parse the action
        parts = action_str.split()
        if not parts:
            return ActionResult(
                success=False,
                action=action_str,
                message="Empty action",
                state_before=state_before,
            )

        cmd = parts[0].lower()
        # For bash commands, preserve case in arguments
        if cmd == "bash":
            args = parts[1:]
        else:
            args = [a.lower() for a in parts[1:]]

        try:
            result = self._execute_command(cmd, args)
        except Exception as e:
            result = ActionResult(
                success=False,
                action=action_str,
                message=f"Error: {str(e)}",
            )

        result.state_before = state_before
        result.state_after = json.loads(self.sim.serialize_state())
        result.game_time_delta = self.sim.game_time - time_before
        result.action = action_str

        self.action_history.append(result)
        return result

    def _execute_command(self, cmd: str, args: List[str]) -> ActionResult:
        """Execute a parsed command."""

        if cmd == "mine":
            if len(args) < 2:
                return ActionResult(False, cmd, "Usage: mine <resource> <amount>")
            resource, amount = args[0], int(args[1])
            if resource not in self.MINEABLE_RESOURCES:
                return ActionResult(False, cmd, f"Cannot mine {resource}. Valid: {self.MINEABLE_RESOURCES}")
            res, msg = self.sim.mine(resource, amount)
            return ActionResult(res == 0, cmd, msg or f"Mined {amount} {resource}")

        elif cmd == "craft":
            if len(args) < 1:
                return ActionResult(False, cmd, "Usage: craft <item> [amount]")
            item = args[0]
            amount = int(args[1]) if len(args) > 1 else 1
            if item not in self.sim.current_recipes:
                return ActionResult(False, cmd, f"Recipe '{item}' not available. Research required?")
            res, msg = self.sim.craft(item, amount)
            return ActionResult(res == 0, cmd, msg or f"Crafted {amount} {item}")

        elif cmd == "place":
            if len(args) < 2:
                return ActionResult(False, cmd, "Usage: place <machine> <item> [amount]")
            machine, item = args[0], args[1]
            amount = int(args[2]) if len(args) > 2 else 1
            res, msg = self.sim.place_machine(machine, item, amount)
            return ActionResult(res == 0, cmd, msg or f"Placed {amount} {machine} producing {item}")

        elif cmd == "research":
            if len(args) < 1:
                return ActionResult(False, cmd, "Usage: research <technology>")
            tech = args[0]
            res, msg = self.sim.research(tech)
            return ActionResult(res == 0, cmd, msg or f"Researched {tech}")

        elif cmd == "next":
            minutes = int(args[0]) if args else 1
            self.sim.next(minutes * 60)
            return ActionResult(True, cmd, f"Advanced {minutes} minute(s)")

        elif cmd == "limit":
            if len(args) < 2:
                return ActionResult(False, cmd, "Usage: limit <item> <amount>")
            item, amount = args[0], int(args[1])
            self.sim.set_limit(item, amount)
            return ActionResult(True, cmd, f"Set limit on {item} to {amount}")

        elif cmd == "prio":
            if len(args) < 4:
                return ActionResult(False, cmd, "Usage: prio <machine> <item> <old_prio> <new_prio>")
            machine, item, old_prio, new_prio = args[0], args[1], int(args[2]), int(args[3])
            self.sim.set_machine_prio(machine, item, old_prio, new_prio)
            return ActionResult(True, cmd, f"Changed priority of {machine}/{item} from {old_prio} to {new_prio}")

        elif cmd == "launch":
            success = self.sim.launch()
            if success:
                return ActionResult(True, cmd, "ROCKET LAUNCHED! YOU WIN!")
            return ActionResult(False, cmd, "Not enough rocket parts (need 100)")

        elif cmd == "bash":
            if not self.bash_enabled:
                return ActionResult(False, cmd, "Bash access is disabled")
            if not args:
                return ActionResult(False, cmd, "Usage: bash <command>")
            # Rejoin args since bash command might have spaces
            bash_cmd = " ".join(args)
            result = self.bash.execute(bash_cmd)
            if result.blocked:
                return ActionResult(False, cmd, f"Blocked: {result.block_reason}")
            elif result.success:
                output = result.stdout.strip() or "(no output)"
                return ActionResult(True, cmd, output)
            else:
                error = result.stderr.strip() or f"Command failed with code {result.return_code}"
                return ActionResult(False, cmd, error)

        elif cmd == "info":
            if not args:
                return ActionResult(False, cmd, "Usage: info <item>")
            item = args[0]
            info = self.get_helper_info(item)
            return ActionResult(True, cmd, info)

        else:
            return ActionResult(False, cmd, f"Unknown command: {cmd}")

    def save_state(self) -> str:
        """Serialize current state for checkpointing."""
        return json.dumps({
            "sim_state": self.sim.serialize_state(),
            "turn_count": self.turn_count,
            "action_history": [
                {
                    "success": r.success,
                    "action": r.action,
                    "message": r.message,
                    "game_time_delta": r.game_time_delta,
                }
                for r in self.action_history
            ]
        })

    def load_state(self, state_json: str) -> None:
        """Load state from checkpoint."""
        data = json.loads(state_json)
        self.sim.deserialize_state(data["sim_state"])
        self.turn_count = data["turn_count"]
        self.action_history = [
            ActionResult(
                success=r["success"],
                action=r["action"],
                message=r["message"],
                game_time_delta=r["game_time_delta"],
            )
            for r in data["action_history"]
        ]

    def get_helper_info(self, item: str) -> str:
        """Get helpful information about an item (shopping list, tech requirements)."""
        lines = []

        if item in self.sim.data.recipes:
            lines.append(f"Recipe for {item}:")
            sh = shopping_list(self.sim.data.recipes, {item: 1})
            for ing, amt in sh.items():
                lines.append(f"  {ing}: {amt}")

        if item in self.sim.data.technology:
            lines.append(f"Research requirements for {item}:")
            packs = get_potion_list(self.sim.data.technology, item)
            for pack, amt in packs.items():
                lines.append(f"  {pack}: {amt}")

        return "\n".join(lines) if lines else f"No info found for {item}"

    def is_game_won(self) -> bool:
        """Check if the game has been won (rocket launched)."""
        # Check action history for successful launch
        for result in self.action_history:
            if result.action == "launch" and result.success:
                return True
        return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get current game metrics for evaluation."""
        obs = self.get_observation()
        return {
            "turn_count": self.turn_count,
            "game_time_seconds": self.sim.game_time,
            "game_time_hours": self.sim.game_time / 3600,
            "actions_successful": sum(1 for r in self.action_history if r.success),
            "actions_failed": sum(1 for r in self.action_history if not r.success),
            "success_rate": sum(1 for r in self.action_history if r.success) / max(1, len(self.action_history)),
            "unique_items_crafted": len([k for k, v in obs.inventory.items() if v > 0]),
            "machines_placed": sum(obs.machines.values()),
            "tech_researched": len(obs.researched_tech),
            "rocket_parts": obs.inventory.get("rocket-part", 0),
            "game_won": self.is_game_won(),
        }


# Convenience function for quick testing
def create_harness() -> FactorioHarness:
    """Create a new harness instance."""
    return FactorioHarness()


if __name__ == "__main__":
    # Quick test
    harness = create_harness()
    obs = harness.reset()
    print(obs.to_prompt_string())
    print()
    print(harness.get_action_prompt())

    # Test some actions
    print("\n--- Testing actions ---")
    print(harness.execute_action("mine iron-ore 50"))
    print(harness.execute_action("mine stone 20"))
    print(harness.execute_action("craft stone-furnace 2"))
    print(harness.execute_action("place stone-furnace iron-plate"))
    print()
    print(harness.get_observation().to_prompt_string())
    print()
    print("Metrics:", harness.get_metrics())

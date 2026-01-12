"""
Game Client for Isolated LLM Agent

HTTP client that communicates with the game server.
The agent uses this instead of direct harness access.
"""

import os
import requests
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class ActionResult:
    """Result of executing an action."""
    success: bool
    action: str
    message: str
    game_time: float = 0.0


@dataclass
class GameState:
    """Observable game state."""
    game_time: float
    inventory: Dict[str, int]
    machines: Dict[str, int]
    available_recipes: List[str]
    researched_tech: List[str]
    researchable_tech: List[str]
    production: List[Any]

    def to_prompt_string(self) -> str:
        """Format state for LLM prompt."""
        lines = [
            "=== GAME STATE ===",
            f"Time: {self.game_time:.0f}s ({self.game_time/3600:.1f}h)",
            "",
            "INVENTORY:",
        ]

        inv = {k: v for k, v in self.inventory.items() if v > 0}
        if inv:
            for item, count in sorted(inv.items()):
                lines.append(f"  {item}: {count}")
        else:
            lines.append("  (empty)")

        lines.append("")
        lines.append("MACHINES:")
        if self.machines:
            for key, count in sorted(self.machines.items()):
                if count > 0:
                    lines.append(f"  {key}: {count}")
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append(f"AVAILABLE RECIPES: {len(self.available_recipes)} recipes")
        lines.append(f"RESEARCHABLE: {', '.join(self.researchable_tech[:5])}")
        if len(self.researchable_tech) > 5:
            lines.append(f"  ...and {len(self.researchable_tech) - 5} more")

        return "\n".join(lines)


class GameClient:
    """
    HTTP client for LLM agent to interact with game server.

    Provides isolated access - agent cannot see game files.
    """

    def __init__(self, server_url: Optional[str] = None):
        self.server_url = server_url or os.environ.get(
            "GAME_SERVER_URL", "http://localhost:5000"
        )
        self.session = requests.Session()
        self.action_history: List[ActionResult] = []
        self.turn_count = 0

    def reset(self) -> GameState:
        """Reset game to initial state."""
        self.session.post(f"{self.server_url}/clear")
        self.action_history = []
        self.turn_count = 0
        return self.get_state()

    def get_state(self) -> GameState:
        """Get current game state."""
        resp = self.session.get(f"{self.server_url}/state")
        data = resp.json()

        return GameState(
            game_time=data.get("game_time", 0),
            inventory=data.get("current_items", {}),
            machines=data.get("machines", {}),
            available_recipes=data.get("current_recipes", []),
            researched_tech=data.get("current_tech", []),
            researchable_tech=self._get_researchable(),
            production=self._get_production(),
        )

    def _get_researchable(self) -> List[str]:
        """Get list of researchable technologies."""
        resp = self.session.get(f"{self.server_url}/suggest")
        return resp.text.strip().split() if resp.text.strip() else []

    def _get_production(self) -> List[Any]:
        """Get production statistics."""
        resp = self.session.get(f"{self.server_url}/production")
        # Production returns a string representation, parse it
        try:
            import ast
            return ast.literal_eval(resp.text) if resp.text else []
        except:
            return []

    def execute_action(self, action_str: str) -> ActionResult:
        """
        Execute an action and return result.

        Supported actions:
        - mine <resource> <amount>
        - craft <item> [amount]
        - place <machine> <item> [amount]
        - research <technology>
        - next [minutes]
        - limit <item> <amount>
        - launch
        - info <item>
        """
        self.turn_count += 1
        action_str = action_str.strip()
        parts = action_str.split()

        if not parts:
            return ActionResult(False, action_str, "Empty action")

        cmd = parts[0].lower()
        args = parts[1:]

        try:
            result = self._dispatch_action(cmd, args)
        except requests.RequestException as e:
            result = ActionResult(False, action_str, f"Server error: {e}")
        except Exception as e:
            result = ActionResult(False, action_str, f"Error: {e}")

        result.action = action_str
        result.game_time = self._get_time()
        self.action_history.append(result)
        return result

    def _dispatch_action(self, cmd: str, args: List[str]) -> ActionResult:
        """Route action to appropriate endpoint."""

        if cmd == "mine":
            if len(args) < 2:
                return ActionResult(False, cmd, "Usage: mine <resource> <amount>")
            resp = self.session.post(
                f"{self.server_url}/mine",
                params={"resource": args[0], "amount": args[1]}
            )
            return self._parse_response(resp, f"Mined {args[1]} {args[0]}")

        elif cmd == "craft":
            if len(args) < 1:
                return ActionResult(False, cmd, "Usage: craft <item> [amount]")
            amount = args[1] if len(args) > 1 else "1"
            resp = self.session.post(
                f"{self.server_url}/craft",
                params={"item": args[0], "amount": amount}
            )
            return self._parse_response(resp, f"Crafted {amount} {args[0]}")

        elif cmd == "place":
            if len(args) < 2:
                return ActionResult(False, cmd, "Usage: place <machine> <item> [amount]")
            amount = args[2] if len(args) > 2 else "1"
            resp = self.session.post(
                f"{self.server_url}/place",
                params={"machine": args[0], "item": args[1], "amount": amount}
            )
            return self._parse_response(resp, f"Placed {amount} {args[0]} for {args[1]}")

        elif cmd == "research":
            if len(args) < 1:
                return ActionResult(False, cmd, "Usage: research <technology>")
            resp = self.session.post(
                f"{self.server_url}/research",
                params={"technology": args[0]}
            )
            return self._parse_response(resp, f"Researched {args[0]}")

        elif cmd == "next":
            minutes = args[0] if args else "1"
            resp = self.session.post(
                f"{self.server_url}/next",
                params={"minutes": minutes}
            )
            return ActionResult(True, cmd, f"Advanced {minutes} minute(s)")

        elif cmd == "limit":
            if len(args) < 2:
                return ActionResult(False, cmd, "Usage: limit <item> <amount>")
            resp = self.session.post(
                f"{self.server_url}/limit",
                params={"item": args[0], "amount": args[1]}
            )
            return ActionResult(True, cmd, f"Set limit on {args[0]} to {args[1]}")

        elif cmd == "launch":
            resp = self.session.post(f"{self.server_url}/launch")
            if "LIFT OFF" in resp.text:
                return ActionResult(True, cmd, "ROCKET LAUNCHED! YOU WIN!")
            return ActionResult(False, cmd, resp.text)

        elif cmd == "info":
            if len(args) < 1:
                return ActionResult(False, cmd, "Usage: info <item>")
            return self._get_info(args[0])

        elif cmd == "recipes":
            # List available recipes (names only)
            resp = self.session.get(f"{self.server_url}/cookbook")
            recipes = resp.text.strip().split()
            return ActionResult(True, cmd, f"Available recipes: {', '.join(recipes[:20])}...")

        elif cmd == "help":
            return self._get_help(args[0] if args else None)

        else:
            return ActionResult(False, cmd, f"Unknown command: {cmd}")

    def _parse_response(self, resp: requests.Response, success_msg: str) -> ActionResult:
        """Parse server response into ActionResult."""
        if resp.status_code == 200:
            if "pog" in resp.text.lower() or resp.text == "":
                return ActionResult(True, "", success_msg)
            return ActionResult(True, "", resp.text or success_msg)
        else:
            return ActionResult(False, "", resp.text or "Action failed")

    def _get_time(self) -> float:
        """Get current game time."""
        try:
            resp = self.session.get(f"{self.server_url}/time")
            return float(resp.text)
        except:
            return 0.0

    def _get_info(self, item: str) -> ActionResult:
        """Get recipe information for an item."""
        # First check if it's a craftable item
        resp = self.session.get(f"{self.server_url}/cookbook")
        recipes = resp.text.strip().split()

        if item in recipes:
            # Get crafting requirements by trying to craft with 0 resources
            # The error message will tell us what's needed
            # This is a workaround since we don't expose recipe details directly
            resp = self.session.get(
                f"{self.server_url}/craftable",
                params={"item": item, "amount": 1}
            )

            # For now, return a hint that they should try crafting
            return ActionResult(
                True, "info",
                f"'{item}' is a craftable recipe. Try 'craft {item}' to see requirements."
            )
        else:
            return ActionResult(
                False, "info",
                f"'{item}' not found in available recipes. Research may be needed."
            )

    def _get_help(self, topic: Optional[str]) -> ActionResult:
        """Get help information."""
        if topic is None:
            help_text = """
Available commands:
  mine <resource> <amount>  - Mine: iron-ore, copper-ore, stone, coal
  craft <item> [amount]     - Craft item (need ingredients in inventory)
  place <machine> <item>    - Place machine to automate production
  research <technology>     - Research tech (need science packs)
  next [minutes]            - Advance time (let machines work)
  limit <item> <amount>     - Limit production rate
  launch                    - Launch rocket (need 100 rocket-parts)
  info <item>               - Get info about an item
  recipes                   - List available recipes
  help [topic]              - Show this help

Goal: Launch a rocket! You need 100 rocket-parts.
"""
            return ActionResult(True, "help", help_text.strip())
        else:
            return ActionResult(True, "help", f"No detailed help for '{topic}'")

    def get_action_prompt(self) -> str:
        """Get prompt describing available actions."""
        return """
ACTIONS:
  mine <resource> <amount>  - Mine raw resources
  craft <item> [amount]     - Craft items (need materials)
  place <machine> <item>    - Automate production
  research <technology>     - Unlock new recipes
  next [minutes]            - Let time pass
  info <item>               - Get recipe info
  recipes                   - List craftable items
  launch                    - Win the game!

GOAL: Launch a rocket (requires 100 rocket-parts)
""".strip()

    def get_metrics(self) -> Dict[str, Any]:
        """Get evaluation metrics."""
        state = self.get_state()
        return {
            "turn_count": self.turn_count,
            "game_time_seconds": state.game_time,
            "actions_successful": sum(1 for r in self.action_history if r.success),
            "actions_failed": sum(1 for r in self.action_history if not r.success),
            "tech_researched": len(state.researched_tech),
            "machines_placed": sum(state.machines.values()),
            "rocket_parts": state.inventory.get("rocket-part", 0),
        }

    def is_game_won(self) -> bool:
        """Check if game was won."""
        for r in self.action_history:
            if r.action == "launch" and r.success:
                return True
        return False


# For compatibility with existing code
def create_client(server_url: Optional[str] = None) -> GameClient:
    """Create a game client."""
    return GameClient(server_url)

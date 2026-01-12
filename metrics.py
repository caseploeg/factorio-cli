"""
Metrics collection and export for LLM evaluation.

Ensures metrics are automatically saved before container exit.
"""

import os
import json
import atexit
import signal
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class RunMetrics:
    """Comprehensive metrics for an evaluation run."""
    # Run identification
    run_id: str
    agent_type: str
    model: str
    start_time: str
    end_time: Optional[str] = None

    # Game progress
    game_won: bool = False
    total_turns: int = 0
    game_time_hours: float = 0.0

    # Action statistics
    actions_total: int = 0
    actions_successful: int = 0
    actions_failed: int = 0
    success_rate: float = 0.0

    # Breakdown by action type
    action_counts: Dict[str, int] = None

    # Game milestones
    tech_researched: int = 0
    machines_placed: int = 0
    rocket_parts: int = 0

    # Bash usage (if enabled)
    bash_commands_run: int = 0
    bash_commands_blocked: int = 0

    # Resource efficiency
    total_items_crafted: int = 0
    unique_recipes_used: int = 0

    # Errors and issues
    consecutive_failures_max: int = 0
    error_messages: List[str] = None

    def __post_init__(self):
        if self.action_counts is None:
            self.action_counts = {}
        if self.error_messages is None:
            self.error_messages = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MetricsCollector:
    """
    Automatic metrics collection with guaranteed persistence.

    Features:
    - Automatic save on exit (normal or crash)
    - Periodic checkpoints during run
    - Signal handlers for graceful shutdown
    - JSON export for easy analysis
    """

    def __init__(self, output_dir: str = "results", run_id: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.metrics = RunMetrics(
            run_id=self.run_id,
            agent_type="unknown",
            model="unknown",
            start_time=datetime.now().isoformat(),
        )

        self.turn_history: List[Dict] = []
        self._setup_auto_save()

    def _setup_auto_save(self):
        """Register handlers to save metrics on exit."""
        # Save on normal exit
        atexit.register(self.save_final)

        # Save on signals (SIGTERM, SIGINT)
        for sig in [signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\nReceived signal {signum}, saving metrics...")
        self.save_final()
        exit(0)

    def set_agent_info(self, agent_type: str, model: str = ""):
        """Set agent identification."""
        self.metrics.agent_type = agent_type
        self.metrics.model = model

    def record_turn(self, turn: int, action: str, success: bool, message: str,
                    game_time: float, blocked: bool = False):
        """Record a single turn."""
        self.metrics.total_turns = turn
        self.metrics.game_time_hours = game_time / 3600
        self.metrics.actions_total += 1

        if success:
            self.metrics.actions_successful += 1
        else:
            self.metrics.actions_failed += 1

        # Track action types
        action_type = action.split()[0] if action else "unknown"
        self.metrics.action_counts[action_type] = \
            self.metrics.action_counts.get(action_type, 0) + 1

        # Track bash usage
        if action_type == "bash":
            if blocked:
                self.metrics.bash_commands_blocked += 1
            else:
                self.metrics.bash_commands_run += 1

        # Store turn history
        self.turn_history.append({
            "turn": turn,
            "action": action,
            "success": success,
            "message": message[:200],  # Truncate long messages
            "game_time": game_time,
        })

        # Update success rate
        self.metrics.success_rate = \
            self.metrics.actions_successful / max(1, self.metrics.actions_total)

    def record_game_state(self, tech_count: int, machines: int, rocket_parts: int,
                         unique_items: int):
        """Record game progress."""
        self.metrics.tech_researched = tech_count
        self.metrics.machines_placed = machines
        self.metrics.rocket_parts = rocket_parts
        self.metrics.unique_recipes_used = unique_items

    def record_win(self):
        """Record game won."""
        self.metrics.game_won = True

    def record_error(self, message: str):
        """Record an error message."""
        if len(self.metrics.error_messages) < 100:  # Cap errors stored
            self.metrics.error_messages.append(message)

    def save_checkpoint(self, suffix: str = ""):
        """Save intermediate checkpoint."""
        filename = f"metrics_{self.run_id}"
        if suffix:
            filename += f"_{suffix}"
        filename += ".json"

        self._save_to_file(self.output_dir / filename)

    def save_final(self):
        """Save final metrics (called automatically on exit)."""
        self.metrics.end_time = datetime.now().isoformat()

        # Save summary metrics
        summary_file = self.output_dir / f"metrics_{self.run_id}_final.json"
        self._save_to_file(summary_file)

        # Save detailed turn history
        history_file = self.output_dir / f"history_{self.run_id}.jsonl"
        with open(history_file, 'w') as f:
            for turn in self.turn_history:
                f.write(json.dumps(turn) + '\n')

        print(f"Metrics saved to: {summary_file}")

    def _save_to_file(self, path: Path):
        """Write metrics to file."""
        with open(path, 'w') as f:
            json.dump(self.metrics.to_dict(), f, indent=2)

    def get_summary(self) -> str:
        """Get human-readable summary."""
        m = self.metrics
        lines = [
            "=" * 50,
            "EVALUATION METRICS",
            "=" * 50,
            f"Run ID: {m.run_id}",
            f"Agent: {m.agent_type} ({m.model})",
            f"Duration: {m.start_time} to {m.end_time or 'ongoing'}",
            "",
            "RESULTS:",
            f"  Game Won: {m.game_won}",
            f"  Total Turns: {m.total_turns}",
            f"  Game Time: {m.game_time_hours:.2f} hours",
            f"  Success Rate: {m.success_rate:.1%}",
            "",
            "PROGRESS:",
            f"  Tech Researched: {m.tech_researched}",
            f"  Machines Placed: {m.machines_placed}",
            f"  Rocket Parts: {m.rocket_parts}",
            "",
            "ACTIONS:",
        ]
        for action, count in sorted(m.action_counts.items()):
            lines.append(f"  {action}: {count}")

        if m.bash_commands_run > 0 or m.bash_commands_blocked > 0:
            lines.extend([
                "",
                "BASH USAGE:",
                f"  Commands Run: {m.bash_commands_run}",
                f"  Commands Blocked: {m.bash_commands_blocked}",
            ])

        return "\n".join(lines)


def create_collector(output_dir: str = "/app/results") -> MetricsCollector:
    """Create metrics collector with Docker-friendly defaults."""
    # Use /app/results in Docker, ./results locally
    if not os.path.exists("/app"):
        output_dir = "results"
    return MetricsCollector(output_dir=output_dir)


# Example integration
if __name__ == "__main__":
    print("Testing MetricsCollector...")

    collector = create_collector("test_results")
    collector.set_agent_info("CohereAgent", "command-r-plus")

    # Simulate some turns
    for i in range(10):
        success = i % 3 != 0  # Some failures
        collector.record_turn(
            turn=i + 1,
            action=f"mine iron-ore {i * 10}",
            success=success,
            message="OK" if success else "Failed",
            game_time=i * 60,
        )

    collector.record_game_state(
        tech_count=3,
        machines=5,
        rocket_parts=0,
        unique_items=12,
    )

    print(collector.get_summary())
    collector.save_final()

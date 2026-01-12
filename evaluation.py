"""
Evaluation Testbed for LLM Factorio Agents

Provides:
- Long-running evaluation with checkpointing
- Metrics collection and logging
- Multiple agent comparison
- Configurable stopping conditions
"""

import os
import json
import time
import logging
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path

from llm_harness import FactorioHarness, GameObservation, ActionResult, create_harness
from llm_agent import BaseAgent, AgentConfig, CohereAgent, RandomAgent, ScriptedAgent
from metrics import MetricsCollector, create_collector


@dataclass
class EvalConfig:
    """Configuration for evaluation runs."""
    # Run settings
    max_turns: int = 1000  # Maximum turns per episode
    max_game_time: float = 86400.0  # Max game time in seconds (24 hours)
    num_episodes: int = 1  # Number of episodes to run

    # Checkpointing
    checkpoint_dir: str = "checkpoints"
    checkpoint_interval: int = 50  # Save checkpoint every N turns
    save_full_history: bool = True

    # Logging
    log_dir: str = "logs"
    log_level: str = "INFO"
    verbose: bool = True

    # Stopping conditions
    stop_on_win: bool = True
    stop_on_consecutive_failures: int = 20  # Stop after N consecutive failures

    # Delays (for rate limiting)
    turn_delay: float = 0.0  # Delay between turns (seconds)


@dataclass
class EpisodeMetrics:
    """Metrics collected during an episode."""
    episode_id: int
    agent_name: str
    start_time: str
    end_time: Optional[str] = None
    total_turns: int = 0
    game_time_seconds: float = 0.0
    game_won: bool = False

    # Action statistics
    actions_total: int = 0
    actions_successful: int = 0
    actions_failed: int = 0
    action_type_counts: Dict[str, int] = field(default_factory=dict)

    # Progress metrics
    tech_researched: int = 0
    machines_placed: int = 0
    unique_items: int = 0
    rocket_parts: int = 0

    # Efficiency metrics
    success_rate: float = 0.0
    turns_per_hour_gametime: float = 0.0

    # Stopping reason
    stop_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TurnLog:
    """Log entry for a single turn."""
    turn: int
    action: str
    success: bool
    message: str
    game_time: float
    timestamp: str


class EvaluationRunner:
    """
    Long-running evaluation testbed for LLM agents.

    Supports:
    - Checkpointing for resumption
    - Detailed metrics and logging
    - Multiple stopping conditions
    - Progress callbacks
    """

    def __init__(self, config: EvalConfig):
        self.config = config
        self.harness: Optional[FactorioHarness] = None
        self.agent: Optional[BaseAgent] = None
        self.current_episode: Optional[EpisodeMetrics] = None
        self.turn_logs: List[TurnLog] = []

        # Setup directories
        Path(config.checkpoint_dir).mkdir(parents=True, exist_ok=True)
        Path(config.log_dir).mkdir(parents=True, exist_ok=True)

        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging."""
        log_file = Path(self.config.log_dir) / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler() if self.config.verbose else logging.NullHandler(),
            ]
        )
        self.logger = logging.getLogger(__name__)

    def run_episode(
        self,
        agent: BaseAgent,
        episode_id: int = 0,
        progress_callback: Optional[Callable[[int, EpisodeMetrics], None]] = None,
    ) -> EpisodeMetrics:
        """
        Run a single evaluation episode.

        Args:
            agent: The agent to evaluate
            episode_id: Identifier for this episode
            progress_callback: Optional callback called after each turn

        Returns:
            EpisodeMetrics with results
        """
        self.agent = agent
        self.harness = create_harness()
        self.turn_logs = []

        # Initialize metrics
        self.current_episode = EpisodeMetrics(
            episode_id=episode_id,
            agent_name=agent.__class__.__name__,
            start_time=datetime.now().isoformat(),
        )

        self.logger.info(f"Starting episode {episode_id} with agent {agent.__class__.__name__}")

        # Reset game and agent
        obs = self.harness.reset()
        agent.reset()

        last_result: Optional[ActionResult] = None
        consecutive_failures = 0

        for turn in range(1, self.config.max_turns + 1):
            # Check stopping conditions
            stop_reason = self._check_stop_conditions(consecutive_failures)
            if stop_reason:
                self.current_episode.stop_reason = stop_reason
                self.logger.info(f"Stopping: {stop_reason}")
                break

            # Get action from agent
            try:
                action = agent.get_action(obs, last_result)
            except Exception as e:
                self.logger.error(f"Agent error on turn {turn}: {e}")
                consecutive_failures += 1
                continue

            # Execute action
            result = self.harness.execute_action(action)
            last_result = result

            # Update metrics
            self._update_metrics(turn, action, result)

            # Log turn
            turn_log = TurnLog(
                turn=turn,
                action=action,
                success=result.success,
                message=result.message,
                game_time=self.harness.sim.game_time,
                timestamp=datetime.now().isoformat(),
            )
            self.turn_logs.append(turn_log)

            if self.config.verbose and turn % 10 == 0:
                self.logger.info(
                    f"Turn {turn}: {action} -> {'OK' if result.success else 'FAIL'} "
                    f"(game time: {self.harness.sim.game_time/60:.1f}min)"
                )

            # Track consecutive failures
            if result.success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1

            # Get new observation
            obs = self.harness.get_observation()

            # Checkpoint
            if turn % self.config.checkpoint_interval == 0:
                self._save_checkpoint(episode_id, turn)

            # Progress callback
            if progress_callback:
                progress_callback(turn, self.current_episode)

            # Turn delay
            if self.config.turn_delay > 0:
                time.sleep(self.config.turn_delay)

        # Finalize metrics
        self._finalize_metrics()

        # Save final state
        self._save_checkpoint(episode_id, self.current_episode.total_turns, final=True)
        self._save_episode_log(episode_id)

        self.logger.info(
            f"Episode {episode_id} complete: {self.current_episode.total_turns} turns, "
            f"won={self.current_episode.game_won}, "
            f"success_rate={self.current_episode.success_rate:.2%}"
        )

        return self.current_episode

    def _check_stop_conditions(self, consecutive_failures: int) -> Optional[str]:
        """Check if any stopping condition is met."""
        if self.harness.is_game_won() and self.config.stop_on_win:
            return "Game won (rocket launched)"

        if self.harness.sim.game_time >= self.config.max_game_time:
            return f"Max game time reached ({self.config.max_game_time}s)"

        if consecutive_failures >= self.config.stop_on_consecutive_failures:
            return f"Too many consecutive failures ({consecutive_failures})"

        return None

    def _update_metrics(self, turn: int, action: str, result: ActionResult):
        """Update episode metrics after a turn."""
        m = self.current_episode
        m.total_turns = turn
        m.game_time_seconds = self.harness.sim.game_time
        m.actions_total += 1

        if result.success:
            m.actions_successful += 1
        else:
            m.actions_failed += 1

        # Track action types
        action_type = action.split()[0] if action else "unknown"
        m.action_type_counts[action_type] = m.action_type_counts.get(action_type, 0) + 1

    def _finalize_metrics(self):
        """Calculate final metrics at end of episode."""
        m = self.current_episode
        m.end_time = datetime.now().isoformat()

        # Get harness metrics
        harness_metrics = self.harness.get_metrics()
        m.game_won = harness_metrics["game_won"]
        m.tech_researched = harness_metrics["tech_researched"]
        m.machines_placed = harness_metrics["machines_placed"]
        m.unique_items = harness_metrics["unique_items_crafted"]
        m.rocket_parts = harness_metrics["rocket_parts"]

        # Calculate efficiency
        m.success_rate = m.actions_successful / max(1, m.actions_total)
        if m.game_time_seconds > 0:
            m.turns_per_hour_gametime = m.total_turns / (m.game_time_seconds / 3600)

    def _save_checkpoint(self, episode_id: int, turn: int, final: bool = False):
        """Save checkpoint for resumption."""
        suffix = "final" if final else f"turn_{turn}"
        checkpoint_path = Path(self.config.checkpoint_dir) / f"episode_{episode_id}_{suffix}.json"

        checkpoint_data = {
            "episode_id": episode_id,
            "turn": turn,
            "metrics": self.current_episode.to_dict(),
            "harness_state": self.harness.save_state(),
            "timestamp": datetime.now().isoformat(),
        }

        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)

        self.logger.debug(f"Saved checkpoint: {checkpoint_path}")

    def _save_episode_log(self, episode_id: int):
        """Save detailed turn log for episode."""
        if not self.config.save_full_history:
            return

        log_path = Path(self.config.log_dir) / f"episode_{episode_id}_turns.jsonl"

        with open(log_path, 'w') as f:
            for turn_log in self.turn_logs:
                f.write(json.dumps(asdict(turn_log)) + '\n')

        self.logger.info(f"Saved turn log: {log_path}")

    def run_evaluation(
        self,
        agent: BaseAgent,
        progress_callback: Optional[Callable[[int, int, EpisodeMetrics], None]] = None,
    ) -> List[EpisodeMetrics]:
        """
        Run full evaluation with multiple episodes.

        Args:
            agent: Agent to evaluate
            progress_callback: Called with (episode_id, turn, metrics)

        Returns:
            List of EpisodeMetrics for all episodes
        """
        all_metrics = []

        for ep_id in range(self.config.num_episodes):
            self.logger.info(f"=== Episode {ep_id + 1}/{self.config.num_episodes} ===")

            def ep_callback(turn, metrics):
                if progress_callback:
                    progress_callback(ep_id, turn, metrics)

            metrics = self.run_episode(agent, episode_id=ep_id, progress_callback=ep_callback)
            all_metrics.append(metrics)

        # Save summary
        self._save_evaluation_summary(all_metrics)

        return all_metrics

    def _save_evaluation_summary(self, all_metrics: List[EpisodeMetrics]):
        """Save summary of all episodes."""
        summary_path = Path(self.config.log_dir) / "evaluation_summary.json"

        summary = {
            "config": asdict(self.config),
            "episodes": [m.to_dict() for m in all_metrics],
            "aggregate": {
                "total_episodes": len(all_metrics),
                "wins": sum(1 for m in all_metrics if m.game_won),
                "avg_turns": sum(m.total_turns for m in all_metrics) / len(all_metrics),
                "avg_success_rate": sum(m.success_rate for m in all_metrics) / len(all_metrics),
            },
            "timestamp": datetime.now().isoformat(),
        }

        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        self.logger.info(f"Saved evaluation summary: {summary_path}")

    def resume_from_checkpoint(self, checkpoint_path: str) -> Optional[EpisodeMetrics]:
        """Resume evaluation from a checkpoint."""
        with open(checkpoint_path) as f:
            checkpoint = json.load(f)

        self.harness = create_harness()
        self.harness.load_state(checkpoint["harness_state"])

        self.current_episode = EpisodeMetrics(**checkpoint["metrics"])
        self.logger.info(f"Resumed from checkpoint: turn {checkpoint['turn']}")

        return self.current_episode


def run_quick_eval(
    agent: BaseAgent,
    max_turns: int = 100,
    verbose: bool = True,
) -> EpisodeMetrics:
    """Convenience function for quick evaluation runs."""
    config = EvalConfig(
        max_turns=max_turns,
        verbose=verbose,
        checkpoint_interval=max_turns + 1,  # Don't checkpoint
        save_full_history=False,
    )
    runner = EvaluationRunner(config)
    return runner.run_episode(agent, episode_id=0)


def compare_agents(
    agents: Dict[str, BaseAgent],
    max_turns: int = 500,
    num_episodes: int = 3,
) -> Dict[str, List[EpisodeMetrics]]:
    """Compare multiple agents."""
    results = {}

    for name, agent in agents.items():
        print(f"\n{'='*50}")
        print(f"Evaluating: {name}")
        print('='*50)

        config = EvalConfig(
            max_turns=max_turns,
            num_episodes=num_episodes,
            log_dir=f"logs/{name}",
            checkpoint_dir=f"checkpoints/{name}",
        )
        runner = EvaluationRunner(config)
        results[name] = runner.run_evaluation(agent)

    # Print comparison
    print("\n" + "="*60)
    print("COMPARISON RESULTS")
    print("="*60)
    for name, metrics in results.items():
        avg_success = sum(m.success_rate for m in metrics) / len(metrics)
        avg_turns = sum(m.total_turns for m in metrics) / len(metrics)
        wins = sum(1 for m in metrics if m.game_won)
        print(f"{name}:")
        print(f"  Wins: {wins}/{len(metrics)}")
        print(f"  Avg Success Rate: {avg_success:.2%}")
        print(f"  Avg Turns: {avg_turns:.0f}")

    return results


if __name__ == "__main__":
    # Demo evaluation with random agent
    print("Running evaluation demo with RandomAgent...")

    from llm_agent import create_random_agent

    agent = create_random_agent()
    metrics = run_quick_eval(agent, max_turns=50, verbose=True)

    print("\n" + "="*40)
    print("FINAL METRICS")
    print("="*40)
    for key, value in metrics.to_dict().items():
        if not isinstance(value, dict):
            print(f"  {key}: {value}")
        else:
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")

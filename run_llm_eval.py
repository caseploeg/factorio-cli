#!/usr/bin/env python3
"""
Main entry point for running LLM evaluations on Factorio simulation.

Usage:
    # Run with Cohere agent (requires COHERE_API_KEY env var)
    python run_llm_eval.py --agent cohere --max-turns 500

    # Run with random baseline agent
    python run_llm_eval.py --agent random --max-turns 100

    # Run comparison between agents
    python run_llm_eval.py --compare --max-turns 200 --episodes 3

    # Run with custom Cohere model
    python run_llm_eval.py --agent cohere --model command-r --temperature 0.5

    # Resume from checkpoint
    python run_llm_eval.py --resume checkpoints/episode_0_turn_100.json
"""

import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Run LLM evaluation on Factorio simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--agent",
        choices=["cohere", "random", "scripted"],
        default="random",
        help="Agent type to use (default: random)",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=200,
        help="Maximum turns per episode (default: 200)",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=1,
        help="Number of episodes to run (default: 1)",
    )
    parser.add_argument(
        "--model",
        default="command-r-plus",
        help="Cohere model to use (default: command-r-plus)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="LLM temperature (default: 0.3)",
    )
    parser.add_argument(
        "--api-key",
        help="Cohere API key (or set COHERE_API_KEY env var)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run comparison between Cohere and random agents",
    )
    parser.add_argument(
        "--resume",
        help="Path to checkpoint file to resume from",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=50,
        help="Save checkpoint every N turns (default: 50)",
    )
    parser.add_argument(
        "--output-dir",
        default="eval_output",
        help="Directory for logs and checkpoints (default: eval_output)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Verbose output",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output",
    )
    parser.add_argument(
        "--turn-delay",
        type=float,
        default=0.0,
        help="Delay between turns in seconds (for rate limiting)",
    )

    args = parser.parse_args()

    # Import here to avoid slow startup for --help
    from llm_agent import AgentConfig, CohereAgent, RandomAgent, ScriptedAgent, create_cohere_agent
    from evaluation import EvalConfig, EvaluationRunner, run_quick_eval, compare_agents

    # Setup output directories
    output_dir = Path(args.output_dir)
    log_dir = output_dir / "logs"
    checkpoint_dir = output_dir / "checkpoints"

    # Create config
    config = EvalConfig(
        max_turns=args.max_turns,
        num_episodes=args.episodes,
        checkpoint_dir=str(checkpoint_dir),
        checkpoint_interval=args.checkpoint_interval,
        log_dir=str(log_dir),
        verbose=not args.quiet,
        turn_delay=args.turn_delay,
    )

    if args.compare:
        # Run comparison
        print("Running agent comparison...")
        agents = {"random": RandomAgent(AgentConfig())}

        # Try to add Cohere agent
        api_key = args.api_key or os.environ.get("COHERE_API_KEY")
        if api_key:
            try:
                agents["cohere"] = create_cohere_agent(
                    api_key=api_key,
                    model=args.model,
                    temperature=args.temperature,
                )
            except Exception as e:
                print(f"Warning: Could not create Cohere agent: {e}")
        else:
            print("Note: Set COHERE_API_KEY to include Cohere in comparison")

        compare_agents(agents, max_turns=args.max_turns, num_episodes=args.episodes)
        return

    # Create agent
    if args.agent == "cohere":
        api_key = args.api_key or os.environ.get("COHERE_API_KEY")
        if not api_key:
            print("Error: Cohere agent requires API key.")
            print("Set COHERE_API_KEY environment variable or use --api-key")
            sys.exit(1)

        try:
            agent = create_cohere_agent(
                api_key=api_key,
                model=args.model,
                temperature=args.temperature,
            )
        except ImportError:
            print("Error: cohere package not installed. Run: pip install cohere")
            sys.exit(1)

        print(f"Using Cohere agent with model: {args.model}")

    elif args.agent == "random":
        agent = RandomAgent(AgentConfig())
        print("Using random baseline agent")

    elif args.agent == "scripted":
        # Load a basic script
        script = [
            "mine iron-ore 50",
            "mine stone 30",
            "mine copper-ore 30",
            "craft stone-furnace 2",
            "craft burner-mining-drill 2",
            "place burner-mining-drill iron-ore",
            "place stone-furnace iron-plate",
            "next 5",
        ]
        agent = ScriptedAgent(AgentConfig(), script)
        print("Using scripted agent")

    # Resume from checkpoint if specified
    if args.resume:
        print(f"Resuming from checkpoint: {args.resume}")
        runner = EvaluationRunner(config)
        runner.resume_from_checkpoint(args.resume)
        # Continue running...
        # Note: This is a simplified resume - full implementation would
        # restore agent state as well
        print("Note: Agent state not restored - starting with fresh agent from checkpoint game state")

    # Run evaluation
    print(f"\nStarting evaluation: {args.episodes} episode(s), max {args.max_turns} turns each")
    print(f"Output directory: {output_dir}")
    print("-" * 50)

    runner = EvaluationRunner(config)

    def progress_callback(episode, turn, metrics):
        if turn % 25 == 0:
            print(f"  Episode {episode}, Turn {turn}: "
                  f"success_rate={metrics.success_rate:.1%}, "
                  f"game_time={metrics.game_time_seconds/60:.1f}min")

    all_metrics = runner.run_evaluation(agent, progress_callback=progress_callback)

    # Print final summary
    print("\n" + "=" * 50)
    print("EVALUATION COMPLETE")
    print("=" * 50)

    for i, metrics in enumerate(all_metrics):
        print(f"\nEpisode {i}:")
        print(f"  Turns: {metrics.total_turns}")
        print(f"  Game Time: {metrics.game_time_seconds/3600:.2f} hours")
        print(f"  Success Rate: {metrics.success_rate:.1%}")
        print(f"  Tech Researched: {metrics.tech_researched}")
        print(f"  Machines Placed: {metrics.machines_placed}")
        print(f"  Game Won: {metrics.game_won}")
        print(f"  Stop Reason: {metrics.stop_reason}")

    if len(all_metrics) > 1:
        print("\nAggregate:")
        print(f"  Total Episodes: {len(all_metrics)}")
        print(f"  Wins: {sum(1 for m in all_metrics if m.game_won)}/{len(all_metrics)}")
        avg_success = sum(m.success_rate for m in all_metrics) / len(all_metrics)
        print(f"  Avg Success Rate: {avg_success:.1%}")

    print(f"\nResults saved to: {output_dir}")


if __name__ == "__main__":
    main()

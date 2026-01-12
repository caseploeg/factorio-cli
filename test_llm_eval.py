#!/usr/bin/env python3
"""
Test LLM evaluation locally with various providers.

Supports:
- Groq (free tier) - GROQ_API_KEY
- Cohere (free trial) - COHERE_API_KEY
- Random (no API needed)

Usage:
  # Start server first:
  python minimal_server.py &

  # Then run:
  python test_llm_eval.py --agent random --turns 20
  GROQ_API_KEY=xxx python test_llm_eval.py --agent groq --turns 50
"""

import os
import re
import sys
import time
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict
from abc import ABC, abstractmethod

from agent_client import GameClient, GameState, ActionResult


@dataclass
class AgentConfig:
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 256
    max_retries: int = 3


SYSTEM_PROMPT = """You are playing Factorio, a factory automation game.

GOAL: Launch a rocket. You need 100 rocket-parts.

COMMANDS:
- mine <resource> <amount>: Mine iron-ore, copper-ore, stone, coal
- craft <item> [amount]: Craft items (need ingredients)
- place <machine> <item>: Automate production
- research <technology>: Unlock recipes (needs science packs)
- next [minutes]: Advance time
- info <item>: Get recipe info
- recipes: List available recipes
- launch: Win!

ERROR MESSAGES tell you what you're missing.
Use 'info <item>' to learn recipes.

Respond with EXACTLY ONE command."""


class BaseAgent(ABC):
    def __init__(self, config: AgentConfig):
        self.config = config
        self.history: List[Dict] = []

    @abstractmethod
    def get_action(self, state: GameState, last_result: Optional[ActionResult] = None) -> str:
        pass

    def reset(self):
        self.history = []


class RandomAgent(BaseAgent):
    def get_action(self, state: GameState, last_result: Optional[ActionResult] = None) -> str:
        import random
        actions = [
            f"mine iron-ore {random.randint(20, 50)}",
            f"mine copper-ore {random.randint(20, 50)}",
            f"mine stone {random.randint(10, 30)}",
            f"mine coal {random.randint(10, 30)}",
            "next",
            "next 5",
            "recipes",
        ]
        if state.available_recipes:
            for r in random.sample(state.available_recipes, min(3, len(state.available_recipes))):
                actions.append(f"craft {r}")
        return random.choice(actions)


class GroqAgent(BaseAgent):
    """Agent using Groq's free API (llama, mixtral, etc.)"""

    def __init__(self, config: AgentConfig, api_key: Optional[str] = None):
        super().__init__(config)
        try:
            from groq import Groq
        except ImportError:
            raise ImportError("groq not installed. Run: pip install groq")

        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY required")

        self.client = Groq(api_key=self.api_key)
        self.model = config.model or "llama-3.1-8b-instant"  # Fast, free

    def get_action(self, state: GameState, last_result: Optional[ActionResult] = None) -> str:
        parts = []
        if last_result:
            status = "OK" if last_result.success else "FAILED"
            parts.append(f"Last: {last_result.action} -> {status}: {last_result.message[:100]}")
            parts.append("")

        parts.append(state.to_prompt_string())
        parts.append("")
        parts.append("Your action:")

        user_msg = "\n".join(parts)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        for h in self.history[-6:]:  # Keep history short
            messages.append(h)
        messages.append({"role": "user", "content": user_msg})

        for attempt in range(self.config.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                text = response.choices[0].message.content
                action = self._extract_action(text)

                self.history.append({"role": "user", "content": user_msg})
                self.history.append({"role": "assistant", "content": text})

                return action

            except Exception as e:
                print(f"  API error (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))
                else:
                    return "next"  # Fallback

    def _extract_action(self, text: str) -> str:
        text = text.strip()
        patterns = [
            r"^(mine\s+\S+\s+\d+)",
            r"^(craft\s+\S+(?:\s+\d+)?)",
            r"^(place\s+\S+\s+\S+(?:\s+\d+)?)",
            r"^(research\s+\S+)",
            r"^(next(?:\s+\d+)?)",
            r"^(limit\s+\S+\s+\d+)",
            r"^(launch)",
            r"^(info\s+\S+)",
            r"^(recipes)",
        ]

        for pattern in patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).lower()

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            for pattern in patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    return match.group(1).lower()

        # Fallback
        return "next"


class CohereAgent(BaseAgent):
    """Agent using Cohere API"""

    def __init__(self, config: AgentConfig, api_key: Optional[str] = None):
        super().__init__(config)
        try:
            import cohere
        except ImportError:
            raise ImportError("cohere not installed. Run: pip install cohere")

        self.api_key = api_key or os.environ.get("COHERE_API_KEY")
        if not self.api_key:
            raise ValueError("COHERE_API_KEY required")

        self.client = cohere.ClientV2(api_key=self.api_key)
        self.model = config.model or "command-r"

    def get_action(self, state: GameState, last_result: Optional[ActionResult] = None) -> str:
        parts = []
        if last_result:
            status = "OK" if last_result.success else "FAILED"
            parts.append(f"Last: {last_result.action} -> {status}: {last_result.message[:100]}")
            parts.append("")

        parts.append(state.to_prompt_string())
        parts.append("")
        parts.append("Your action:")

        user_msg = "\n".join(parts)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        for h in self.history[-6:]:
            messages.append(h)
        messages.append({"role": "user", "content": user_msg})

        for attempt in range(self.config.max_retries):
            try:
                response = self.client.chat(
                    model=self.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                text = response.message.content[0].text
                action = self._extract_action(text)

                self.history.append({"role": "user", "content": user_msg})
                self.history.append({"role": "assistant", "content": text})

                return action

            except Exception as e:
                print(f"  API error (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))
                else:
                    return "next"

    def _extract_action(self, text: str) -> str:
        # Same as GroqAgent
        text = text.strip()
        patterns = [
            r"^(mine\s+\S+\s+\d+)",
            r"^(craft\s+\S+(?:\s+\d+)?)",
            r"^(place\s+\S+\s+\S+(?:\s+\d+)?)",
            r"^(research\s+\S+)",
            r"^(next(?:\s+\d+)?)",
            r"^(limit\s+\S+\s+\d+)",
            r"^(launch)",
            r"^(info\s+\S+)",
            r"^(recipes)",
        ]

        for pattern in patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).lower()

        for line in text.split("\n"):
            line = line.strip()
            for pattern in patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    return match.group(1).lower()

        return "next"


def run_evaluation(agent: BaseAgent, client: GameClient, max_turns: int, verbose: bool = True):
    """Run evaluation loop."""
    state = client.reset()
    agent.reset()
    last_result = None

    print(f"Starting evaluation: {agent.__class__.__name__}")
    print(f"Max turns: {max_turns}")
    print("-" * 50)

    for turn in range(1, max_turns + 1):
        # Get action
        try:
            action = agent.get_action(state, last_result)
        except Exception as e:
            print(f"Agent error: {e}")
            action = "next"

        # Execute
        result = client.execute_action(action)
        last_result = result

        # Log
        status = "OK" if result.success else "FAIL"
        if verbose or turn % 10 == 0:
            msg = result.message[:50].replace("\n", " ")
            print(f"T{turn:3d}: [{status}] {action:30s} -> {msg}")

        # Check win
        if client.is_game_won():
            print("\n*** GAME WON! ***")
            break

        # Update state
        state = client.get_state()

    # Final report
    metrics = client.get_metrics()
    print()
    print("=" * 50)
    print("FINAL RESULTS")
    print("=" * 50)
    print(f"Turns: {metrics['turn_count']}")
    print(f"Game time: {metrics['game_time_seconds']/3600:.2f} hours")
    print(f"Success rate: {metrics['actions_successful']}/{metrics['actions_successful'] + metrics['actions_failed']}")
    print(f"Tech researched: {metrics['tech_researched']}")
    print(f"Machines placed: {metrics['machines_placed']}")
    print(f"Rocket parts: {metrics['rocket_parts']}")
    print()
    print("Final inventory (non-zero):")
    for item, count in sorted(state.inventory.items()):
        if count > 0:
            print(f"  {item}: {count}")

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Test LLM evaluation")
    parser.add_argument("--agent", choices=["random", "groq", "cohere"], default="random")
    parser.add_argument("--turns", type=int, default=50)
    parser.add_argument("--server", default="http://127.0.0.1:5050")
    parser.add_argument("--model", default="")
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    # Create client
    client = GameClient(args.server)

    # Test connection
    try:
        client.get_state()
    except Exception as e:
        print(f"Cannot connect to server at {args.server}")
        print(f"Start it with: python minimal_server.py &")
        print(f"Error: {e}")
        sys.exit(1)

    # Create agent
    config = AgentConfig(model=args.model, temperature=args.temperature)

    if args.agent == "random":
        agent = RandomAgent(config)
    elif args.agent == "groq":
        agent = GroqAgent(config)
    elif args.agent == "cohere":
        agent = CohereAgent(config)

    # Run
    run_evaluation(agent, client, args.turns, verbose=not args.quiet)


if __name__ == "__main__":
    main()

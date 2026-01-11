"""
LLM Agent for Factorio Simulation using Cohere API

Implements an agent that uses Cohere's command model to play Factorio.
"""

import os
import re
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

try:
    import cohere
    COHERE_AVAILABLE = True
except ImportError:
    COHERE_AVAILABLE = False
    cohere = None

from llm_harness import FactorioHarness, GameObservation, ActionResult


@dataclass
class AgentConfig:
    """Configuration for the LLM agent."""
    model: str = "command-r-plus"  # Cohere model to use
    temperature: float = 0.3  # Lower = more deterministic
    max_tokens: int = 256
    system_prompt: Optional[str] = None
    max_retries: int = 3  # Retries on API failures
    retry_delay: float = 1.0  # Seconds between retries


DEFAULT_SYSTEM_PROMPT = """You are playing Factorio, a factory-building game. Your goal is to launch a rocket.

STRATEGY TIPS:
1. Early game: Mine resources manually (iron-ore, copper-ore, stone, coal)
2. Craft basic machines: stone-furnace, burner-mining-drill
3. Place machines to automate: burner-mining-drill mines ore, stone-furnace smelts to plates
4. Research automation for assembling-machine-1 which can autocraft items
5. Build up science pack production to research more technology
6. Eventually produce rocket-parts and launch!

IMPORTANT:
- Each turn, respond with EXACTLY ONE action
- Use the exact syntax shown (e.g., "mine iron-ore 50" not "mine 50 iron ore")
- Check your inventory before crafting - you need the ingredients
- Place machines to automate production, then use "next" to let time pass
- Research unlocks new recipes

Think step by step about what you need and respond with your action."""


class BaseAgent(ABC):
    """Abstract base class for Factorio agents."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.conversation_history: List[Dict[str, str]] = []

    @abstractmethod
    def get_action(self, observation: GameObservation, last_result: Optional[ActionResult] = None) -> str:
        """Get next action from the agent given current observation."""
        pass

    def reset(self):
        """Reset agent state for a new game."""
        self.conversation_history = []


class CohereAgent(BaseAgent):
    """Agent that uses Cohere API for decision making."""

    def __init__(self, config: AgentConfig, api_key: Optional[str] = None):
        super().__init__(config)

        if not COHERE_AVAILABLE:
            raise ImportError("cohere package not installed. Run: pip install cohere")

        self.api_key = api_key or os.environ.get("COHERE_API_KEY")
        if not self.api_key:
            raise ValueError("COHERE_API_KEY not set. Pass api_key or set environment variable.")

        self.client = cohere.ClientV2(api_key=self.api_key)
        self.system_prompt = config.system_prompt or DEFAULT_SYSTEM_PROMPT

    def get_action(self, observation: GameObservation, last_result: Optional[ActionResult] = None) -> str:
        """Query Cohere API for next action."""

        # Build the user message
        user_message_parts = []

        # Add last action result if available
        if last_result:
            status = "SUCCESS" if last_result.success else "FAILED"
            user_message_parts.append(f"Previous action: {last_result.action}")
            user_message_parts.append(f"Result: {status} - {last_result.message}")
            user_message_parts.append("")

        # Add current observation
        user_message_parts.append(observation.to_prompt_string())
        user_message_parts.append("")
        user_message_parts.append("What is your next action? Respond with exactly one action.")

        user_message = "\n".join(user_message_parts)

        # Build messages for Cohere
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]

        # Add conversation history (limited to avoid token limits)
        for msg in self.conversation_history[-10:]:
            messages.append(msg)

        messages.append({"role": "user", "content": user_message})

        # Call Cohere API with retries
        for attempt in range(self.config.max_retries):
            try:
                response = self.client.chat(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )

                # Extract the action from response
                assistant_message = response.message.content[0].text
                action = self._extract_action(assistant_message)

                # Store in conversation history
                self.conversation_history.append({"role": "user", "content": user_message})
                self.conversation_history.append({"role": "assistant", "content": assistant_message})

                return action

            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise RuntimeError(f"Cohere API failed after {self.config.max_retries} attempts: {e}")

    def _extract_action(self, response: str) -> str:
        """Extract a valid action from the LLM response."""
        # Clean up the response
        response = response.strip()

        # Try to find action patterns in the response
        action_patterns = [
            r"^(mine\s+\S+\s+\d+)",
            r"^(craft\s+\S+(?:\s+\d+)?)",
            r"^(place\s+\S+\s+\S+(?:\s+\d+)?)",
            r"^(research\s+\S+)",
            r"^(next(?:\s+\d+)?)",
            r"^(limit\s+\S+\s+\d+)",
            r"^(prio\s+\S+\s+\S+\s+\d+\s+\d+)",
            r"^(launch)",
        ]

        # First, try to match from start of response
        for pattern in action_patterns:
            match = re.match(pattern, response, re.IGNORECASE)
            if match:
                return match.group(1).lower()

        # Look for action in the full response (might be prefixed with text)
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            # Skip empty lines and lines that look like explanations
            if not line or line.startswith(('I', 'Let', 'We', 'The', 'To', 'First', 'Next', '-', '*')):
                continue
            for pattern in action_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    return match.group(1).lower()

        # If all else fails, return first line as the action
        first_line = lines[0].strip().lower() if lines else "next"
        return first_line


class RandomAgent(BaseAgent):
    """Simple random agent for baseline comparison."""

    import random

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.rng = self.random.Random()

    def get_action(self, observation: GameObservation, last_result: Optional[ActionResult] = None) -> str:
        """Pick a random valid action."""
        import random

        # Simple strategy weights
        actions = []

        # Mining
        resources = ['iron-ore', 'copper-ore', 'stone', 'coal']
        for r in resources:
            actions.append(f"mine {r} {random.randint(10, 50)}")

        # Crafting from available recipes
        if observation.available_recipes:
            recipes = list(observation.available_recipes)[:20]  # Limit choices
            for recipe in random.sample(recipes, min(5, len(recipes))):
                actions.append(f"craft {recipe}")

        # Advance time
        actions.append("next")
        actions.append("next 5")

        return random.choice(actions)


class ScriptedAgent(BaseAgent):
    """Agent that follows a predefined script (for testing/baseline)."""

    def __init__(self, config: AgentConfig, script: List[str]):
        super().__init__(config)
        self.script = script
        self.script_index = 0

    def get_action(self, observation: GameObservation, last_result: Optional[ActionResult] = None) -> str:
        """Return next action from script."""
        if self.script_index >= len(self.script):
            return "next"  # Default when script exhausted

        action = self.script[self.script_index]
        self.script_index += 1
        return action

    def reset(self):
        super().reset()
        self.script_index = 0


def create_cohere_agent(
    api_key: Optional[str] = None,
    model: str = "command-r-plus",
    temperature: float = 0.3,
) -> CohereAgent:
    """Convenience function to create a Cohere agent."""
    config = AgentConfig(model=model, temperature=temperature)
    return CohereAgent(config, api_key=api_key)


def create_random_agent() -> RandomAgent:
    """Create a random baseline agent."""
    return RandomAgent(AgentConfig())


if __name__ == "__main__":
    # Quick test of the agent
    print("Testing LLM Agent...")

    # Create harness
    from llm_harness import create_harness
    harness = create_harness()
    obs = harness.reset()

    # Test with random agent (doesn't need API key)
    agent = create_random_agent()

    print("Initial observation:")
    print(obs.to_prompt_string())
    print()

    print("Random agent actions:")
    for i in range(5):
        action = agent.get_action(obs)
        print(f"  Turn {i+1}: {action}")
        result = harness.execute_action(action)
        print(f"    Result: {'OK' if result.success else 'FAIL'} - {result.message}")
        obs = harness.get_observation()

    print()
    print("Final metrics:", harness.get_metrics())

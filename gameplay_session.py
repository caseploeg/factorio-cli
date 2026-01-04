#!/usr/bin/env python3
"""
Gameplay session to set up mining + furnace setup for iron and copper
Goal: Reach 10 iron plates per minute in production
"""

import client
import json
import time
from datetime import timedelta

class GameplayLogger:
    def __init__(self):
        self.log = []

    def run_command(self, command_name, *args, **kwargs):
        """Run a command and log the result"""
        print(f"\n{'='*80}")
        print(f"COMMAND: {command_name} {args} {kwargs}")
        print(f"{'='*80}")

        # Get current game time
        game_time = client.get_game_time()
        time_str = str(timedelta(seconds=game_time))

        # Run the command
        result = None
        if command_name == "get_inventory":
            result = client.get_inventory()
            print(f"[{time_str}] INVENTORY:")
            print(json.dumps(result, indent=2))
        elif command_name == "mine":
            result = client.mine(*args)
            print(f"[{time_str}] MINE: {result}")
        elif command_name == "craft":
            result = client.craft(*args)
            print(f"[{time_str}] CRAFT: {result}")
        elif command_name == "place":
            result = client.place(*args)
            print(f"[{time_str}] PLACE: {result}")
        elif command_name == "next":
            print(f"[{time_str}] Simulating {args[0]} minutes...")
            result = client.next(*args)
            new_time = client.get_game_time()
            new_time_str = str(timedelta(seconds=new_time))
            print(f"[{new_time_str}] Simulation complete")
        elif command_name == "production":
            result = client.production()
            print(f"[{time_str}] PRODUCTION STATS:")
            print(result)
        elif command_name == "cookbook":
            result = client.cookbook()
            print(f"[{time_str}] AVAILABLE RECIPES:")
            print(result)
        elif command_name == "limit":
            result = client.limit(*args)
            print(f"[{time_str}] LIMIT: {result}")
        else:
            print(f"Unknown command: {command_name}")

        # Log the action
        self.log.append({
            'time': time_str,
            'command': command_name,
            'args': args,
            'kwargs': kwargs,
            'result': str(result) if result else None
        })

        return result

    def save_log(self, filename):
        """Save the log to a file"""
        with open(filename, 'w') as f:
            json.dump(self.log, f, indent=2)
        print(f"\nLog saved to {filename}")

def main():
    logger = GameplayLogger()

    print("="*80)
    print("FACTORIO CLI GAMEPLAY SESSION")
    print("Goal: Set up mining + furnace for iron and copper")
    print("Target: 10 iron plates per minute")
    print("="*80)

    # Check initial state
    logger.run_command("get_inventory")

    # Step 1: Mine initial resources
    print("\n### PHASE 1: Mining Initial Resources ###")
    logger.run_command("mine", "stone", 25)
    logger.run_command("mine", "coal", 15)
    logger.run_command("mine", "iron-ore", 30)
    logger.run_command("mine", "copper-ore", 20)
    logger.run_command("get_inventory")

    # Step 2: Craft basic machinery
    print("\n### PHASE 2: Crafting Basic Machinery ###")

    # Check what we can craft
    logger.run_command("cookbook")

    # Craft stone furnaces (need stone)
    logger.run_command("craft", "stone-furnace", 6)

    # Craft burner mining drills (need iron plates + stone furnace)
    # First need to make iron plates manually
    logger.run_command("craft", "iron-plate", 10)
    logger.run_command("craft", "iron-gear-wheel", 3)
    logger.run_command("craft", "burner-mining-drill", 3)

    logger.run_command("get_inventory")

    # Step 3: Place mining drills
    print("\n### PHASE 3: Placing Mining Drills ###")
    logger.run_command("place", "burner-mining-drill", "iron-ore", 2)
    logger.run_command("place", "burner-mining-drill", "copper-ore", 1)

    # Step 4: Place furnaces
    print("\n### PHASE 4: Placing Furnaces ###")
    logger.run_command("place", "stone-furnace", "iron-plate", 4)
    logger.run_command("place", "stone-furnace", "copper-plate", 2)

    # Step 5: Check production
    print("\n### PHASE 5: Initial Production Check ###")
    logger.run_command("production")

    # Step 6: Run the factory
    print("\n### PHASE 6: Running the Factory ###")
    logger.run_command("next", 1)
    logger.run_command("production")
    logger.run_command("get_inventory")

    # Step 7: Optimize to reach 10 iron plates/min
    print("\n### PHASE 7: Scaling to 10 Iron Plates/Minute ###")

    # Check current production rate
    prod_output = logger.run_command("production")

    # Mine more resources for additional machines
    logger.run_command("mine", "stone", 20)
    logger.run_command("mine", "iron-ore", 40)
    logger.run_command("mine", "coal", 20)

    # Craft more furnaces if needed
    logger.run_command("craft", "iron-plate", 20)
    logger.run_command("craft", "stone-furnace", 4)
    logger.run_command("craft", "iron-gear-wheel", 6)
    logger.run_command("craft", "burner-mining-drill", 2)

    # Place additional mining drills and furnaces
    logger.run_command("place", "burner-mining-drill", "iron-ore", 2)
    logger.run_command("place", "stone-furnace", "iron-plate", 4)

    # Run and check production
    logger.run_command("next", 2)
    logger.run_command("production")
    logger.run_command("get_inventory")

    # Step 8: Final check
    print("\n### PHASE 8: Final Production Stats ###")
    logger.run_command("next", 1)
    logger.run_command("production")
    logger.run_command("get_inventory")

    # Save the log
    logger.save_log('/home/user/factorio-cli/gameplay_log.json')

    print("\n" + "="*80)
    print("GAMEPLAY SESSION COMPLETE!")
    print("="*80)

if __name__ == "__main__":
    main()

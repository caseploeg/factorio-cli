#!/usr/bin/env python3
"""
Gameplay session v2 - Better understanding of game mechanics
Goal: Set up mining + furnace setup for iron and copper
Target: 10 iron plates per minute in production
"""

import client
import json
from datetime import timedelta

class GameplayLogger:
    def __init__(self):
        self.log = []
        self.step = 0

    def header(self, text):
        print(f"\n{'='*80}")
        print(f"{text}")
        print(f"{'='*80}")

    def run_command(self, command_name, *args):
        """Run a command and log the result"""
        self.step += 1
        game_time = client.get_game_time()
        time_str = str(timedelta(seconds=int(game_time)))

        print(f"\n[Step {self.step}] [{time_str}] {command_name} {args}")

        result = None
        try:
            if command_name == "get_inventory":
                result = client.get_inventory()
                print(json.dumps(result, indent=2))
            elif command_name == "mine":
                result = client.mine(*args)
                print(f"  → {result}")
            elif command_name == "craft":
                result = client.craft(*args)
                print(f"  → {result}")
            elif command_name == "place":
                result = client.place(*args)
                print(f"  → {result}")
            elif command_name == "next":
                result = client.next(*args)
                new_time = client.get_game_time()
                new_time_str = str(timedelta(seconds=int(new_time)))
                print(f"  → Advanced to {new_time_str}")
            elif command_name == "production":
                result = client.production()
                # Parse production data
                import ast
                try:
                    prod_data = ast.literal_eval(result)
                    print(f"  Production Report:")
                    print(f"  {'Item':<20} {'Actual/min':<12} {'Potential/min':<12} {'Inventory':<12} {'Limit'}")
                    print(f"  {'-'*75}")
                    for row in prod_data:
                        item, actual, potential, inventory, limit = row
                        print(f"  {item:<20} {actual:<12.1f} {potential:<12.1f} {inventory:<12} {limit}")
                except:
                    print(f"  → {result}")
            else:
                print(f"  Unknown command: {command_name}")

            self.log.append({
                'step': self.step,
                'time': time_str,
                'command': command_name,
                'args': args,
                'result': str(result) if result else None
            })
        except Exception as e:
            print(f"  ERROR: {e}")
            self.log.append({
                'step': self.step,
                'time': time_str,
                'command': command_name,
                'args': args,
                'error': str(e)
            })

        return result

    def save_log(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.log, f, indent=2)
        print(f"\n{'='*80}")
        print(f"Log saved to {filename}")

def main():
    logger = GameplayLogger()

    logger.header("FACTORIO CLI GAMEPLAY SESSION V2")
    print("Goal: Set up automated mining + smelting for iron and copper")
    print("Target: 10 iron plates per minute production")

    # Clear game state to start fresh
    logger.header("RESETTING GAME STATE")
    client.clear()

    logger.header("PHASE 1: Check Starting Inventory")
    logger.run_command("get_inventory")

    logger.header("PHASE 2: Mine Initial Resources")
    print("Mining stone for furnaces...")
    logger.run_command("mine", "stone", 50)

    print("Mining coal for fuel...")
    logger.run_command("mine", "coal", 30)

    print("Mining iron ore for initial crafting...")
    logger.run_command("mine", "iron-ore", 50)

    print("Mining copper ore...")
    logger.run_command("mine", "copper-ore", 30)

    logger.run_command("get_inventory")

    logger.header("PHASE 3: Smelt Initial Iron Plates")
    print("We need iron plates to craft burner mining drills")
    print("Placing a furnace to smelt iron-ore into iron-plate...")
    logger.run_command("place", "stone-furnace", "iron-plate", 1)

    print("Running factory for 1 minute to get some iron plates...")
    logger.run_command("next", 1)
    logger.run_command("get_inventory")

    logger.header("PHASE 4: Craft Burner Mining Drills")
    print("Now we should have iron plates. Let's craft mining drills.")
    print("Crafting iron gear wheels (needed for drills)...")
    logger.run_command("craft", "iron-gear-wheel", 9)

    print("Crafting stone furnaces...")
    logger.run_command("craft", "stone-furnace", 10)

    print("Crafting burner mining drills...")
    logger.run_command("craft", "burner-mining-drill", 6)

    logger.run_command("get_inventory")

    logger.header("PHASE 5: Place Mining Infrastructure")
    print("Placing burner mining drills on iron ore...")
    logger.run_command("place", "burner-mining-drill", "iron-ore", 3)

    print("Placing burner mining drills on copper ore...")
    logger.run_command("place", "burner-mining-drill", "copper-ore", 2)

    logger.header("PHASE 6: Place Smelting Infrastructure")
    print("Placing stone furnaces for iron plate production...")
    logger.run_command("place", "stone-furnace", "iron-plate", 6)

    print("Placing stone furnaces for copper plate production...")
    logger.run_command("place", "stone-furnace", "copper-plate", 3)

    logger.run_command("get_inventory")

    logger.header("PHASE 7: Run Factory and Check Production")
    print("Running factory for 1 minute to see production rates...")
    logger.run_command("next", 1)
    logger.run_command("production")
    logger.run_command("get_inventory")

    logger.header("PHASE 8: Scale to 10 Iron Plates/Minute")
    print("Checking current production...")
    prod = logger.run_command("production")

    print("\nAnalysis: We need to adjust the number of furnaces to reach 10 iron plates/min")
    print("Stone furnace produces 12 plates/min when fully supplied")
    print("For 10 plates/min, we need to either:")
    print("  1. Use production limits")
    print("  2. Adjust the number of furnaces")

    # Set a production limit
    print("\nSetting production limit to 10 iron plates per minute...")
    logger.run_command("limit", "iron-plate", 10)

    logger.header("PHASE 9: Final Production Check")
    print("Running factory for 2 more minutes...")
    logger.run_command("next", 2)
    logger.run_command("production")
    logger.run_command("get_inventory")

    # Save everything
    logger.save_log('/home/user/factorio-cli/gameplay_log_v2.json')

    logger.header("GAMEPLAY SESSION COMPLETE!")
    print("\nSummary:")
    print("- Automated iron ore mining with burner mining drills")
    print("- Automated copper ore mining with burner mining drills")
    print("- Set up stone furnaces for smelting")
    print("- Limited iron plate production to 10 per minute")

if __name__ == "__main__":
    main()

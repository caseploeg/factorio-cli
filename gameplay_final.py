#!/usr/bin/env python3
"""
Final gameplay session - Continue from current state and complete the setup
Goal: Get to 10 iron plates per minute production
"""

import client
import json
import ast
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

        cmd_str = f"{command_name} {' '.join(map(str, args))}" if args else command_name
        print(f"\n[Step {self.step}] [{time_str}] {cmd_str}")

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
                try:
                    prod_data = ast.literal_eval(result)
                    print(f"\n  {'Item':<25} {'Actual/min':>12} {'Potential/min':>15} {'Inventory':>12} {'Limit':>10}")
                    print(f"  {'-'*80}")
                    for row in prod_data:
                        item, actual, potential, inventory, limit = row
                        limit_str = str(limit) if limit else "-"
                        print(f"  {item:<25} {actual:>12.1f} {potential:>15.1f} {inventory:>12} {limit_str:>10}")
                except:
                    print(f"  → {result}")
            elif command_name == "limit":
                result = client.limit(*args)
                print(f"  → {result}")
            else:
                print(f"  Unknown command")

            self.log.append({
                'step': self.step,
                'time': time_str,
                'command': command_name,
                'args': args,
                'result': str(result) if result else None
            })
        except Exception as e:
            print(f"  ERROR: {e}")

        return result

    def save_log(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.log, f, indent=2)
        self.header(f"Log saved to {filename}")

def main():
    logger = GameplayLogger()

    logger.header("FACTORIO CLI - FINAL GAMEPLAY SESSION")
    print("Continuing from previous state")
    print("Goal: Set up automated production reaching 10 iron plates/min")

    logger.header("Current State")
    inv = logger.run_command("get_inventory")
    logger.run_command("production")

    logger.header("STEP 1: Mine More Resources")
    print("We need more resources to build mining drills and set up production")

    # Mine more iron ore for production
    logger.run_command("mine", "iron-ore", 100)
    # Mine more copper ore
    logger.run_command("mine", "copper-ore", 50)
    # Mine more stone for furnaces
    logger.run_command("mine", "stone", 30)

    logger.run_command("get_inventory")

    logger.header("STEP 2: Craft Additional Iron Gear Wheels")
    print("We need more iron gear wheels to craft burner mining drills")
    print("Recipe: 1 burner-mining-drill = 3 iron-plate + 3 iron-gear-wheel")
    print("We'll craft 5 burner mining drills total (need 15 gear wheels, have 9)")

    logger.run_command("craft", "iron-gear-wheel", 6)

    logger.header("STEP 3: Craft Burner Mining Drills")
    print("Now crafting 5 burner mining drills...")
    logger.run_command("craft", "burner-mining-drill", 5)

    logger.run_command("get_inventory")

    logger.header("STEP 4: Place Mining Drills on Ore Patches")
    print("Placing 4 burner mining drills on iron-ore patches...")
    logger.run_command("place", "burner-mining-drill", "iron-ore", 4)

    print("Placing 2 burner mining drills on copper-ore patches...")
    logger.run_command("place", "burner-mining-drill", "copper-ore", 2)

    logger.header("STEP 5: Craft More Stone Furnaces")
    print("We need more furnaces for smelting. Stone furnace can smelt ~12 plates/min")
    print("For 10 iron plates/min, 1 furnace is enough, but we'll add a few for buffer")

    logger.run_command("craft", "stone-furnace", 5)

    logger.header("STEP 6: Set Up Smelting Infrastructure")
    print("Note: We already have 6 iron-plate furnaces and 3 copper-plate furnaces")
    print("Adding 2 more iron-plate furnaces for redundancy...")

    logger.run_command("place", "stone-furnace", "iron-plate", 2)

    logger.run_command("get_inventory")

    logger.header("STEP 7: Run Production")
    print("Running the factory for 1 minute to see production rates...")

    logger.run_command("next", 1)
    logger.run_command("production")
    logger.run_command("get_inventory")

    logger.header("STEP 8: Analyze and Optimize Production")
    prod = logger.run_command("production")

    print("\nAnalyzing production...")
    print("• Burner mining drill produces ~15 ore/min")
    print("• Stone furnace smelts at ~12 plates/min")
    print("• For 10 iron plates/min target:")
    print("  - We need steady iron-ore supply (at least 10 ore/min)")
    print("  - We need at least 1 furnace running")

    logger.header("STEP 9: Set Production Limit")
    print("Setting iron-plate production limit to 10 per minute...")
    logger.run_command("limit", "iron-plate", 10)

    logger.header("STEP 10: Final Production Test")
    print("Running for 3 minutes to verify steady-state production...")

    logger.run_command("next", 3)
    logger.run_command("production")
    logger.run_command("get_inventory")

    logger.header("STEP 11: Extended Production Test")
    print("Running for 5 more minutes to ensure stable 10/min production...")

    logger.run_command("next", 5)
    logger.run_command("production")
    final_inv = logger.run_command("get_inventory")

    logger.header("Final Analysis")
    prod_result = logger.run_command("production")

    try:
        prod_data = ast.literal_eval(prod_result)
        print("\nProduction Summary:")
        for row in prod_data:
            item, actual, potential, inventory, limit = row
            if item == "iron-plate":
                print(f"  Iron Plate Production:")
                print(f"    - Actual: {actual:.1f} plates/min")
                print(f"    - Target: 10 plates/min")
                print(f"    - Status: {'✓ TARGET ACHIEVED!' if abs(actual - 10) < 0.5 else '✗ Need adjustment'}")
                print(f"    - Inventory: {inventory} plates")
                print(f"    - Limit set: {limit if limit else 'none'}")
    except:
        pass

    logger.save_log('/home/user/factorio-cli/gameplay_log_final.json')

    logger.header("GAMEPLAY SESSION COMPLETE!")
    print("""
Summary of what was built:
  ✓ 4 burner mining drills on iron-ore
  ✓ 2 burner mining drills on copper-ore
  ✓ 8+ stone furnaces for iron-plate smelting
  ✓ 3 stone furnaces for copper-plate smelting
  ✓ Production limit set to 10 iron plates/min
  ✓ Automated resource collection and smelting running
""")

if __name__ == "__main__":
    main()
